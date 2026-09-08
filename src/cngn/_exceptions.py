"""Exception hierarchy for the cNGN SDK.

Every API failure raises a subclass of :class:`CNGNError`; nothing is
swallowed into ``{"success": False}`` dicts as in v1.
"""

from __future__ import annotations

from typing import Any

# Endpoint path prefix -> dashboard permission name, used to enrich
# PermissionDeniedError when the API only says "Permission denied".
PERMISSION_BY_PATH: tuple[tuple[str, str], ...] = (
    ("/virtual-account", "Fiat Deposit"),
    ("/redeemAsset", "Redeem"),
    ("/withdraw", "Send Crypto"),
    ("/bridge", "Swap"),
)


class CNGNError(Exception):
    """Base error for all cNGN SDK failures.

    Carries the HTTP ``status`` code, the API ``message`` and the raw
    ``response`` payload when they are available.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.response = response


class AuthenticationError(CNGNError):
    """The API key is missing, malformed, or unknown to the platform."""


class IPWhitelistError(CNGNError):
    """The request source IP is not whitelisted on the dashboard."""


class PermissionDeniedError(CNGNError):
    """The API key lacks the dashboard permission required for this endpoint.

    ``permission`` names the dashboard permission when it can be derived
    from the endpoint (e.g. ``"Redeem"`` for ``/redeemAsset``).
    """

    def __init__(
        self,
        message: str,
        *,
        permission: str | None = None,
        status: int | None = None,
        response: dict[str, Any] | None = None,
    ) -> None:
        if permission:
            message = f"{message} (requires the '{permission}' permission)"
        super().__init__(message, status=status, response=response)
        self.permission = permission


class RateLimitError(CNGNError):
    """Rate limit exceeded; the key is blocked for ``retry_after`` seconds."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: float = 60.0,
        status: int | None = None,
        response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status=status, response=response)
        self.retry_after = retry_after


class ValidationError(CNGNError):
    """A request field failed server-side validation.

    ``field_errors`` maps field names to messages when the API returned
    ``"field: message"``-shaped errors.
    """

    def __init__(
        self,
        message: str,
        *,
        field_errors: dict[str, str] | None = None,
        status: int | None = None,
        response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status=status, response=response)
        self.field_errors = field_errors or {}


class EncryptionError(CNGNError):
    """The request body could not be encrypted, or the API rejected it."""


class DecryptionError(CNGNError):
    """The API response could not be decrypted with the configured key."""


class ServiceUnavailableError(CNGNError):
    """The API reported a transient outage; safe to retry after a pause."""


class TransactionNotFoundError(CNGNError):
    """The referenced transaction does not exist."""


class NetworkError(CNGNError):
    """A transport-level failure (DNS, connect, timeout) occurred."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        response: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, status=status, response=response)
        self.cause = cause


class EnvironmentMismatchError(CNGNError, ValueError):
    """The explicit ``environment`` contradicts the API-key prefix."""


class APIError(CNGNError):
    """An undocumented error response from the API."""
