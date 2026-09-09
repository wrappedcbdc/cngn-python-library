"""Sync client tests: every endpoint hits the right method+path, sends the
right decrypted params, carries the Bearer header, and parses into models."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx

from cngn import CNGN, Transaction
from conftest import (
    API_KEY,
    BASE_URL,
    ENCRYPTION_KEY,
    decrypt_request,
    success_payload,
)


@pytest.fixture()
def client(openssh_pem: str, router: respx.MockRouter) -> CNGN:
    with CNGN(api_key=API_KEY, encryption_key=ENCRYPTION_KEY, private_key=openssh_pem) as c:
        yield c


def _request_body(route: respx.Route) -> dict[str, str]:
    assert route.calls, "expected the route to be called"
    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert request.headers["Content-Type"] == "application/json"
    if not request.content:
        return {}  # GET requests send no body
    return json.loads(request.content)


def _decrypted_params(route: respx.Route, aes_key: bytes) -> dict:
    return decrypt_request(_request_body(route), aes_key)


def test_get_balance(client: CNGN, router: respx.MockRouter, ed25519_seed: bytes) -> None:
    data = [{"asset_type": "credit_alphanum4", "asset_code": "CNGN", "balance": "150000.00"}]
    route = router.get("/balance").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    balances = client.get_balance()
    assert route.called
    assert balances[0].asset_code == "CNGN"
    assert balances[0].balance == "150000.00"  # amounts stay strings
    _request_body(route)  # header assertion; GET sends no encrypted body


def test_get_transactions_pagination_well_formed(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    tx = {
        "id": "tx1",
        "from": "addr",
        "receiver": {"address": "0xabc"},
        "amount": "250.5",
        "description": "test",
        "createdAt": "2024-01-01T00:00:00Z",
        "trx_ref": "ref-1",
        "trx_type": "deposit",
        "network": "ethereum",
        "asset_type": "credit_alphanum4",
        "asset_symbol": "CNGN",
        "base_trx_hash": "0xhash",
        "extl_trx_hash": None,
        "explorer_link": "https://etherscan.io/tx/0xhash",
        "status": "success",
    }
    data = {
        "data": [tx],
        "pagination": {
            "count": 1,
            "pages": 5,
            "isLastPage": False,
            "nextPage": 3,
            "previousPage": 1,
        },
    }
    route = router.get("/transactions").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    page = client.get_transactions(page=2, limit=20)
    assert route.called
    url = route.calls.last.request.url
    assert url.params["page"] == "2" and url.params["limit"] == "20"
    assert str(url) == f"{BASE_URL}/transactions?page=2&limit=20"
    assert page.data[0].trx_ref == "ref-1"
    assert page.data[0].from_ == "addr"
    assert page.data[0].amount == "250.5"
    assert page.pagination.pages == 5
    assert page.pagination.next_page == 3


def test_iter_transactions_walks_pages(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    def page_payload(num: int, is_last: bool) -> dict:
        return {
            "data": [
                {"id": f"tx{num}a", "status": "success"},
                {"id": f"tx{num}b", "status": "pending"},
            ],
            "pagination": {
                "count": 4,
                "pages": 2,
                "isLastPage": is_last,
                "nextPage": None if is_last else num + 1,
                "previousPage": None if num == 1 else num - 1,
            },
        }

    router.get("/transactions").mock(
        side_effect=[
            httpx.Response(200, json=success_payload(page_payload(1, False), ed25519_seed)),
            httpx.Response(200, json=success_payload(page_payload(2, True), ed25519_seed)),
        ]
    )
    transactions = list(client.iter_transactions(limit=100))
    assert [t.id for t in transactions] == ["tx1a", "tx1b", "tx2a", "tx2b"]
    assert all(isinstance(t, Transaction) for t in transactions)


def test_get_networks(client: CNGN, router: respx.MockRouter, ed25519_seed: bytes) -> None:
    data = [{"id": "n1", "name": "Ethereum", "short_name": "ETH", "isDisabled": False}]
    route = router.get("/networks").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    networks = client.get_networks()
    assert "includeBlockchain" not in route.calls.last.request.url.params
    assert networks[0].short_name == "ETH"

    route_with = router.get("/networks").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    client.get_networks(include_blockchain=True)
    assert route_with.calls.last.request.url.params["includeBlockchain"] == "true"


def test_get_virtual_account(client: CNGN, router: respx.MockRouter, ed25519_seed: bytes) -> None:
    data = [
        {
            "accountNumber": "1234567890",
            "accountName": "ACME LTD",
            "bankName": "Providus Bank",
            "bankCode": "101",
        }
    ]
    router.get("/virtual-account").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    accounts = client.get_virtual_account()
    assert accounts[0].account_number == "1234567890"
    assert accounts[0].bank_code == "101"


def test_create_temporary_virtual_account(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    data = {
        "reference": "ref",
        "paymentReference": "payref",
        "amount": "5000",
        "amountExpected": "5000",
        "fee": "50",
        "vat": "3.75",
        "currency": "NGN",
        "status": "pending",
        "narration": "order-123",
        "accountNumber": "9876543210",
        "accountName": "CNGN/ACME",
        "bankName": "Providus Bank",
        "bankCode": "101",
        "expiresAt": "2024-01-01T01:00:00Z",
    }
    route = router.post("/virtual-account/temporary").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    account = client.create_temporary_virtual_account(
        amount=5000,
        customer_email="user@example.com",
        customer_name="Test User",
        account_name="CNGN/ACME",
        narration="order-123",
    )
    params = _decrypted_params(route, aes_key)
    assert params == {
        "amount": 5000,
        "customer": {"email": "user@example.com", "name": "Test User"},
        "accountName": "CNGN/ACME",
        "narration": "order-123",
    }
    assert account.payment_reference == "payref"
    assert account.currency == "NGN"


def test_create_temporary_virtual_account_omits_narration(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    route = router.post("/virtual-account/temporary").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    client.create_temporary_virtual_account(
        amount=100,
        customer_email="user@example.com",
        customer_name="Test User",
        account_name="CNGN/ACME",
    )
    assert "narration" not in _decrypted_params(route, aes_key)


def test_redeem_asset(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    data = {"trxRef": "redeem-1", "address": "0xdef"}
    route = router.post("/redeemAsset").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    result = client.redeem_asset(amount=100, bank_code="058", account_number="0123456789")
    assert _decrypted_params(route, aes_key) == {
        "amount": 100,
        "bankCode": "058",
        "accountNumber": "0123456789",
        "saveDetails": False,
    }
    assert result.trx_ref == "redeem-1"


def test_verify_bank_account(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    data = {"accountName": "JOHN DOE", "accountNumber": "0123456789", "bankCode": "058"}
    route = router.post("/account/verify").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    result = client.verify_bank_account(bank_code="058", account_number="0123456789")
    assert _decrypted_params(route, aes_key) == {
        "bankCode": "058",
        "accountNumber": "0123456789",
    }
    assert result.account_name == "JOHN DOE"


def test_get_banks(client: CNGN, router: respx.MockRouter, ed25519_seed: bytes) -> None:
    data = [{"name": "GTBank", "code": "058"}, {"name": "Zenith", "code": "057"}]
    router.get("/banks").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    banks = client.get_banks()
    assert [b.code for b in banks] == ["058", "057"]


def test_update_bank_account_uses_put(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    route = router.put("/bank-account").mock(
        return_value=httpx.Response(200, json=success_payload({"ok": True}, ed25519_seed))
    )
    client.update_bank_account(
        bank_name="GTBank", bank_account_name="ACME LTD", bank_account_number="0123456789"
    )
    assert _decrypted_params(route, aes_key) == {
        "bankName": "GTBank",
        "bankAccountName": "ACME LTD",
        "bankAccountNumber": "0123456789",
    }


def test_withdraw(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    data = {"trxRef": "wd-1", "address": "0xabc"}
    route = router.post("/withdraw").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    result = client.withdraw(amount=50, address="0xabc", network_id="n1", should_save_address=True)
    assert _decrypted_params(route, aes_key) == {
        "amount": 50,
        "address": "0xabc",
        "networkId": "n1",
        "shouldSaveAddress": True,
    }
    assert result.address == "0xabc"


def test_verify_withdrawal(client: CNGN, router: respx.MockRouter, ed25519_seed: bytes) -> None:
    data = {"id": "tx1", "trx_ref": "wd-1", "status": "success", "trx_type": "withdrawal"}
    route = router.get("/withdraw/verify/wd-1").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    result = client.verify_withdrawal("wd-1")
    assert route.called
    assert result.status == "success"


def test_get_bridge_quote(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    data = {"amountReceivable": "99.0", "networkFee": "0.5", "bridgeFee": "0.5"}
    route = router.post("/bridge-quote").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    quote = client.get_bridge_quote(
        amount=100,
        origin_network_id="n1",
        destination_network_id="n2",
        destination_address="0xabc",
    )
    assert _decrypted_params(route, aes_key) == {
        "amount": 100,
        "originNetworkId": "n1",
        "destinationNetworkId": "n2",
        "destinationAddress": "0xabc",
    }
    assert quote.amount_receivable == "99.0"


def test_bridge(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    data = {"receivableAddress": "0xrecv", "transactionId": "tx9", "reference": "br-1"}
    route = router.post("/bridge").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    result = client.bridge(
        origin_network_id="n1",
        destination_network_id="n2",
        destination_address="0xabc",
        sender_address="0xsender",
        callback_url="https://example.com/cb",
    )
    assert _decrypted_params(route, aes_key) == {
        "originNetworkId": "n1",
        "destinationNetworkId": "n2",
        "destinationAddress": "0xabc",
        "senderAddress": "0xsender",
        "callbackUrl": "https://example.com/cb",
    }
    assert result.reference == "br-1"


def test_bridge_omits_optional_fields(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    route = router.post("/bridge").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    client.bridge(origin_network_id="n1", destination_network_id="n2", destination_address="0xabc")
    params = _decrypted_params(route, aes_key)
    assert "senderAddress" not in params and "callbackUrl" not in params


def test_whitelist_address(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    route = router.post("/whitelist").mock(
        return_value=httpx.Response(200, json=success_payload({"updated": True}, ed25519_seed))
    )
    client.whitelist_address(network_id="n1", address="0xabc")
    assert _decrypted_params(route, aes_key) == {"networkId": "n1", "address": "0xabc"}


def test_get_whitelisted_addresses(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    data = [
        {
            "id": "w1",
            "networkId": "n1",
            "publicKey": "0xabc",
            "internalPublicKey": "int-1",
            "network": {"name": "Ethereum"},
            "created_at": "2024-01-01",
            "updated_at": "2024-01-02",
        }
    ]
    route = router.get("/whitelisted").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    entries = client.get_whitelisted_addresses(include_network=True)
    assert route.calls.last.request.url.params["includeNetwork"] == "true"
    assert entries[0].public_key == "0xabc"


def test_encrypted_envelope_shape(
    client: CNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    route = router.post("/whitelist").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    client.whitelist_address(network_id="n1", address="0xabc")
    body = _request_body(route)
    assert set(body) == {"content", "iv"}
    assert len(base64.b64decode(body["iv"])) == 16


def test_context_manager_closes(openssh_pem: str) -> None:
    with CNGN(api_key=API_KEY, encryption_key=ENCRYPTION_KEY, private_key=openssh_pem) as c:
        http = c._http
    assert http.is_closed
