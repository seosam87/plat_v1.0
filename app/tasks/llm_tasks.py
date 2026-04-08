"""Celery task for AI-powered brief enhancement (Phase 16 LLM-03).

Calls Anthropic Claude Haiku 4.5 to generate expanded sections, FAQ block,
and title/meta variants for an existing template content brief.

CLAUDE.md mandates retry=3 for all external API calls.
- Transient errors (network, timeout, 429, 529 overloaded) → self.retry with exponential backoff.
- Permanent errors (401/403 auth, 400 bad request) → fail fast, no retry.
- Circuit breaker (record_llm_failure) only fires on REAL failure (after retries exhausted OR
  permanent error), NOT on every transient retry — prevents circuit opening from a single flaky blip.

LLM-03 invariant: this task is purely additive — template brief generation is NEVER modified
or blocked by this task. The template brief always exists before this task runs.
"""
from __future__ import annotations

import asyncio

from loguru import logger

from app.celery_app import celery_app
from app.services.llm.config import ANTHROPIC_MODEL
from app.services.notifications import notify


# ---------------------------------------------------------------------------
# Internal sentinel exception for Celery retry signaling
# ---------------------------------------------------------------------------


class _TransientLLMError(Exception):
    """Raised inside _run_enhance to signal Celery should retry.

    Does NOT trip the per-user circuit breaker — transient network blips
    should not penalize the user's LLM circuit.
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
    name="llm.generate_brief_enhancement",
    bind=True,
    max_retries=3,
    queue="default",
)
def generate_llm_brief_enhancement(self, job_id: int) -> None:
    """Enhance a content brief using Claude Haiku 4.5.

    Flow:
      1. Load LLMBriefJob and User from DB
      2. Check per-user circuit breaker (Redis)
      3. Retrieve decrypted Anthropic API key
      4. Load ContentBrief + build context
      5. Build prompt and call Anthropic API
      6. Parse structured JSON response
      7. Write output_json to LLMBriefJob, status='done'
      8. Log LLMUsage row

    Error handling:
      - No API key → status='failed', no retry
      - Circuit open → status='failed', no retry
      - Permanent Anthropic error (401/403/400) → status='failed', circuit ++, no retry
      - Transient error on non-final retry → self.retry(countdown=60*2**retries)
      - Transient error exhausted → status='failed', circuit ++

    Args:
        job_id: Primary key of LLMBriefJob to process.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            _run_enhance(
                job_id=job_id,
                task_retries=self.request.retries,
                max_retries=self.max_retries,
            )
        )
    except _TransientLLMError as exc:
        # Exponential back-off: 60s, 120s, 240s
        countdown = 60 * 2 ** self.request.retries
        logger.warning(
            "LLM transient error on job {}, retry {} of {}, countdown={}s: {}",
            job_id, self.request.retries, self.max_retries, countdown, exc,
        )
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.error("LLM task unexpected error for job {}: {}", job_id, exc)
        raise
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Async implementation
# ---------------------------------------------------------------------------


