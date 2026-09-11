"""Retry-policy tests: 429/5xx/transport errors retried, other 4xx never."""

from __future__ import annotations

import httpx
import pytest
import respx

from cngn import CNGN, AsyncCNGN, NetworkError, RateLimitError
from conftest import API_KEY, ENCRYPTION_KEY, success_payload


@pytest.fixture()
def client(openssh_pem: str, router: respx.MockRouter) -> CNGN:
    c = CNGN(api_key=API_KEY, encryption_key=ENCRYPTION_KEY, private_key=openssh_pem)
    c._sleep = lambda delay: None
    yield c
    c.close()


def test_429_retried_then_succeeds(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    route = router.get("/balance").mock(
        side_effect=[
            httpx.Response(
                429, json={"status": 429, "message": "Too many requests. Please try again later."}
            ),
            httpx.Response(200, json=success_payload([{"balance": "1.00"}], ed25519_seed)),
        ]
    )
    delays: list[float] = []
    client._sleep = delays.append
    balances = client.get_balance()
    assert route.call_count == 2
    assert delays == [60.0]  # honors the 60-second block
    assert balances[0].balance == "1.00"


def test_5xx_retried_with_exponential_backoff(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    route = router.get("/balance").mock(
        side_effect=[
            httpx.Response(500, json={"status": 500, "message": "Internal error"}),
            httpx.Response(502, json={"status": 502, "message": "Bad gateway"}),
            httpx.Response(200, json=success_payload([], ed25519_seed)),
        ]
    )
    delays: list[float] = []
    client._sleep = delays.append
    assert client.get_balance() == []
    assert route.call_count == 3
    assert delays == [1.0, 2.0]  # backoff_base=1.0, doubling


def test_400_not_retried(client: CNGN, router: respx.MockRouter) -> None:
    route = router.get("/balance").mock(
        return_value=httpx.Response(400, json={"status": 400, "message": "No token provided"})
    )
    from cngn import AuthenticationError

    with pytest.raises(AuthenticationError):
        client.get_balance()
    assert route.call_count == 1


def test_max_retries_honored(client: CNGN, router: respx.MockRouter) -> None:
    route = router.get("/balance").mock(
        return_value=httpx.Response(500, json={"status": 500, "message": "boom"})
    )
    from cngn import APIError

    with pytest.raises(APIError):
        client.get_balance()
    assert route.call_count == 1 + 3  # initial + max_retries


def test_transport_error_wrapped_and_retried(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    route = router.get("/balance").mock(
        side_effect=[
            httpx.ConnectError("connection refused"),
            httpx.Response(200, json=success_payload([], ed25519_seed)),
        ]
    )
    assert client.get_balance() == []
    assert route.call_count == 2


def test_transport_error_exhaustion(client: CNGN, router: respx.MockRouter) -> None:
    router.get("/balance").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(NetworkError) as exc_info:
        client.get_balance()
    assert isinstance(exc_info.value.cause, httpx.ConnectError)


def test_zero_max_retries(openssh_pem: str, router: respx.MockRouter) -> None:
    client = CNGN(
        api_key=API_KEY,
        encryption_key=ENCRYPTION_KEY,
        private_key=openssh_pem,
        max_retries=0,
    )
    client._sleep = lambda delay: None
    route = router.get("/balance").mock(
        return_value=httpx.Response(
            429, json={"status": 429, "message": "Too many requests. Please try again later."}
        )
    )
    with pytest.raises(RateLimitError):
        client.get_balance()
    assert route.call_count == 1
    client.close()


async def test_async_429_retried(
    openssh_pem: str, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    async with AsyncCNGN(
        api_key=API_KEY, encryption_key=ENCRYPTION_KEY, private_key=openssh_pem
    ) as client:

        async def _no_sleep(delay: float) -> None:
            pass

        client._sleep = _no_sleep
        route = router.get("/balance").mock(
            side_effect=[
                httpx.Response(
                    429,
                    json={"status": 429, "message": "Too many requests. Please try again later."},
                ),
                httpx.Response(200, json=success_payload([], ed25519_seed)),
            ]
        )
        assert await client.get_balance() == []
        assert route.call_count == 2
