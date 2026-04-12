"""Celery task for AI agent execution (Phase 999.9).

Calls Anthropic via call_agent() with per-agent model/temperature/max_tokens.
Retry=3 for transient errors per CLAUDE.md mandate.

Error handling mirrors llm_tasks.py:
- Transient errors (network, timeout, 429, 529 overloaded) → self.retry with exponential backoff.
- Permanent errors (401/403 auth, 400 bad request) → fail fast, no retry.
- Circuit breaker (Redis) applied per-user.
"""
from __future__ import annotations

import asyncio

from loguru import logger

from app.celery_app import celery_app


# ---------------------------------------------------------------------------
# Internal sentinel exception for Celery retry signaling
# ---------------------------------------------------------------------------


class _TransientAgentError(Exception):
    """Raised inside _run_agent_job to signal Celery should retry.

    Does NOT trip the circuit breaker — transient network blips
    should not penalize the user.
    """

    pass


# ---------------------------------------------------------------------------
# Dependency getters (injectable for tests)
# ---------------------------------------------------------------------------


def _get_async_session():
    """Return an async DB session context manager (AsyncSessionLocal())."""
    from app.database import AsyncSessionLocal

    return AsyncSessionLocal()


def _get_redis():
    """Return a connected async Redis client."""
    import redis.asyncio as aioredis

    from app.config import settings

    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


# ---------------------------------------------------------------------------
# Celery task entry point
# ---------------------------------------------------------------------------


@celery_app.task(
    name="agents.run_agent_job",
    bind=True,
    max_retries=3,
    queue="default",
)
def run_agent_job(self, job_id: int) -> None:
    """Execute an AI agent job using the stored prompt template.

    Flow:
      1. Load AgentJob and set status='running'
      2. Load AIAgent for model/temperature/max_tokens/prompts
      3. Render user_template with inputs_json
      4. Check per-user circuit breaker (Redis)
      5. Call Anthropic via call_agent()
      6. Write output_text to AgentJob, status='done'
      7. Increment agent usage_count

    Error handling:
      - Agent not found → status='error', no retry
      - Permanent Anthropic error (401/403/400) → status='error', no retry
      - Transient error on non-final retry → self.retry(countdown=60*2**retries)
      - Transient error exhausted → status='error', error_message set

    Args:
        job_id: Primary key of AgentJob to process.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            _run_agent_job(
                job_id=job_id,
                current_retry=self.request.retries,
                max_retries=self.max_retries,
            )
        )
    except _TransientAgentError as exc:
        countdown = 60 * 2 ** self.request.retries
        logger.warning(
            "Agent transient error on job {}, retry {} of {}, countdown={}s: {}",
            job_id,
            self.request.retries,
            self.max_retries,
            countdown,
            exc,
        )
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.error("Agent task unexpected error for job {}: {}", job_id, exc)
        raise
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Async implementation
# ---------------------------------------------------------------------------


async def _run_agent_job(
    job_id: int, current_retry: int, max_retries: int
) -> None:
    """Async body of run_agent_job.

    Separated from the sync task wrapper so it can be tested directly
    without running a full Celery worker.
    """
    from app.services.agent_service import (
        get_job,
        increment_usage_count,
        render_template,
    )
    from app.services.llm.llm_service import call_agent
    from app.services.user_service import get_anthropic_api_key

    async with _get_async_session() as session:
        # 1. Load job
        job = await get_job(session, job_id)
        if not job:
            logger.warning("AgentJob {} not found — skipping", job_id)
            return

        job.status = "running"
        await session.commit()

        # 2. Load agent
        if job.agent_id is None:
            await _set_job_error(
                session, job, "Agent ID not set on job"
            )
            return

        from app.models.agent import AIAgent

        agent = await session.get(AIAgent, job.agent_id)
        if agent is None:
            await _set_job_error(
                session, job, f"AIAgent {job.agent_id} not found"
            )
            return

        # 3. Render user_template
        rendered = render_template(agent.user_template, job.inputs_json or {})

        # 4. Get API key from user
        from app.models.user import User

        user = await session.get(User, job.user_id) if job.user_id else None
        api_key: str | None = None

        if user is not None:
            api_key = await get_anthropic_api_key(session, user)

        if not api_key:
            await _set_job_error(
                session, job, "Anthropic API key not configured for this user"
            )
            return

        # 5. Circuit breaker check
        from app.services.llm.llm_service import (
            is_circuit_open,
            record_llm_failure,
            record_llm_success,
        )

        redis = _get_redis()
        user_key = user.id if user else job_id  # fallback to job_id if no user

        if await is_circuit_open(redis, user_key):
            await _set_job_error(
                session,
                job,
                "LLM circuit open — повторите попытку через 15 минут",
            )
            return

        # 6. Call Anthropic
        from anthropic import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            AuthenticationError,
            BadRequestError,
            PermissionDeniedError,
            RateLimitError,
        )

        try:
            text, in_tok, out_tok = await call_agent(
                api_key,
                system_prompt=agent.system_prompt,
                user_message=rendered,
                model=agent.model,
                temperature=float(agent.temperature),
                max_tokens=agent.max_tokens,
            )
        except (AuthenticationError, PermissionDeniedError, BadRequestError) as exc:
            # PERMANENT — fail fast, trip circuit breaker, do NOT retry
            logger.error(
                "Agent permanent error for job {} agent {}: {}",
                job_id,
                agent.id,
                exc,
            )
            await record_llm_failure(redis, user_key)
            await _set_job_error(
                session, job, f"Anthropic permanent error: {exc}"
            )
            return
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            # TRANSIENT — retry; only trip circuit on final retry
            if current_retry >= max_retries:
                logger.error(
                    "Agent transient error exhausted retries for job {} agent {}: {}",
                    job_id,
                    agent.id,
                    exc,
                )
                await record_llm_failure(redis, user_key)
                await _set_job_error(
                    session,
                    job,
                    f"API недоступен после {max_retries} попыток",
                )
                return
            raise _TransientAgentError(str(exc)) from exc
        except APIStatusError as exc:
            # 429 / 529 / 5xx — transient; 400/401/403 handled above
            if exc.status_code in (429, 529) or 500 <= exc.status_code < 600:
                if current_retry < max_retries:
                    raise _TransientAgentError(str(exc)) from exc
                await record_llm_failure(redis, user_key)
                await _set_job_error(
                    session,
                    job,
                    f"API недоступен после {max_retries} попыток",
                )
                return
            # Other status errors — permanent
            await record_llm_failure(redis, user_key)
            await _set_job_error(
                session, job, f"Anthropic API error {exc.status_code}: {exc}"
            )
            return
        except Exception as exc:
            logger.error(
                "Agent unexpected error for job {} agent {}: {}",
                job_id,
                agent.id,
                exc,
            )
            await record_llm_failure(redis, user_key)
            await _set_job_error(session, job, f"Unexpected error: {exc}")
            return

        # 7. Success — write output
        job.status = "done"
        job.output_text = text
        job.input_tokens = in_tok
        job.output_tokens = out_tok
        await session.commit()

        # Reset circuit breaker on success
        await record_llm_success(redis, user_key)

        # 8. Increment usage count
        await increment_usage_count(session, agent.id)
        await session.commit()

        logger.info(
            "Agent job done: job={} agent={} in_tok={} out_tok={}",
            job_id,
            agent.id,
            in_tok,
            out_tok,
        )


async def _set_job_error(session, job, message: str) -> None:
    """Set job status to 'error' and commit."""
    job.status = "error"
    job.error_message = message
    await session.commit()
    logger.warning("AgentJob {} error: {}", job.id, message)