async def _run_enhance(job_id: int, task_retries: int, max_retries: int) -> None:
    """Async body of generate_llm_brief_enhancement.

    Separated from the sync task wrapper so it can be tested directly
    without running a full Celery worker.
    """
    from app.models.llm_brief_job import LLMBriefJob
    from app.models.user import User
    from app.services.llm import llm_service
    from app.services.user_service import get_anthropic_api_key
    from app.services.brief_service import get_brief

    async with _get_async_session() as session:
        # 1. Load job
        job = await session.get(LLMBriefJob, job_id)
        if not job:
            logger.warning("LLMBriefJob {} not found — skipping", job_id)
            return

        job.status = "running"
        await session.commit()

        # 2. Load user
        user = await session.get(User, job.user_id)
        if not user:
            await _mark_failed(session, job, None, "User not found", redis=None)
            return

        redis = _get_redis()

        # 3. Circuit breaker check
        if await llm_service.is_circuit_open(redis, user.id):
            await _mark_failed(
                session, job, user,
                "LLM circuit open — повторите попытку через 15 минут",
                redis=redis,
            )
            return

        # 4. API key
        api_key = await get_anthropic_api_key(session, user)
        if not api_key:
            await _mark_failed(
                session, job, user,
                "Anthropic API key not configured for this user",
                redis=redis,
            )
            return

        # 5. Load brief and build context
        brief = await get_brief(session, job.brief_id)
        if not brief:
            await _mark_failed(
                session, job, user,
                f"ContentBrief {job.brief_id} not found",
                redis=redis,
            )
            return

        # Build minimal context from brief data (LLM-02: all 5 types required)
        context = {
            "keywords": brief.keywords_json or [],
            "gap_keywords": [],       # populated by Plan 04 when gap analysis available
            "geo_score": None,        # populated by Plan 04 when page geo_score available
            "cannibalization": [],    # populated by Plan 04 when cannibalization data available
            "competitors": (
                [{"domain": brief.competitor_data_json.get("domain", "")}]
                if brief.competitor_data_json and brief.competitor_data_json.get("domain")
                else []
            ),
        }

        prompt = llm_service.build_brief_prompt(brief, context)

        # 6. Call Anthropic — distinguish transient vs permanent errors
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
            output, in_tok, out_tok = await llm_service.call_llm_brief_enhance(api_key, prompt)
        except (AuthenticationError, PermissionDeniedError, BadRequestError) as exc:
            # PERMANENT — fail fast, trip circuit breaker, do NOT retry
            logger.error(
                "LLM permanent error for job {} user {}: {}",
                job_id, user.id, exc,
            )
            await llm_service.record_llm_failure(redis, user.id)
            await _mark_failed(
                session, job, user,
                f"Anthropic permanent error: {exc}",
                redis=redis,
                in_tok=0,
                out_tok=0,
            )
            return
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            # TRANSIENT — retry via self.retry; only trip circuit on final retry
            if task_retries >= max_retries:
                logger.error(
                    "LLM transient error exhausted retries for job {} user {}: {}",
                    job_id, user.id, exc,
                )
                await llm_service.record_llm_failure(redis, user.id)
                await _mark_failed(
                    session, job, user,
                    f"Anthropic transient error after {max_retries} retries: {exc}",
                    redis=redis,
                    in_tok=0,
                    out_tok=0,
                )
                return
            raise _TransientLLMError(str(exc)) from exc
        except APIStatusError as exc:
            # 5xx server errors — treat as transient
            if 500 <= exc.status_code < 600 and task_retries < max_retries:
                raise _TransientLLMError(str(exc)) from exc
            await llm_service.record_llm_failure(redis, user.id)
            await _mark_failed(
                session, job, user,
                f"Anthropic API error {exc.status_code}: {exc}",
                redis=redis,
                in_tok=0,
                out_tok=0,
            )
            return
        except Exception as exc:
            # Unknown — treat as permanent to be safe
            logger.error(
                "LLM unexpected error for job {} user {}: {}",
                job_id, user.id, exc,
            )
            await llm_service.record_llm_failure(redis, user.id)
            await _mark_failed(
                session, job, user,
                f"Unexpected error: {exc}",
                redis=redis,
                in_tok=0,
                out_tok=0,
            )
            return

        # 7. Success — write output
        job.status = "done"
        job.output_json = output
        await session.commit()

        # 8. Reset circuit breaker + log usage
        await llm_service.record_llm_success(redis, user.id)
        await llm_service.log_llm_usage(
            session,
            user_id=user.id,
            brief_id=job.brief_id,
            job_id=job.id,
            model=ANTHROPIC_MODEL,
            input_tokens=in_tok,
            output_tokens=out_tok,
            status="success",
        )
        await session.commit()

        logger.info(
            "LLM brief enhancement done: job={} brief={} in_tok={} out_tok={}",
            job_id, job.brief_id, in_tok, out_tok,
        )

        # In-app notification — user_id is available from loaded user object (D-02)
        await notify(
            db=session,
            user_id=user.id,
            kind="llm_brief.ready",
            title="AI-бриф готов",
            body=f"Бриф для {brief.topic} сгенерирован",
            link_url=f"/llm-briefs/{job.brief_id}",
            severity="info",
        )
        await session.commit()


async def _mark_failed(
    session,
    job,
    user,
    message: str,
    *,
    redis,
    in_tok: int = 0,
    out_tok: int = 0,
) -> None:
    """Set job status to 'failed' and log an LLMUsage row."""
    from app.services.llm import llm_service

    job.status = "failed"
    job.error_message = message
    await session.commit()

    if user is not None:
        try:
            await llm_service.log_llm_usage(
                session,
                user_id=user.id,
                brief_id=job.brief_id,
                job_id=job.id,
                model=ANTHROPIC_MODEL,
                input_tokens=in_tok,
                output_tokens=out_tok,
                status="failed",
                error_message=message,
            )
            await session.commit()
        except Exception as log_exc:
            logger.warning("Failed to log LLM usage for failed job {}: {}", job.id, log_exc)

        # In-app failure notification — user_id is available from loaded user object (D-02)
        try:
            await notify(
                db=session,
                user_id=user.id,
                kind="llm_brief.failed",
                title="AI-бриф: ошибка",
                body=f"Ошибка генерации брифа: {message[:200]}",
                link_url=f"/llm-briefs/{job.brief_id}",
                severity="error",
            )
            await session.commit()
        except Exception as notify_exc:
            logger.warning("Failed to insert failure notification for job {}: {}", job.id, notify_exc)
