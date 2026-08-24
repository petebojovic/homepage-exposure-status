import asyncio

import httpx
import pytest
import respx

from homepage_exposure_status.checks.check_host import CheckHostChecker, NodeResult, parse_node_results


def test_parse_node_results_skips_nodes_still_checking():
    raw = {
        "node1": [[1, 0.123, "OK", "200", "1.2.3.4"]],
        "node2": None,
    }

    results = parse_node_results(raw)

    assert results == [
        NodeResult(
            node_name="node1",
            success_flag=1,
            response_time=0.123,
            message="OK",
            status_code="200",
            resolved_ip="1.2.3.4",
        )
    ]


def test_parse_node_results_handles_multiple_finished_nodes():
    raw = {
        "node1": [[1, 0.1, "OK", "200", "1.2.3.4"]],
        "node2": [[0, None, "Connection refused", None, None]],
    }

    results = parse_node_results(raw)

    assert {result.node_name for result in results} == {"node1", "node2"}
    node2 = next(result for result in results if result.node_name == "node2")
    assert node2.status_code is None


@pytest.fixture
def checker(monkeypatch):
    async def instant_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", instant_sleep)
    return CheckHostChecker()


@respx.mock
async def test_check_returns_true_when_host_is_reachable(checker):
    respx.get("https://check-host.net/check-http").mock(
        return_value=httpx.Response(200, json={"request_id": "abc123"})
    )
    respx.get("https://check-host.net/check-result/abc123").mock(
        return_value=httpx.Response(200, json={"node1": [[1, 0.1, "OK", "200", "1.2.3.4"]]})
    )

    assert await checker.check("example.com") is True


@respx.mock
async def test_check_returns_false_when_host_is_never_reachable(checker):
    respx.get("https://check-host.net/check-http").mock(
        return_value=httpx.Response(200, json={"request_id": "abc123"})
    )
    respx.get("https://check-host.net/check-result/abc123").mock(
        return_value=httpx.Response(
            200, json={"node1": [[0, None, "Connection refused", None, None]]}
        )
    )

    assert await checker.check("example.com", max_attempts=2) is False


@respx.mock
async def test_check_returns_false_when_initial_request_fails(checker):
    respx.get("https://check-host.net/check-http").mock(return_value=httpx.Response(500))

    assert await checker.check("example.com") is False


@respx.mock
async def test_check_recovers_after_a_transient_polling_error(checker):
    respx.get("https://check-host.net/check-http").mock(
        return_value=httpx.Response(200, json={"request_id": "abc123"})
    )
    respx.get("https://check-host.net/check-result/abc123").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200, json={"node1": [[1, 0.1, "OK", "200", "1.2.3.4"]]}),
        ]
    )

    assert await checker.check("example.com", max_attempts=2) is True
