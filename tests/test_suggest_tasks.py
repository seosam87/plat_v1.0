"""Unit tests for suggest_tasks Celery task.

Tests mock all external dependencies (fetch functions, Redis, DB) and call
the task function directly (not via .delay()) to test logic in isolation.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(
    job_id: str | None = None,
    seed: str = "тест",
    include_google: bool = False,
    status: str = "pending",
    cache_key: str | None = None,
) -> MagicMock:
    """Create a mock SuggestJob instance."""
    job = MagicMock()
    job.id = uuid.UUID(job_id) if job_id else uuid.uuid4()
    job.seed = seed
    job.include_google = include_google
    job.status = status
    job.cache_key = cache_key
    job.cache_hit = False
    job.result_count = None
    job.expected_count = None
    job.error_message = None
    return job


def _make_db_ctx(job: MagicMock) -> MagicMock:
    """Create a mock sync DB context manager that returns job on db.get()."""
    db = MagicMock()
    db.get.return_value = job
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# Cache hit path
# ---------------------------------------------------------------------------

class TestFetchSuggestKeywordsCacheHit:
    def test_cache_hit_sets_complete_status(self):
        """On cache hit, job.status is set to 'complete' and cache_hit=True."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест")
        cached_data = [{"keyword": "тест сео", "source": "yandex"}]

        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached_data)

        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
            patch("app.tasks.suggest_tasks.get_active_proxy_urls_sync", return_value=[]),
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            result = fetch_suggest_keywords(job_id)

        assert result["status"] == "complete"
        assert result["cache_hit"] is True
        assert result["count"] == 1
        assert job.status == "complete"
        assert job.cache_hit is True

    def test_cache_hit_does_not_call_external_apis(self):
        """On cache hit, Yandex and Google fetch functions are NOT called."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест")
        cached_data = [{"keyword": "тест", "source": "yandex"}]
        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached_data)

        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
            patch("app.tasks.suggest_tasks.fetch_yandex_suggest_sync") as mock_yandex,
            patch("app.tasks.suggest_tasks.fetch_google_suggest_sync") as mock_google,
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            fetch_suggest_keywords(job_id)

        mock_yandex.assert_not_called()
        mock_google.assert_not_called()

    def test_cache_hit_result_count_set(self):
        """On cache hit, job.result_count is set to the number of cached items."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест")
        cached_data = [
            {"keyword": "тест а", "source": "yandex"},
            {"keyword": "тест б", "source": "yandex"},
            {"keyword": "тест в", "source": "yandex"},
        ]
        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached_data)

        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            result = fetch_suggest_keywords(job_id)

        assert result["count"] == 3
        assert job.result_count == 3


# ---------------------------------------------------------------------------
# Cache miss — alphabetic expansion
# ---------------------------------------------------------------------------

