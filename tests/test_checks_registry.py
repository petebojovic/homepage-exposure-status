import time

import pytest

from homepage_exposure_status import checks
from homepage_exposure_status.checks.base import Checker


class FakeChecker(Checker):
    def __init__(self, configured: bool = True, result: bool = True, error: Exception | None = None):
        self._configured = configured
        self._result = result
        self._error = error
        self.call_count = 0

    def is_configured(self) -> bool:
        return self._configured

    async def check(self, url: str) -> bool:
        self.call_count += 1
        if self._error:
            raise self._error
        return self._result

    async def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def restore_checkers():
    original = checks.CHECKERS.copy()
    checks._cache.clear()
    yield
    checks.CHECKERS.clear()
    checks.CHECKERS.update(original)
    checks._cache.clear()


def test_default_enabled_checks_is_check_host(monkeypatch):
    monkeypatch.delenv("ENABLED_CHECKS", raising=False)

    assert checks.get_enabled_checks() == ["check_host"]


def test_unknown_checker_name_is_dropped(monkeypatch):
    monkeypatch.setenv("ENABLED_CHECKS", "check_host,not_a_real_checker")

    assert checks.get_enabled_checks() == ["check_host"]


def test_unconfigured_checker_is_dropped(monkeypatch):
    checks.CHECKERS["fake"] = FakeChecker(configured=False)
    monkeypatch.setenv("ENABLED_CHECKS", "fake")

    assert checks.get_enabled_checks() == []


def test_empty_enabled_checks_returns_nothing(monkeypatch):
    monkeypatch.setenv("ENABLED_CHECKS", "")

    assert checks.get_enabled_checks() == []


async def test_run_checks_collects_results_by_name(monkeypatch):
    checks.CHECKERS["fake"] = FakeChecker(result=True)
    monkeypatch.setenv("ENABLED_CHECKS", "fake")

    result = await checks.run_checks("example.com")

    assert result == {"fake": True}


async def test_run_checks_treats_exceptions_as_false(monkeypatch):
    checks.CHECKERS["fake"] = FakeChecker(error=RuntimeError("boom"))
    monkeypatch.setenv("ENABLED_CHECKS", "fake")

    result = await checks.run_checks("example.com")

    assert result == {"fake": False}


async def test_run_checks_is_uncached_by_default(monkeypatch):
    fake = FakeChecker(result=True)
    checks.CHECKERS["fake"] = fake
    monkeypatch.setenv("ENABLED_CHECKS", "fake")
    monkeypatch.setattr(checks, "CACHE_TTL_SECONDS", 0)

    await checks.run_checks("example.com")
    await checks.run_checks("example.com")

    assert fake.call_count == 2


async def test_run_checks_reuses_cached_result_within_ttl(monkeypatch):
    fake = FakeChecker(result=True)
    checks.CHECKERS["fake"] = fake
    monkeypatch.setenv("ENABLED_CHECKS", "fake")
    monkeypatch.setattr(checks, "CACHE_TTL_SECONDS", 3600)

    await checks.run_checks("example.com")
    await checks.run_checks("example.com")

    assert fake.call_count == 1


async def test_run_checks_recomputes_after_ttl_expires(monkeypatch):
    fake = FakeChecker(result=True)
    checks.CHECKERS["fake"] = fake
    monkeypatch.setenv("ENABLED_CHECKS", "fake")
    monkeypatch.setattr(checks, "CACHE_TTL_SECONDS", 60)

    await checks.run_checks("example.com")
    # Age the cached entry past the TTL directly, rather than mocking
    # time.monotonic globally (which also affects pytest-asyncio's own
    # internals, since it's the same shared module object).
    cached_result, _ = checks._cache[("fake", "example.com")]
    checks._cache[("fake", "example.com")] = (cached_result, time.monotonic() - 61)

    await checks.run_checks("example.com")

    assert fake.call_count == 2


async def test_run_checks_does_not_cache_exceptions(monkeypatch):
    fake = FakeChecker(error=RuntimeError("boom"))
    checks.CHECKERS["fake"] = fake
    monkeypatch.setenv("ENABLED_CHECKS", "fake")
    monkeypatch.setattr(checks, "CACHE_TTL_SECONDS", 3600)

    await checks.run_checks("example.com")
    await checks.run_checks("example.com")

    assert fake.call_count == 2


async def test_run_checks_caches_per_url_independently(monkeypatch):
    fake = FakeChecker(result=True)
    checks.CHECKERS["fake"] = fake
    monkeypatch.setenv("ENABLED_CHECKS", "fake")
    monkeypatch.setattr(checks, "CACHE_TTL_SECONDS", 3600)

    await checks.run_checks("example.com")
    await checks.run_checks("other.com")

    assert fake.call_count == 2


async def test_clear_cache_for_one_url_forces_recompute(monkeypatch):
    fake = FakeChecker(result=True)
    checks.CHECKERS["fake"] = fake
    monkeypatch.setenv("ENABLED_CHECKS", "fake")
    monkeypatch.setattr(checks, "CACHE_TTL_SECONDS", 3600)

    await checks.run_checks("example.com")
    cleared = checks.clear_cache("example.com")
    await checks.run_checks("example.com")

    assert cleared == 1
    assert fake.call_count == 2


async def test_clear_cache_for_one_url_leaves_others_cached(monkeypatch):
    fake = FakeChecker(result=True)
    checks.CHECKERS["fake"] = fake
    monkeypatch.setenv("ENABLED_CHECKS", "fake")
    monkeypatch.setattr(checks, "CACHE_TTL_SECONDS", 3600)

    await checks.run_checks("example.com")
    await checks.run_checks("other.com")
    checks.clear_cache("example.com")
    await checks.run_checks("other.com")

    assert fake.call_count == 2


async def test_clear_cache_with_no_url_clears_everything(monkeypatch):
    fake = FakeChecker(result=True)
    checks.CHECKERS["fake"] = fake
    monkeypatch.setenv("ENABLED_CHECKS", "fake")
    monkeypatch.setattr(checks, "CACHE_TTL_SECONDS", 3600)

    await checks.run_checks("example.com")
    await checks.run_checks("other.com")
    cleared = checks.clear_cache()
    await checks.run_checks("example.com")
    await checks.run_checks("other.com")

    assert cleared == 2
    assert fake.call_count == 4
