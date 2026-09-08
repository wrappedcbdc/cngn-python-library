"""Endpoint definitions shared by the sync and async clients.

Each endpoint is declared exactly once: HTTP method, path, a request
builder producing the plaintext parameter payload, and a parser that
turns the decrypted ``data`` value into typed models.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import _models as m


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    builder: Callable[..., dict[str, Any] | None]
    parser: Callable[[Any], Any]


def _no_body() -> None:
    return None


def _get(
    path: str, parser: Callable[[Any], Any], builder: Callable[..., Any] = _no_body
) -> Endpoint:
    return Endpoint("GET", path, builder, parser)


def _post(
    path: str, builder: Callable[..., dict[str, Any]], parser: Callable[[Any], Any]
) -> Endpoint:
    return Endpoint("POST", path, builder, parser)


def _parse_list(model: type[m.CNGNModel]) -> Callable[[Any], Any]:
    def parse(data: Any) -> Any:
        if data is None:
            return []
        return [model.model_validate(item) for item in data]

    return parse


def _parse_one(model: type[m.CNGNModel]) -> Callable[[Any], Any]:
    def parse(data: Any) -> Any:
        return model.model_validate(data if data is not None else {})

    return parse


def _raw(data: Any) -> Any:
    return data


GET_BALANCE = _get("/balance", _parse_list(m.Balance))

GET_TRANSACTIONS = _get(
    "/transactions",
    _parse_one(m.TransactionPage),
    builder=lambda page, limit: {"page": page, "limit": limit},
)

GET_NETWORKS = _get(
    "/networks",
    _parse_list(m.Network),
    builder=lambda include_blockchain: (
        {"includeBlockchain": "true"} if include_blockchain else None
    ),
)

GET_VIRTUAL_ACCOUNT = _get("/virtual-account", _parse_list(m.VirtualAccount))

CREATE_TEMPORARY_VIRTUAL_ACCOUNT = _post(
    "/virtual-account/temporary",
    lambda amount, customer_email, customer_name, account_name, narration=None: {
        "amount": amount,
        "customer": {"email": customer_email, "name": customer_name},
        "accountName": account_name,
        **({"narration": narration} if narration is not None else {}),
    },
    _parse_one(m.TemporaryAccount),
)

REDEEM_ASSET = _post(
    "/redeemAsset",
    lambda amount, bank_code, account_number, save_details=False: {
        "amount": amount,
        "bankCode": bank_code,
        "accountNumber": account_number,
        "saveDetails": save_details,
    },
    _parse_one(m.RedeemResult),
)

VERIFY_BANK_ACCOUNT = _post(
    "/account/verify",
    lambda bank_code, account_number: {
        "bankCode": bank_code,
        "accountNumber": account_number,
    },
    _parse_one(m.AccountVerification),
)

GET_BANKS = _get("/banks", _parse_list(m.Bank))

UPDATE_BANK_ACCOUNT = Endpoint(
    "PUT",
    "/bank-account",
    lambda bank_name, bank_account_name, bank_account_number: {
        "bankName": bank_name,
        "bankAccountName": bank_account_name,
        "bankAccountNumber": bank_account_number,
    },
    _raw,
)

WITHDRAW = _post(
    "/withdraw",
    lambda amount, address, network_id, should_save_address=False: {
        "amount": amount,
        "address": address,
        "networkId": network_id,
        "shouldSaveAddress": should_save_address,
    },
    _parse_one(m.WithdrawResult),
)

VERIFY_WITHDRAWAL = _get("/withdraw/verify/{trx_ref}", _parse_one(m.Transaction))

GET_BRIDGE_QUOTE = _post(
    "/bridge-quote",
    lambda amount, origin_network_id, destination_network_id, destination_address: {
        "amount": amount,
        "originNetworkId": origin_network_id,
        "destinationNetworkId": destination_network_id,
        "destinationAddress": destination_address,
    },
    _parse_one(m.BridgeQuote),
)


def _build_bridge(
    origin_network_id: str,
    destination_network_id: str,
    destination_address: str,
    sender_address: str | None = None,
    callback_url: str | None = None,
) -> dict[str, Any]:
    return {
        "originNetworkId": origin_network_id,
        "destinationNetworkId": destination_network_id,
        "destinationAddress": destination_address,
        **({"senderAddress": sender_address} if sender_address is not None else {}),
        **({"callbackUrl": callback_url} if callback_url is not None else {}),
    }


BRIDGE = _post("/bridge", _build_bridge, _parse_one(m.BridgeResult))

WHITELIST_ADDRESS = _post(
    "/whitelist",
    lambda network_id, address: {"networkId": network_id, "address": address},
    _raw,
)

GET_WHITELISTED_ADDRESSES = _get(
    "/whitelisted",
    _parse_list(m.WhitelistEntry),
    builder=lambda include_network: {"includeNetwork": "true"} if include_network else None,
)
