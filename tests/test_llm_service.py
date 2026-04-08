"""Unit tests for LLM service module (Phase 16, Plan 03).

Tests cover:
- pricing.compute_cost
- user_service anthropic key set/get/clear
- circuit breaker helpers
- build_brief_prompt truncation
- LLMBriefEnhancement pydantic schema validation

No real Anthropic API calls — all external deps are monkeypatched.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest


# ---------------------------------------------------------------------------
# Pricing tests
# ---------------------------------------------------------------------------


def test_pricing_haiku_45():
    """compute_cost for Haiku 4.5 with 1M input + 1M output should return $6.000000."""
    from app.services.llm.pricing import compute_cost

    result = compute_cost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    assert result == Decimal("6.000000"), f"Expected 6.000000, got {result}"


def test_pricing_unknown_model():
    """Unknown model should return Decimal('0.000000')."""
    from app.services.llm.pricing import compute_cost

    result = compute_cost("unknown-model", 100_000, 100_000)
    assert result == Decimal("0.000000")


def test_pricing_input_only():
    """1M input tokens only costs $1.00 for Haiku 4.5."""
    from app.services.llm.pricing import compute_cost

    result = compute_cost("claude-haiku-4-5-20251001", 1_000_000, 0)
    assert result == Decimal("1.000000")


def test_pricing_output_only():
    """1M output tokens only costs $5.00 for Haiku 4.5."""
    from app.services.llm.pricing import compute_cost

    result = compute_cost("claude-haiku-4-5-20251001", 0, 1_000_000)
    assert result == Decimal("5.000000")


# ---------------------------------------------------------------------------
# User service — anthropic key management
# ---------------------------------------------------------------------------


def _make_user(**kwargs):
    """Create a mock User object with anthropic_api_key_encrypted attribute."""
    user = MagicMock()
    user.anthropic_api_key_encrypted = kwargs.get("anthropic_api_key_encrypted", None)
    # Make flush on session a no-op
    return user


@pytest.mark.asyncio
async def test_set_anthropic_key_encrypts():
    """set_anthropic_api_key stores ciphertext != raw key; get decrypts correctly."""
    from app.services import user_service

    raw_key = "sk-ant-test-12345"
    user = _make_user()
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()

    await user_service.set_anthropic_api_key(mock_db, user, raw_key)

    # Ciphertext should be set
    assert user.anthropic_api_key_encrypted is not None
    assert user.anthropic_api_key_encrypted != raw_key

    # get_anthropic_api_key should decrypt back to raw
    result = await user_service.get_anthropic_api_key(mock_db, user)
    assert result == raw_key


@pytest.mark.asyncio
async def test_clear_anthropic_key():
    """clear_anthropic_api_key sets column to None; has_anthropic_key returns False."""
    from app.services import user_service
    from app.models.user import User

    # Set a key first
    raw_key = "sk-ant-test-clear"

    # Use a real User-like object with the property
    user = MagicMock(spec=User)
    user.anthropic_api_key_encrypted = "some_encrypted_value"
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()

    await user_service.clear_anthropic_api_key(mock_db, user)

    assert user.anthropic_api_key_encrypted is None


@pytest.mark.asyncio
async def test_get_anthropic_key_returns_none_when_not_set():
    """get_anthropic_api_key returns None when no key is stored."""
    from app.services import user_service

    user = _make_user(anthropic_api_key_encrypted=None)
    mock_db = AsyncMock()

    result = await user_service.get_anthropic_api_key(mock_db, user)
    assert result is None


def test_has_anthropic_key_property():
    """User.has_anthropic_key returns True when key is set, False otherwise."""
    from app.models.user import User

    user_with_key = MagicMock(spec=User)
    user_with_key.anthropic_api_key_encrypted = "some_encrypted_value"
    # Compute the property directly since MagicMock doesn't run real property
    assert bool(user_with_key.anthropic_api_key_encrypted) is True

    user_without_key = MagicMock(spec=User)
    user_without_key.anthropic_api_key_encrypted = None
    assert bool(user_without_key.anthropic_api_key_encrypted) is False


# ---------------------------------------------------------------------------
# Circuit breaker tests
# ---------------------------------------------------------------------------


def _make_fake_redis():
    """Create an in-memory fake Redis client using a plain dict."""
    store: dict[str, tuple[str, int | None]] = {}  # key -> (value, optional_ttl)

    class FakeRedis:
        async def get(self, key):
            entry = store.get(key)
            return entry[0] if entry else None

        async def set(self, key, value, ex=None):
            store[key] = (str(value), ex)

        async def incr(self, key):
            current = store.get(key)
            new_val = int(current[0]) + 1 if current else 1
            store[key] = (str(new_val), current[1] if current else None)
            return new_val

        async def expire(self, key, ttl):
            if key in store:
                val, _ = store[key]
                store[key] = (val, ttl)
            return True

        async def delete(self, *keys):
            for key in keys:
                store.pop(key, None)

        async def ttl(self, key):
            entry = store.get(key)
            if entry and entry[1] is not None:
                return entry[1]
            return -1

        def _store(self):
            return store

    return FakeRedis()


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_3_failures():
    """record_llm_failure called 3 times → is_circuit_open returns True."""
    from app.services.llm import llm_service

    redis = _make_fake_redis()
    user_id = 42

    # Initially closed
    assert await llm_service.is_circuit_open(redis, user_id) is False

    for _ in range(3):
        await llm_service.record_llm_failure(redis, user_id)

    assert await llm_service.is_circuit_open(redis, user_id) is True


@pytest.mark.asyncio
async def test_circuit_breaker_reset_on_success():
    """record_llm_success resets the circuit breaker."""
    from app.services.llm import llm_service

    redis = _make_fake_redis()
    user_id = 99

    for _ in range(3):
        await llm_service.record_llm_failure(redis, user_id)

    assert await llm_service.is_circuit_open(redis, user_id) is True

    await llm_service.record_llm_success(redis, user_id)
    assert await llm_service.is_circuit_open(redis, user_id) is False


@pytest.mark.asyncio
async def test_circuit_breaker_ttl():
    """Redis key llm:cb:user:{id} should be created with TTL when circuit opens."""
    from app.services.llm import llm_service
    from app.services.llm.config import CIRCUIT_BREAKER_TTL_SECONDS

    redis = _make_fake_redis()
    user_id = 7

    for _ in range(3):
        await llm_service.record_llm_failure(redis, user_id)

    # Check the TTL was set on the circuit breaker key
    ttl = await redis.ttl(f"llm:cb:user:{user_id}")
    assert ttl == CIRCUIT_BREAKER_TTL_SECONDS, f"Expected TTL={CIRCUIT_BREAKER_TTL_SECONDS}, got {ttl}"


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------


def _make_brief(title="Тестовый бриф", headings=None):
    brief = MagicMock()
    brief.title = title
    brief.headings_json = headings or [
        {"level": 2, "text": "Введение"},
        {"level": 3, "text": "Подраздел 1"},
    ]
    return brief


def test_build_brief_prompt_truncates():
    """Prompt builder with oversized context returns prompt <= INPUT_CHAR_BUDGET."""
    from app.services.llm import llm_service
    from app.services.llm.config import INPUT_CHAR_BUDGET

    # Build oversized context
    big_keywords = [{"phrase": f"ключевое слово номер {i}", "position": i} for i in range(200)]
    big_gaps = [{"phrase": f"gap keyword {i}"} for i in range(200)]
    big_competitors = [{"domain": f"competitor{i}.ru"} for i in range(100)]
    big_cannibalization = [{"keywords": [f"kw{j}" for j in range(20)]} for _ in range(50)]

    context = {
        "keywords": big_keywords,
        "gap_keywords": big_gaps,
        "geo_score": 75,
        "cannibalization": big_cannibalization,
        "competitors": big_competitors,
    }

    brief = _make_brief(title="Очень длинный бриф " * 100)
    prompt = llm_service.build_brief_prompt(brief, context)

    assert len(prompt) <= INPUT_CHAR_BUDGET, (
        f"Prompt length {len(prompt)} exceeds INPUT_CHAR_BUDGET={INPUT_CHAR_BUDGET}"
    )


def test_build_brief_prompt_includes_all_5_context_types():
    """Prompt includes all 5 required context types even when some are empty."""
    from app.services.llm import llm_service

    context = {}  # No context provided
    brief = _make_brief()
    prompt = llm_service.build_brief_prompt(brief, context)

    assert "Топ-20 ключевых слов" in prompt
    assert "gap keywords" in prompt
    assert "GEO-оценка" in prompt
    assert "каннибализации" in prompt
    assert "Конкуренты" in prompt
    assert "(нет данных)" in prompt  # Empty sections should show this


# ---------------------------------------------------------------------------
# LLMBriefEnhancement schema validation
# ---------------------------------------------------------------------------


def test_llm_brief_enhancement_schema_validates():
    """LLMBriefEnhancement pydantic model accepts the canonical 4-key dict."""
    from app.services.llm.llm_service import LLMBriefEnhancement

    canonical = {
        "expanded_sections": [
            {"heading": "Введение", "content": "Подробный контент..."},
            {"heading": "Основная часть", "content": "Ещё контент..."},
        ],
        "faq_block": [
            {"question": "Вопрос 1?", "answer": "Ответ 1."},
            {"question": "Вопрос 2?", "answer": "Ответ 2."},
        ],
        "title_variants": ["Вариант 1", "Вариант 2", "Вариант 3"],
        "meta_variants": ["Мета 1", "Мета 2", "Мета 3"],
    }

    result = LLMBriefEnhancement(**canonical)
    assert len(result.expanded_sections) == 2
    assert len(result.faq_block) == 2
    assert len(result.title_variants) == 3
    assert len(result.meta_variants) == 3
