"""Webhook signature verification and parsing tests."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from cngn import CNGNError, WebhookEvent, parse_webhook, verify_webhook_signature

SECRET = "whsec_test_secret"


def _signed_body(payload: dict) -> tuple[bytes, str]:
    raw = json.dumps(payload).encode()
    signature = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, f"sha256={signature}"


def test_valid_signature_verifies() -> None:
    raw, header = _signed_body({"event": "deposit.completed", "data": {}, "timestamp": "t"})
    assert verify_webhook_signature(raw, header, SECRET) is True


def test_tampered_body_fails() -> None:
    raw, header = _signed_body({"event": "deposit.completed", "data": {}, "timestamp": "t"})
    tampered = raw.replace(b"completed", b"received  ")
    assert verify_webhook_signature(tampered, header, SECRET) is False


def test_wrong_secret_fails() -> None:
    raw, header = _signed_body({"event": "x"})
    assert verify_webhook_signature(raw, header, "whsec_other") is False


def test_missing_header_returns_false() -> None:
    assert verify_webhook_signature(b"{}", None, SECRET) is False


def test_malformed_headers_return_false() -> None:
    raw, _ = _signed_body({"event": "x"})
    assert verify_webhook_signature(raw, "", SECRET) is False
    assert verify_webhook_signature(raw, "sha256=", SECRET) is False
    assert verify_webhook_signature(raw, "sha1=abcdef", SECRET) is False


def test_parse_webhook_round_trip() -> None:
    payload = {
        "event": "deposit.completed",
        "data": {
            "transactionId": "tx1",
            "trx_ref": "ref-1",
            "businessId": "biz-1",
            "initiatorId": "user-1",
            "status": "completed",
            "trx_type": "fiat_buy",
            "network": "ethereum",
            "base_trx_hash": "0xhash",
            "extl_trx_hash": None,
            "explorer_link": "https://etherscan.io/tx/0xhash",
            "amount": "150000.00",
            "asset_symbol": "CNGN",
            "receiver": {"address": "0xabc"},
            "reason": None,
            "occurredAt": "2024-01-01T00:00:00Z",
            "future_field": "kept",  # extra fields allowed
        },
        "timestamp": "2024-01-01T00:00:01Z",
    }
    raw, header = _signed_body(payload)
    assert verify_webhook_signature(raw, header, SECRET)
    event = parse_webhook(raw)
    assert isinstance(event, WebhookEvent)
    assert event.event == "deposit.completed"
    assert event.data.transaction_id == "tx1"
    assert event.data.amount == "150000.00"
    assert event.data.trx_type == "fiat_buy"
    assert event.data.occurred_at == "2024-01-01T00:00:00Z"
    assert event.data.model_extra["future_field"] == "kept"


def test_parse_webhook_rejects_bad_json() -> None:
    with pytest.raises(CNGNError, match="not valid JSON"):
        parse_webhook(b"not json")


def test_parse_webhook_rejects_bad_envelope() -> None:
    with pytest.raises(CNGNError, match="expected envelope"):
        parse_webhook(b'{"data": 42}')
