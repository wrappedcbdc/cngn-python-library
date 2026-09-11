"""Webhook signature verification and payload parsing.

cNGN signs webhooks with ``X-cNGN-Signature: sha256=<hex>``, an
HMAC-SHA256 of the raw request body keyed with the dashboard signing
secret. The SDK only verifies — merchants receive webhooks on their own
infrastructure. Always capture the raw body (Flask: ``request.get_data()``,
FastAPI: ``await request.body()``) before parsing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from ._exceptions import CNGNError
from ._models import CNGNModel

_SIGNATURE_PREFIX = "sha256="


class WebhookData(CNGNModel):
    transaction_id: str | None = Field(default=None, alias="transactionId")
    trx_ref: str | None = None
    business_id: str | None = Field(default=None, alias="businessId")
    initiator_id: str | None = Field(default=None, alias="initiatorId")
    status: str | None = None
    trx_type: str | None = None
    network: str | None = None
    base_trx_hash: str | None = None
    extl_trx_hash: str | None = None
    explorer_link: str | None = None
    amount: str | None = None
    asset_symbol: str | None = None
    receiver: dict[str, Any] | str | None = None
    reason: str | None = None
    occurred_at: str | None = Field(default=None, alias="occurredAt")


class WebhookEvent(CNGNModel):
    event: str
    data: WebhookData
    timestamp: str | None = None


def verify_webhook_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    """Verify the ``X-cNGN-Signature`` header against the raw request body.

    Returns False when the header is missing or malformed — never raises.
    Payloads are unsigned when no signing secret is configured on the
    dashboard; in that case this check cannot be performed.
    """
    if not signature_header or not signature_header.startswith(_SIGNATURE_PREFIX):
        return False
    expected_hex = signature_header[len(_SIGNATURE_PREFIX) :].strip()
    if not expected_hex:
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected_hex)


def parse_webhook(raw_body: bytes) -> WebhookEvent:
    """Parse a raw webhook body into a :class:`WebhookEvent`.

    Verify the signature with :func:`verify_webhook_signature` first.
    """
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CNGNError(f"Webhook body is not valid JSON: {exc}") from exc
    try:
        return WebhookEvent.model_validate(payload)
    except PydanticValidationError as exc:
        raise CNGNError(f"Webhook payload does not match the expected envelope: {exc}") from exc
