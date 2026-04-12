"""LLM service: Anthropic SDK wrapper, prompt builder, circuit breaker, usage logging.

Provides async helpers for the generate_llm_brief_enhancement Celery task.
All functions are pure or use injected dependencies (session, redis) — no
global state except the schema definition.
"""
from __future__ import annotations

import json
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.config import (
    ANTHROPIC_MODEL,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_TTL_SECONDS,
    INPUT_CHAR_BUDGET,
    OUTPUT_TOKEN_BUDGET,
)
from app.services.llm.pricing import compute_cost

# ---------------------------------------------------------------------------
# Structured output schema (D-03) — verbatim from RESEARCH.md Pattern 3
# ---------------------------------------------------------------------------

BRIEF_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "expanded_sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["heading", "content"],
                "additionalProperties": False,
            },
        },
        "faq_block": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
                "additionalProperties": False,
            },
        },
        "title_variants": {
            "type": "array",
            "items": {"type": "string"},
        },
        "meta_variants": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["expanded_sections", "faq_block", "title_variants", "meta_variants"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Pydantic model for validating LLM output (D-03)
# ---------------------------------------------------------------------------


class _ExpandedSection(BaseModel):
    heading: str
    content: str


class _FaqItem(BaseModel):
    question: str
    answer: str


class LLMBriefEnhancement(BaseModel):
    """Validates the structured JSON returned by the Anthropic API."""

    expanded_sections: list[_ExpandedSection]
    faq_block: list[_FaqItem]
    title_variants: list[str]
    meta_variants: list[str]


# ---------------------------------------------------------------------------
# Prompt builder (LLM-02: all 5 context types required)
# ---------------------------------------------------------------------------


def build_brief_prompt(brief: object, context: dict) -> str:
    """Build a Russian-language prompt for brief AI enhancement.

    Includes all 5 context types required by LLM-02:
      1. Brief title + H2/H3 outline
      2. Top-20 keywords with positions
      3. Top-10 gap keywords
      4. GEO score
      5. Cannibalization clusters (top 5)
      6. Competitor list (top 5)

    Prompt is hard-truncated to INPUT_CHAR_BUDGET chars.

    Args:
        brief: ContentBrief ORM object (or any object with title, headings_json attrs).
        context: Dict with optional keys: keywords, gap_keywords, geo_score,
                 cannibalization, competitors.

    Returns:
        Prompt string ready for the Anthropic messages API.
    """
    title = getattr(brief, "title", "") or getattr(brief, "recommended_title", "") or ""
    headings_json = getattr(brief, "headings_json", []) or []

    # Build heading outline
    heading_lines = []
    for h in headings_json:
        level = h.get("level", 2)
        text = h.get("text", "")
        prefix = "  " if level == 3 else ""
        heading_lines.append(f"{prefix}H{level}: {text}")
    heading_outline = "\n".join(heading_lines) if heading_lines else "(нет данных)"

    # Top-20 keywords with positions
    keywords = context.get("keywords", []) or []
    if keywords:
        kw_lines = []
        for kw in keywords[:20]:
            phrase = kw.get("phrase", "") if isinstance(kw, dict) else str(kw)
            pos = kw.get("position", "") if isinstance(kw, dict) else ""
            pos_str = f" (позиция: {pos})" if pos else ""
            kw_lines.append(f"  - {phrase}{pos_str}")
        keywords_text = "\n".join(kw_lines)
    else:
        keywords_text = "(нет данных)"

    # Top-10 gap keywords
    gap_keywords = context.get("gap_keywords", []) or []
    if gap_keywords:
        gap_lines = [
            f"  - {kw.get('phrase', kw) if isinstance(kw, dict) else kw}"
            for kw in gap_keywords[:10]
        ]
        gap_text = "\n".join(gap_lines)
    else:
        gap_text = "(нет данных)"

    # GEO score
    geo_score = context.get("geo_score")
    geo_text = str(geo_score) if geo_score is not None else "(нет данных)"

    # Cannibalization clusters (top 5)
    cannibalization = context.get("cannibalization", []) or []
    if cannibalization:
        cann_lines = []
        for cluster in cannibalization[:5]:
            if isinstance(cluster, dict):
                kws = cluster.get("keywords", cluster.get("phrases", []))
                kws_str = ", ".join(str(k) for k in kws[:5])
                cann_lines.append(f"  - {kws_str}")
            else:
                cann_lines.append(f"  - {cluster}")
        cann_text = "\n".join(cann_lines)
    else:
        cann_text = "(нет данных)"

    # Competitors (top 5)
    competitors = context.get("competitors", []) or []
    if competitors:
        comp_lines = [
            f"  - {c.get('domain', c.get('url', str(c))) if isinstance(c, dict) else c}"
            for c in competitors[:5]
        ]
        comp_text = "\n".join(comp_lines)
    else:
        comp_text = "(нет данных)"

    prompt_body = f"""Ты — опытный SEO-стратег. Улучши контент-бриф, добавив расширенные разделы, FAQ-блок и варианты title/meta, учитывая следующий контекст.

## Бриф: {title}

### Структура заголовков
{heading_outline}

### Топ-20 ключевых слов с позициями
{keywords_text}

### Топ-10 ключевых запросов-пробелов (gap keywords)
{gap_text}

### GEO-оценка готовности страницы
{geo_text}

### Кластеры каннибализации (топ-5)
{cann_text}

### Конкуренты (топ-5)
{comp_text}

## Задача
Верни JSON строго по схеме:
- expanded_sections: 3-5 новых разделов со структурированным контентом
- faq_block: 5-8 вопросов и ответов в формате FAQ
- title_variants: 3 варианта title (до 60 символов)
- meta_variants: 3 варианта meta description (до 160 символов)

Ответ только на русском языке. Только JSON, без пояснений."""

    # Hard-truncate to INPUT_CHAR_BUDGET
    if len(prompt_body) > INPUT_CHAR_BUDGET:
        prompt_body = prompt_body[:INPUT_CHAR_BUDGET]

    return prompt_body


# ---------------------------------------------------------------------------
# Anthropic API call (RESEARCH Pattern 3)
# ---------------------------------------------------------------------------


async def call_llm_brief_enhance(
    api_key: str, prompt: str
) -> tuple[dict, int, int]:
    """Call the Anthropic API to enhance a brief and return structured JSON.

    Args:
        api_key: Plaintext Anthropic API key.
        prompt: Built prompt string from build_brief_prompt().

    Returns:
        Tuple of (parsed_json_dict, input_tokens, output_tokens).

    Raises:
        anthropic.APIError subclasses on API failures (callers must handle).
    """
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=OUTPUT_TOKEN_BUDGET,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": BRIEF_OUTPUT_SCHEMA,
            }
        },
    )
    parsed = json.loads(response.content[0].text)
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    return parsed, input_tokens, output_tokens


