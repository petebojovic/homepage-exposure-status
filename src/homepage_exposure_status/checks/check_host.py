"""This module provides a Checker that checks HTTP reachability using the Check Host API.
"""

import os
import logging
import asyncio
import httpx
from dataclasses import dataclass
from homepage_exposure_status.checks.base import Checker

logger = logging.getLogger(__name__)

CHECK_HOST_MAX_NODES = int(os.getenv("CHECK_HOST_MAX_NODES", "3"))
CHECK_HOST_TIMEOUT = 10  # seconds

CHECK_HOST_BASE_URL = "https://check-host.net/"
CHECK_HOST_CHECK_HTTP_URL = "check-http"
CHECK_HOST_CHECK_RESULT_URL = "check-result"

@dataclass
class NodeResult:
    node_name: str
    success_flag: int
    response_time: float
    message: str
    status_code: str | None
    resolved_ip: str | None

def parse_node_results(check_result: dict) -> list[NodeResult]:
    node_results = []
    for node_name, result in check_result.items():
        if result is None:
            continue
        success_flag, response_time, message, status_code, resolved_ip = result[0]
        node_result = NodeResult(
            node_name=node_name,
            success_flag=success_flag,
            response_time=response_time,
            message=message,
            status_code=status_code,
            resolved_ip=resolved_ip
        )
        node_results.append(node_result)
    return node_results

class CheckHostChecker(Checker):
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=CHECK_HOST_BASE_URL,
            headers={"Accept": "application/json"},
            timeout=CHECK_HOST_TIMEOUT,
        )

    def is_configured(self) -> bool:
        """check-host.net needs no credentials, so it's always configured."""
        return True

    async def close(self) -> None:
        await self._client.aclose()

    async def check(self, url: str, max_attempts: int = 5) -> bool:
        try:
            check_http_result = await self._check_http(url)
            request_id = check_http_result["request_id"]
        except httpx.HTTPError as e:
            logger.error("Error occurred while checking HTTP status for URL %s: %s", url, e)
            return False

        for attempt in range(max_attempts):
            try:
                result = await self._is_outside_accessible(request_id)
                logger.debug("Attempt %d/%d: Check result for request_id %s: %s", attempt + 1, max_attempts, request_id, result)
            except httpx.HTTPError as e:
                logger.warning("Error occurred while checking result for request_id %s: (%s/%s) %s", request_id, attempt + 1, max_attempts, e)
                continue

            if result:
                return True

            await asyncio.sleep(1)
        return False

    async def _is_outside_accessible(self, request_id: str) -> bool:
        check_result_result = parse_node_results(await self._check_result(request_id))
        return any(result.status_code is not None for result in check_result_result)

    async def _check_http(self, url: str) -> dict:
        response = await self._client.get(CHECK_HOST_CHECK_HTTP_URL, params={"host": url, "max_nodes": CHECK_HOST_MAX_NODES})
        response.raise_for_status()
        return response.json()

    async def _check_result(self, request_id: str) -> dict:
        response = await self._client.get(f"{CHECK_HOST_CHECK_RESULT_URL}/{request_id}")
        response.raise_for_status()
        return response.json()
