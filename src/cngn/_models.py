"""Pydantic v2 models for cNGN API resources.

All models allow extra fields so new API fields never break parsing.
Amounts are kept as strings exactly as the API returns them; no float
conversion is performed, preserving decimal precision.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CNGNModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Balance(CNGNModel):
    asset_type: str = ""
    asset_code: str = ""
    balance: str = "0"


class Receiver(CNGNModel):
    address: str | None = None
    bank: str | None = None
    account_number: str | None = Field(default=None, alias="accountNumber")


class Transaction(CNGNModel):
    id: str | None = None
    from_: str | None = Field(default=None, alias="from")
    receiver: Receiver | dict[str, Any] | str | None = None
    amount: str | None = None
    description: str | None = None
    created_at: str | None = Field(default=None, alias="createdAt")
    trx_ref: str | None = None
    trx_type: str | None = None
    network: str | None = None
    asset_type: str | None = None
    asset_symbol: str | None = None
    base_trx_hash: str | None = None
    extl_trx_hash: str | None = None
    explorer_link: str | None = None
    status: str | None = None


class Pagination(CNGNModel):
    count: int = 0
    pages: int = 0
    is_last_page: bool = Field(default=True, alias="isLastPage")
    next_page: int | None = Field(default=None, alias="nextPage")
    previous_page: int | None = Field(default=None, alias="previousPage")


class TransactionPage(CNGNModel):
    data: list[Transaction] = Field(default_factory=list)
    pagination: Pagination = Field(default_factory=Pagination)


class Network(CNGNModel):
    id: str | None = None
    name: str | None = None
    short_name: str | None = None
    is_disabled: bool | None = Field(default=None, alias="isDisabled")
    blockchain: str | None = None


class VirtualAccount(CNGNModel):
    account_number: str = Field(default="", alias="accountNumber")
    account_name: str = Field(default="", alias="accountName")
    bank_name: str = Field(default="", alias="bankName")
    bank_code: str = Field(default="", alias="bankCode")


class TemporaryAccount(CNGNModel):
    reference: str | None = None
    payment_reference: str | None = Field(default=None, alias="paymentReference")
    amount: str | None = None
    amount_expected: str | None = Field(default=None, alias="amountExpected")
    fee: str | None = None
    vat: str | None = None
    currency: str | None = None
    status: str | None = None
    narration: str | None = None
    account_number: str | None = Field(default=None, alias="accountNumber")
    account_name: str | None = Field(default=None, alias="accountName")
    bank_name: str | None = Field(default=None, alias="bankName")
    bank_code: str | None = Field(default=None, alias="bankCode")
    expires_at: str | None = Field(default=None, alias="expiresAt")


class Bank(CNGNModel):
    name: str | None = None
    code: str | None = None
    bank_code: str | None = Field(default=None, alias="bankCode")


class RedeemResult(CNGNModel):
    trx_ref: str | None = Field(default=None, alias="trxRef")
    address: str | None = None


class WithdrawResult(CNGNModel):
    trx_ref: str | None = Field(default=None, alias="trxRef")
    address: str | None = None


class AccountVerification(CNGNModel):
    account_name: str | None = Field(default=None, alias="accountName")
    account_number: str | None = Field(default=None, alias="accountNumber")
    bank_code: str | None = Field(default=None, alias="bankCode")


class BridgeQuote(CNGNModel):
    amount_receivable: str | None = Field(default=None, alias="amountReceivable")
    network_fee: str | None = Field(default=None, alias="networkFee")
    bridge_fee: str | None = Field(default=None, alias="bridgeFee")


class BridgeResult(CNGNModel):
    receivable_address: str | None = Field(default=None, alias="receivableAddress")
    transaction_id: str | None = Field(default=None, alias="transactionId")
    reference: str | None = None


class WhitelistEntry(CNGNModel):
    id: str | None = None
    network_id: str | None = Field(default=None, alias="networkId")
    public_key: str | None = Field(default=None, alias="publicKey")
    internal_public_key: str | None = Field(default=None, alias="internalPublicKey")
    network: str | dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None