# ---------------------------------------------------------------------------
# Circuit breaker helpers (D-06, LLM-04)
# ---------------------------------------------------------------------------

_CB_KEY = "llm:cb:user:{user_id}"
_CB_FAILS_KEY = "llm:cb:fails:{user_id}"


async def is_circuit_open(redis, user_id: int) -> bool:
    """Return True if the per-user circuit breaker is OPEN (user is blocked)."""
    key = _CB_KEY.format(user_id=user_id)
    val = await redis.get(key)
    return val is not None


async def record_llm_failure(redis, user_id: int) -> None:
    """Increment the failure counter; open circuit if threshold is reached.

    - Increments llm:cb:fails:{user_id} (TTL 900s auto-set on first failure)
    - When count >= CIRCUIT_BREAKER_FAILURE_THRESHOLD, sets llm:cb:user:{user_id}
      with TTL 900s, marking the circuit OPEN.
    """
    fails_key = _CB_FAILS_KEY.format(user_id=user_id)
    cb_key = _CB_KEY.format(user_id=user_id)

    count = await redis.incr(fails_key)
    if count == 1:
        # Set TTL only on first increment so it self-clears
        await redis.expire(fails_key, CIRCUIT_BREAKER_TTL_SECONDS)

    if count >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
        await redis.set(cb_key, "open", ex=CIRCUIT_BREAKER_TTL_SECONDS)


async def record_llm_success(redis, user_id: int) -> None:
    """Reset circuit breaker on successful LLM call."""
    await redis.delete(
        _CB_KEY.format(user_id=user_id),
        _CB_FAILS_KEY.format(user_id=user_id),
    )


async def reset_circuit(redis, user_id: int) -> None:
    """Manual circuit reset — same as success."""
    await record_llm_success(redis, user_id)


# ---------------------------------------------------------------------------
# Agent execution call (Phase 999.9)
# ---------------------------------------------------------------------------


async def call_agent(
    api_key: str,
    *,
    system_prompt: str,
    user_message: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> tuple[str, int, int]:
    """Call Anthropic for agent execution. Returns (output_text, input_tokens, output_tokens)."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        temperature=temperature,
    )
    text = response.content[0].text
    return text, response.usage.input_tokens, response.usage.output_tokens


# ---------------------------------------------------------------------------
# Usage logging
# ---------------------------------------------------------------------------


async def log_llm_usage(
    session: AsyncSession,
    *,
    user_id,
    brief_id,
    job_id,
    model: str,
    input_tokens: int,
    output_tokens: int,
    status: str,
    error_message: str | None = None,
) -> None:
    """Insert an LLMUsage row recording token consumption and cost.

    Args:
        session: Async SQLAlchemy session.
        user_id: User UUID (or None).
        brief_id: ContentBrief UUID (or None).
        job_id: LLMBriefJob integer ID (or None).
        model: Model ID string (used for cost lookup).
        input_tokens: Input token count.
        output_tokens: Output token count.
        status: "success" or "failed".
        error_message: Optional error description for failed calls.
    """
    from app.models.llm_brief_job import LLMUsage

    cost = compute_cost(model, input_tokens, output_tokens)
    usage = LLMUsage(
        user_id=user_id,
        brief_id=brief_id,
        job_id=job_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        status=status,
        error_message=error_message,
    )
    session.add(usage)
    await session.flush()