class TestFetchSuggestKeywordsCacheMiss:
    def test_cache_miss_iterates_ru_alphabet_for_yandex(self):
        """On cache miss, fetches Yandex Suggest for each letter of RU_ALPHABET."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords
        from app.services.suggest_service import RU_ALPHABET

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест", include_google=False)
        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # cache miss

        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
            patch("app.tasks.suggest_tasks.get_active_proxy_urls_sync", return_value=[]),
            patch("app.tasks.suggest_tasks.fetch_yandex_suggest_sync", return_value=["подсказка"]) as mock_yandex,
            patch("app.tasks.suggest_tasks.fetch_google_suggest_sync", return_value=[]) as mock_google,
            patch("app.tasks.suggest_tasks.time") as mock_time,
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            fetch_suggest_keywords(job_id)

        # Called once per letter in RU_ALPHABET
        assert mock_yandex.call_count == len(RU_ALPHABET)
        # Google NOT called when include_google=False
        mock_google.assert_not_called()

    def test_cache_miss_also_calls_google_when_include_google_true(self):
        """On cache miss with include_google=True, also iterates alphabet for Google."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords
        from app.services.suggest_service import RU_ALPHABET

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест", include_google=True)
        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
            patch("app.tasks.suggest_tasks.get_active_proxy_urls_sync", return_value=[]),
            patch("app.tasks.suggest_tasks.fetch_yandex_suggest_sync", return_value=["подсказка"]) as mock_yandex,
            patch("app.tasks.suggest_tasks.fetch_google_suggest_sync", return_value=["google hint"]) as mock_google,
            patch("app.tasks.suggest_tasks.time") as mock_time,
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            fetch_suggest_keywords(job_id)

        # Both Yandex and Google are called for full alphabet
        assert mock_yandex.call_count == len(RU_ALPHABET)
        assert mock_google.call_count == len(RU_ALPHABET)

    def test_deduplication_applied_before_caching(self):
        """Combined results are deduplicated before writing to Redis."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест", include_google=True)
        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        # Both sources return the same keyword — dedup must collapse to 1
        duplicate_kw = "совпадающее слово"
        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
            patch("app.tasks.suggest_tasks.get_active_proxy_urls_sync", return_value=[]),
            patch("app.tasks.suggest_tasks.fetch_yandex_suggest_sync", return_value=[duplicate_kw]),
            patch("app.tasks.suggest_tasks.fetch_google_suggest_sync", return_value=[duplicate_kw]),
            patch("app.tasks.suggest_tasks.time"),
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            result = fetch_suggest_keywords(job_id)

        # 33 letters × 1 result each, but all identical = 1 unique after dedup
        assert result["count"] == 1

    def test_results_written_to_redis_with_ttl(self):
        """Results are stored in Redis with SUGGEST_CACHE_TTL after expansion."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords
        from app.services.suggest_service import SUGGEST_CACHE_TTL

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест")
        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
            patch("app.tasks.suggest_tasks.get_active_proxy_urls_sync", return_value=[]),
            patch("app.tasks.suggest_tasks.fetch_yandex_suggest_sync", return_value=["подсказка а"]),
            patch("app.tasks.suggest_tasks.time"),
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            fetch_suggest_keywords(job_id)

        # Redis set was called with the cache key and ex=SUGGEST_CACHE_TTL
        mock_redis.set.assert_called_once()
        set_call = mock_redis.set.call_args
        assert set_call.kwargs.get("ex") == SUGGEST_CACHE_TTL or (
            len(set_call.args) >= 3 and set_call.args[2] == SUGGEST_CACHE_TTL
        )

    def test_result_count_updated_on_job(self):
        """job.result_count is updated to the count of deduplicated results."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест")
        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
            patch("app.tasks.suggest_tasks.get_active_proxy_urls_sync", return_value=[]),
            patch("app.tasks.suggest_tasks.fetch_yandex_suggest_sync", return_value=["слово а", "слово б"]),
            patch("app.tasks.suggest_tasks.time"),
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            result = fetch_suggest_keywords(job_id)

        # 33 letters × 2 unique per letter = 66 unique (all unique since different per call)
        assert result["count"] == job.result_count


# ---------------------------------------------------------------------------
# Proxy exhaustion — partial results
# ---------------------------------------------------------------------------

class TestFetchSuggestKeywordsProxyExhaustion:
    def test_proxy_exhaustion_sets_partial_status(self):
        """When proxies exhausted mid-loop with some results, status is 'partial'."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords
        from app.services.suggest_service import RU_ALPHABET

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест", include_google=False)
        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        # Simulate: first letter succeeds, then all proxies fail
        call_count = 0

        def side_effect_yandex(query, proxy_url=None, timeout=10):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ["первая буква"]
            return []  # All other calls fail (simulating ban)

        # Use 1 proxy so pool exhausts quickly (proxy_idx >= len*3 = 3 after 3 rotations)
        proxies = ["http://proxy1:8080"]

        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
            patch("app.tasks.suggest_tasks.get_active_proxy_urls_sync", return_value=proxies),
            patch("app.tasks.suggest_tasks.fetch_yandex_suggest_sync", side_effect=side_effect_yandex),
            patch("app.tasks.suggest_tasks.time"),
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            result = fetch_suggest_keywords(job_id)

        assert result["status"] == "partial"
        assert result["was_banned"] is True
        assert job.status == "partial"

    def test_total_failure_sets_failed_status(self):
        """When all proxies exhausted with 0 results, status is 'failed'."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест", include_google=False)
        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        proxies = ["http://proxy1:8080"]

        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
            patch("app.tasks.suggest_tasks.get_active_proxy_urls_sync", return_value=proxies),
            patch("app.tasks.suggest_tasks.fetch_yandex_suggest_sync", return_value=[]),
            patch("app.tasks.suggest_tasks.time"),
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            result = fetch_suggest_keywords(job_id)

        assert result["status"] == "failed"
        assert job.status == "failed"
        assert job.error_message is not None

    def test_complete_status_on_success_without_ban(self):
        """When full expansion completes without proxy exhaustion, status is 'complete'."""
        from app.tasks.suggest_tasks import fetch_suggest_keywords

        job_id = str(uuid.uuid4())
        job = _make_job(job_id=job_id, seed="тест", include_google=False)
        db_ctx = _make_db_ctx(job)

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with (
            patch("app.tasks.suggest_tasks.get_sync_db", return_value=db_ctx),
            patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod,
            patch("app.tasks.suggest_tasks.get_active_proxy_urls_sync", return_value=[]),
            patch("app.tasks.suggest_tasks.fetch_yandex_suggest_sync", return_value=["подсказка"]),
            patch("app.tasks.suggest_tasks.time"),
        ):
            mock_redis_mod.from_url.return_value = mock_redis
            result = fetch_suggest_keywords(job_id)

        assert result["status"] == "complete"
        assert result["was_banned"] is False
