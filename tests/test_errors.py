"""Error-mapping tests: every documented message lands on the right exception."""

from __future__ import annotations

import httpx
import pytest
import respx

from cngn import (
    CNGN,
    APIError,
    AuthenticationError,
    DecryptionError,
    EncryptionError,
    IPWhitelistError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    TransactionNotFoundError,
    ValidationError,
)
from conftest import API_KEY, ENCRYPTION_KEY


@pytest.fixture()
def client(openssh_pem: str, router: respx.MockRouter) -> CNGN:
    c = CNGN(api_key=API_KEY, encryption_key=ENCRYPTION_KEY, private_key=openssh_pem)
    c._sleep = lambda delay: None  # don't actually wait out retry delays
    yield c
    c.close()


def _mock(
    router: respx.MockRouter,
    status: int,
    payload: dict,
    method: str = "get",
    path: str = "/balance",
) -> respx.Route:
    return getattr(router, method)(path).mock(return_value=httpx.Response(status, json=payload))


@pytest.mark.parametrize(
    ("http_status", "message", "exception"),
    [
        (400, "No token provided", AuthenticationError),
        (400, "Invalid token prefix", AuthenticationError),
        (400, "Merchant not found", AuthenticationError),
        (404, "Merchant not found", AuthenticationError),
        (400, "No Test SSH Key found", AuthenticationError),
        (400, "No Live SSH Key found", AuthenticationError),
        (403, "IP address not whitelisted", IPWhitelistError),
        (403, "Could not determine client IP address", IPWhitelistError),
        (400, "Missing encryption data, key, or IV", EncryptionError),
        (400, "Decryption failed", DecryptionError),
        (400, "Transaction not found", TransactionNotFoundError),
    ],
)
def test_documented_error_messages(
    client: CNGN,
    router: respx.MockRouter,
    http_status: int,
    message: str,
    exception: type[Exception],
) -> None:
    _mock(router, http_status, {"status": http_status, "message": message})
    with pytest.raises(exception) as exc_info:
        client.get_balance()
    assert exc_info.value.message == message


def test_permission_denied_names_permission(client: CNGN, router: respx.MockRouter) -> None:
    _mock(
        router,
        403,
        {"status": False, "message": "Permission denied"},
        method="post",
        path="/redeemAsset",
    )
    with pytest.raises(PermissionDeniedError) as exc_info:
        client.redeem_asset(amount=5, bank_code="058", account_number="0123456789")
    assert exc_info.value.permission == "Redeem"
    assert "Redeem" in str(exc_info.value)


@pytest.mark.parametrize(
    ("path", "permission"),
    [
        ("/virtual-account", "Fiat Deposit"),
        ("/withdraw", "Send Crypto"),
        ("/bridge", "Swap"),
    ],
)
def test_permission_denied_per_endpoint(
    client: CNGN, router: respx.MockRouter, path: str, permission: str
) -> None:
    _mock(router, 403, {"status": 403, "message": "Permission denied"}, path=path)
    from cngn._client import _permission_for

    assert _permission_for(path) == permission


def test_permission_denied_unknown_endpoint(client: CNGN, router: respx.MockRouter) -> None:
    _mock(router, 403, {"status": 403, "message": "Permission denied"})
    with pytest.raises(PermissionDeniedError) as exc_info:
        client.get_balance()
    assert exc_info.value.permission is None


def test_rate_limit_error(client: CNGN, router: respx.MockRouter) -> None:
    _mock(router, 429, {"status": 429, "message": "Too many requests. Please try again later."})
    with pytest.raises(RateLimitError) as exc_info:
        client.get_balance()
    assert exc_info.value.retry_after == 60.0


def test_validation_error_field_parsing(client: CNGN, router: respx.MockRouter) -> None:
    message = "amount: Number must be greater than or equal to 1"
    _mock(router, 400, {"status": 400, "message": message}, method="post", path="/redeemAsset")
    with pytest.raises(ValidationError) as exc_info:
        client.redeem_asset(amount=0, bank_code="058", account_number="0123456789")
    assert exc_info.value.field_errors == {"amount": "Number must be greater than or equal to 1"}


def test_service_unavailable_retry_exhaustion(client: CNGN, router: respx.MockRouter) -> None:
    message = "Service is currently unavailable. Please try again later."
    route = _mock(router, 400, {"status": 400, "message": message})
    with pytest.raises(ServiceUnavailableError):
        client.get_balance()
    assert route.call_count == 1 + 3  # retried up to max_retries


def test_undocumented_error_is_api_error(client: CNGN, router: respx.MockRouter) -> None:
    _mock(router, 400, {"status": 400, "message": "Something entirely new"})
    with pytest.raises(APIError) as exc_info:
        client.get_balance()
    assert exc_info.value.status == 400


def test_non_json_error_body(client: CNGN, router: respx.MockRouter) -> None:
    router.get("/balance").mock(return_value=httpx.Response(400, text="<html>bad</html>"))
    with pytest.raises(APIError) as exc_info:
        client.get_balance()
    assert "bad" in exc_info.value.message


def test_error_carries_response_payload(client: CNGN, router: respx.MockRouter) -> None:
    payload = {"status": 400, "message": "No token provided"}
    _mock(router, 400, payload)
    with pytest.raises(AuthenticationError) as exc_info:
        client.get_balance()
    assert exc_info.value.response == payload
    assert exc_info.value.status == 400
