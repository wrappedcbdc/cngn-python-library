"""Shared request pipeline for the sync and async clients.

Holds every step except the actual transport: environment resolution,
parameter building, body encryption, response decryption, error mapping
and retry-delay computation. Both front-ends call into this module, so
no endpoint logic is duplicated.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from . import _endpoints as ep
from ._crypto import aes_encrypt, decrypt_response_data, derive_aes_key
from ._exceptions import (
    PERMISSION_BY_PATH,
    APIError,
    AuthenticationError,
    CNGNError,
    DecryptionError,
    EncryptionError,
    EnvironmentMismatchError,
    IPWhitelistError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    TransactionNotFoundError,
    ValidationError,
)

DEFAULT_BASE_URL = "https://api.cngn.co/v1/api"
_TEST_PREFIX = "cngn_test_"
_LIVE_PREFIX = "cngn_live_"
_FIELD_ERROR_RE = re.compile(r"^([A-Za-z_][\w.]*)\s*:\s+(.+)$")


class Environment(str, Enum):
    """API environment. Selected automatically from the API-key prefix."""

    TEST = "test"
    LIVE = "live"

    @classmethod
    def from_api_key(cls, api_key: str) -> Environment:
        if api_key.startswith(_TEST_PREFIX):
            return cls.TEST
        if api_key.startswith(_LIVE_PREFIX):
            return cls.LIVE
        raise CNGNError(
            "Cannot infer environment from API key: expected a "
            f"'{_TEST_PREFIX}*' or '{_LIVE_PREFIX}*' prefix; pass "
            "environment= explicitly only with a properly prefixed key"
        )


@dataclass(frozen=True)
class ClientConfig:
    api_key: str
    encryption_key: str
    private_key: str
    environment: Environment
    base_url: str
    timeout: float
    max_retries: int
    backoff_base: float
    backoff_cap: float

    @property
    def aes_key(self) -> bytes:
        return derive_aes_key(self.encryption_key)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }


def resolve_config(
    api_key: str,
    encryption_key: str,
    private_key: str,
    *,
    environment: Literal["test", "live"] | Environment | None,
    base_url: str,
    timeout: float,
    max_retries: int,
    backoff_base: float,
    backoff_cap: float,
) -> ClientConfig:
    inferred = Environment.from_api_key(api_key)
    if environment is None:
        resolved = inferred
    else:
        resolved = Environment(environment)
        if resolved is not inferred:
            raise EnvironmentMismatchError(
                f"API key is a '{inferred.value}' key but environment='{environment}' was "
                "passed; credentials never cross environments"
            )
    return ClientConfig(
        api_key=api_key,
        encryption_key=encryption_key,
        private_key=private_key,
        environment=resolved,
        base_url=base_url.rstrip("/"),
        timeout=timeout,
        max_retries=max_retries,
        backoff_base=backoff_base,
        backoff_cap=backoff_cap,
    )


@dataclass(frozen=True)
class PreparedRequest:
    method: str
    url: str
    path: str
    query: dict[str, Any] | None
    json_body: dict[str, str] | None
    parser: Callable[[Any], Any]


def prepare_request(endpoint: ep.Endpoint, config: ClientConfig, **kwargs: Any) -> PreparedRequest:
    """Build params → encrypt the body if present → produce a wire request."""
    path = endpoint.path.format(
        **{k: kwargs.pop(k) for k in list(kwargs) if f"{{{k}}}" in endpoint.path}
    )
    params = endpoint.builder(**kwargs)
    url = f"{config.base_url}{path}"
    if endpoint.method == "GET":
        return PreparedRequest(endpoint.method, url, path, params, None, endpoint.parser)
    plaintext = json.dumps(params or {}).encode()
    envelope = aes_encrypt(plaintext, config.aes_key)
    return PreparedRequest(endpoint.method, url, path, None, envelope, endpoint.parser)


def compute_retry_delay(attempt: int, config: ClientConfig, error: BaseException | None) -> float:
    """Delay before retry ``attempt`` (1-based); 429 waits out the 60s block."""
    if isinstance(error, RateLimitError):
        return error.retry_after
    return min(config.backoff_base * (2 ** (attempt - 1)), config.backoff_cap)


def is_retryable(http_status: int | None, error: BaseException | None) -> bool:
    """Retry 429 (after the block), 5xx and transport errors; never other 4xx."""
    if isinstance(error, RateLimitError | ServiceUnavailableError):
        return True
    if isinstance(error, CNGNError):
        return http_status is not None and http_status >= 500
    return error is not None  # transport-level error


def parse_success(
    payload: dict[str, Any], parser: Callable[[Any], Any], config: ClientConfig
) -> Any:
    """Decrypt ``data`` if present, then hand it to the endpoint parser."""
    data = payload.get("data")
    if isinstance(data, str):
        decrypted = decrypt_response_data(data, config.private_key)
        return parser(decrypted)
    return parser(data)


def _permission_for(path: str) -> str | None:
    for prefix, permission in PERMISSION_BY_PATH:
        if path.startswith(prefix):
            return permission
    return None


def _status_code(http_status: int, payload: dict[str, Any] | None) -> int:
    raw = (payload or {}).get("status")
    return raw if isinstance(raw, int) else http_status


def raise_for_error(
    http_status: int,
    payload: dict[str, Any] | None,
    path: str,
    raw_text: str = "",
) -> None:
    """Map a non-success API response onto the exception hierarchy."""
    payload = payload or {}
    message = str(payload.get("message") or raw_text or f"HTTP {http_status}")
    status = _status_code(http_status, payload)
    permission_denied = payload.get("status") is False and "permission denied" in message.lower()

    if http_status == 429 or "too many requests" in message.lower():
        raise RateLimitError(message, retry_after=60.0, status=status, response=payload)
    if permission_denied or message.strip().lower() == "permission denied":
        raise PermissionDeniedError(
            message, permission=_permission_for(path), status=status, response=payload
        )
    if message == "No token provided":
        raise AuthenticationError(message, status=status, response=payload)
    if message == "Invalid token prefix":
        raise AuthenticationError(message, status=status, response=payload)
    if message == "Merchant not found":
        raise AuthenticationError(message, status=status, response=payload)
    if message in ("No Test SSH Key found", "No Live SSH Key found"):
        raise AuthenticationError(message, status=status, response=payload)
    if message == "IP address not whitelisted":
        raise IPWhitelistError(message, status=status, response=payload)
    if message == "Could not determine client IP address":
        raise IPWhitelistError(message, status=status, response=payload)
    if message == "Missing encryption data, key, or IV":
        raise EncryptionError(message, status=status, response=payload)
    if message == "Decryption failed":
        raise DecryptionError(message, status=status, response=payload)
    if message == "Service is currently unavailable. Please try again later.":
        raise ServiceUnavailableError(message, status=status, response=payload)
    if message == "Transaction not found":
        raise TransactionNotFoundError(message, status=status, response=payload)

    field_match = _FIELD_ERROR_RE.match(message)
    if field_match and http_status == 400:
        field, detail = field_match.group(1), field_match.group(2)
        raise ValidationError(
            message, field_errors={field: detail}, status=status, response=payload
        )
    if http_status >= 500:
        raise APIError(message, status=status, response=payload)
    raise APIError(message, status=status, response=payload)


def handle_response(
    http_status: int,
    payload: dict[str, Any],
    prepared: PreparedRequest,
    config: ClientConfig,
) -> Any:
    """Full response handling: error mapping, then decrypt + parse on success."""
    status = _status_code(http_status, payload)
    ok = 200 <= http_status < 300 and status == 200 and payload.get("status") is not False
    if not ok:
        raise_for_error(http_status, payload, prepared.path)
    return parse_success(payload, prepared.parser, config)


__all__ = [
    "DEFAULT_BASE_URL",
    "ClientConfig",
    "Environment",
    "PreparedRequest",
    "compute_retry_delay",
    "handle_response",
    "is_retryable",
    "prepare_request",
    "resolve_config",
]
