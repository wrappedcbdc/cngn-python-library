"""Model parsing: DecimalString coerces JSON numbers to decimal strings."""

from __future__ import annotations

from cngn._models import BridgeQuote, TemporaryAccount, Transaction


def test_temporary_account_accepts_numeric_amounts() -> None:
    """The temporary-account endpoint returns amounts as JSON numbers."""
    account = TemporaryAccount.model_validate(
        {
            "reference": "ref-1",
            "amount": 1500,
            "amountExpected": 1500,
            "fee": 0,
            "vat": 0,
            "accountNumber": "0123456789",
            "bankName": "Test Bank",
        }
    )
    assert account.amount == "1500"
    assert account.amount_expected == "1500"
    assert account.fee == "0"
    assert account.vat == "0"


def test_decimal_string_keeps_strings_and_precision() -> None:
    account = TemporaryAccount.model_validate(
        {"amount": "1500.50", "amountExpected": "1500.50", "fee": "7.25", "vat": "0.54"}
    )
    assert account.amount == "1500.50"
    assert account.fee == "7.25"
    transaction = Transaction.model_validate({"amount": "1000000.00"})
    assert transaction.amount == "1000000.00"


def test_decimal_string_coerces_floats_without_artifacts() -> None:
    quote = BridgeQuote.model_validate(
        {"amountReceivable": 99.5, "networkFee": 1, "bridgeFee": 0.25}
    )
    assert quote.amount_receivable == "99.5"
    assert quote.network_fee == "1"
    assert quote.bridge_fee == "0.25"


def test_decimal_string_passes_none_and_rejects_bool() -> None:
    assert TemporaryAccount.model_validate({}).amount is None
    import pytest

    with pytest.raises(Exception):  # noqa: B017 - must not coerce True to "1"
        Transaction.model_validate({"amount": True})
