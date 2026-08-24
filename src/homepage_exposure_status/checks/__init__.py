import os
import time
import logging
from homepage_exposure_status.checks.base import Checker
from homepage_exposure_status.checks.check_host import CheckHostChecker

logger = logging.getLogger(__name__)

CHECKERS: dict[str, Checker] = {
    "check_host": CheckHostChecker()
}

DEFAULT_ENABLED_CHECKS = "check_host"
# Off by default (0). Homepage's own refreshInterval already controls how
# often the UI re-checks. This is an opt-in workaround for setups that
# want an even longer *effective* interval than whatever refreshInterval
# is set to (e.g. many services, several viewers/tabs), without needing
# to also make the dashboard itself feel slower to update. Only meaningful
# set *longer* than refreshInterval; equal or shorter provides no benefit
# since every scheduled poll would still be a cache miss.
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "0"))

# Homepage polls us on its own schedule regardless of how often anything
# actually needs to change. When enabled, this caches each (checker, url)
# result so repeated polling doesn't turn into repeated load on
# check-host.net (or any future checker's own upstream). Keyed and
# read/written synchronously within a single event loop tick, no lock needed.
_cache: dict[tuple[str, str], tuple[bool, float]] = {}

def get_enabled_checks() -> list[str]:
    requested = os.getenv("ENABLED_CHECKS", DEFAULT_ENABLED_CHECKS)
    names = [name.strip() for name in requested.split(",") if name.strip()]

    enabled = []
    for name in names:
        if name not in CHECKERS:
            logger.warning("ENABLED_CHECKS lists unknown checker '%s', ignoring", name)
            continue
        if not CHECKERS[name].is_configured():
            logger.warning("Checker '%s' is enabled but not configured, skipping", name)
            continue
        enabled.append(name)

    return enabled

def clear_cache(url: str | None = None) -> int:
    """Clear cached results. If url is given, only that hostname's entries
    (across all checkers); otherwise everything. Returns the number of
    entries removed."""
    if url is None:
        count = len(_cache)
        _cache.clear()
        return count

    keys_to_remove = [key for key in _cache if key[1] == url]
    for key in keys_to_remove:
        del _cache[key]
    return len(keys_to_remove)

async def close_all() -> None:
    for checker in CHECKERS.values():
        await checker.close()

async def run_checks(url: str) -> dict[str, bool]:
    results = {}
    now = time.monotonic()
    for check_name in get_enabled_checks():
        cache_key = (check_name, url)
        if CACHE_TTL_SECONDS > 0:
            cached = _cache.get(cache_key)
            if cached is not None and now - cached[1] < CACHE_TTL_SECONDS:
                results[check_name] = cached[0]
                continue

        try:
            result = await CHECKERS[check_name].check(url)
        except Exception as e:
            logger.error("Error occurred while running check '%s' for URL %s: %s", check_name, url, e)
            # Not cached: a transient failure shouldn't lock in a wrong
            # answer for the full TTL. Next poll should retry from scratch.
            results[check_name] = False
            continue

        results[check_name] = result
        if CACHE_TTL_SECONDS > 0:
            _cache[cache_key] = (result, now)
    return results