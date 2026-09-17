"""Async client tests: same core coverage as the sync suite."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from cngn import AsyncCNGN
from conftest import (
    API_KEY,
    ENCRYPTION_KEY,
    decrypt_request,
    success_payload,
)


@pytest.fixture()
async def client(openssh_pem: str, router: respx.MockRouter) -> AsyncCNGN:
    async with AsyncCNGN(
        api_key=API_KEY, encryption_key=ENCRYPTION_KEY, private_key=openssh_pem
    ) as c:
        yield c


async def test_get_balance(
    client: AsyncCNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    data = [{"asset_type": "credit_alphanum4", "asset_code": "CNGN", "balance": "150000.00"}]
    route = router.get("/balance").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    balances = await client.get_balance()
    assert route.called
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert balances[0].balance == "150000.00"


async def test_per_call_idempotency_key_on_money_endpoints(
    client: AsyncCNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    temporary = router.post("/virtual-account/temporary").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    redeem = router.post("/redeemAsset").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    withdraw = router.post("/withdraw").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    bridge = router.post("/bridge").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    await client.create_temporary_virtual_account(
        amount=1000,
        customer_email="user@example.com",
        customer_name="Test User",
        account_name="CNGN/ACME",
        idempotency_key="key-temporary",
    )
    await client.redeem_asset(
        amount=100, bank_code="058", account_number="0123456789", idempotency_key="key-redeem"
    )
    await client.withdraw(
        amount=10, address="0xabc", network_id="n1", idempotency_key="key-withdraw"
    )
    await client.bridge("n1", "n2", "0xabc", idempotency_key="key-bridge")
    assert temporary.calls.last.request.headers["Idempotency-Key"] == "key-temporary"
    assert redeem.calls.last.request.headers["Idempotency-Key"] == "key-redeem"
    assert withdraw.calls.last.request.headers["Idempotency-Key"] == "key-withdraw"
    assert bridge.calls.last.request.headers["Idempotency-Key"] == "key-bridge"


async def test_constructor_idempotency_key_not_leaked_to_other_endpoints(
    openssh_pem: str, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    balance = router.get("/balance").mock(
        return_value=httpx.Response(200, json=success_payload([], ed25519_seed))
    )
    verify = router.post("/account/verify").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    update = router.put("/bank-account").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    quote = router.post("/bridge-quote").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    async with AsyncCNGN(
        api_key=API_KEY,
        encryption_key=ENCRYPTION_KEY,
        private_key=openssh_pem,
        idempotency_key="operation-123",
    ) as client:
        await client.get_balance()
        await client.verify_bank_account(bank_code="058", account_number="0123456789")
        await client.update_bank_account("GTBank", "ACME LTD", "0123456789")
        await client.get_bridge_quote(10, "n1", "n2", "0xabc")

    for route in (balance, verify, update, quote):
        assert "Idempotency-Key" not in route.calls.last.request.headers


async def test_constructor_default_used_and_per_call_overrides(
    openssh_pem: str, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    route = router.post("/withdraw").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    async with AsyncCNGN(
        api_key=API_KEY,
        encryption_key=ENCRYPTION_KEY,
        private_key=openssh_pem,
        idempotency_key="default-key",
    ) as client:
        await client.withdraw(amount=10, address="0xabc", network_id="n1")
        assert route.calls.last.request.headers["Idempotency-Key"] == "default-key"
        await client.withdraw(
            amount=10, address="0xabc", network_id="n1", idempotency_key="call-key"
        )
        assert route.calls.last.request.headers["Idempotency-Key"] == "call-key"


async def test_no_idempotency_key_sends_no_header(
    client: AsyncCNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    route = router.post("/withdraw").mock(
        return_value=httpx.Response(200, json=success_payload({}, ed25519_seed))
    )
    await client.withdraw(amount=10, address="0xabc", network_id="n1")
    assert "Idempotency-Key" not in route.calls.last.request.headers


async def test_retried_money_call_reuses_idempotency_key(
    openssh_pem: str, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    route = router.post("/withdraw").mock(
        side_effect=[
            httpx.Response(500, json={"status": 500, "message": "boom"}),
            httpx.Response(200, json=success_payload({"trxRef": "wd-1"}, ed25519_seed)),
        ]
    )
    async with AsyncCNGN(
        api_key=API_KEY, encryption_key=ENCRYPTION_KEY, private_key=openssh_pem
    ) as client:

        async def _no_sleep(delay: float) -> None:
            pass

        client._sleep = _no_sleep
        await client.withdraw(
            amount=10, address="0xabc", network_id="n1", idempotency_key="retry-key"
        )

    assert route.call_count == 2
    sent = [call.request.headers["Idempotency-Key"] for call in route.calls]
    assert sent == ["retry-key", "retry-key"]


async def test_get_transactions(
    client: AsyncCNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    data = {
        "data": [{"id": "tx1", "trx_ref": "r1", "status": "success"}],
        "pagination": {
            "count": 1,
            "pages": 1,
            "isLastPage": True,
            "nextPage": None,
            "previousPage": None,
        },
    }
    route = router.get("/transactions").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    page = await client.get_transactions(page=2, limit=20)
    url = route.calls.last.request.url
    assert url.params["page"] == "2" and url.params["limit"] == "20"
    assert page.data[0].id == "tx1"
    assert page.pagination.is_last_page


async def test_iter_transactions(
    client: AsyncCNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    def payload(num: int, is_last: bool) -> dict:
        return {
            "data": [{"id": f"tx{num}"}],
            "pagination": {
                "count": 2,
                "pages": 2,
                "isLastPage": is_last,
                "nextPage": None if is_last else num + 1,
                "previousPage": None,
            },
        }

    router.get("/transactions").mock(
        side_effect=[
            httpx.Response(200, json=success_payload(payload(1, False), ed25519_seed)),
            httpx.Response(200, json=success_payload(payload(2, True), ed25519_seed)),
        ]
    )
    ids = [t.id async for t in client.iter_transactions(limit=100)]
    assert ids == ["tx1", "tx2"]


async def test_create_temporary_virtual_account(
    client: AsyncCNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    data = {"reference": "ref", "accountNumber": "9876543210", "status": "pending"}
    route = router.post("/virtual-account/temporary").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    account = await client.create_temporary_virtual_account(
        amount=1000,
        customer_email="user@example.com",
        customer_name="Test User",
        account_name="CNGN/ACME",
        narration="n",
    )
    request = route.calls.last.request
    assert json.loads(request.content)["content"]
    params = decrypt_request(json.loads(request.content), aes_key)
    assert params["customer"] == {"email": "user@example.com", "name": "Test User"}
    assert account.account_number == "9876543210"


async def test_withdraw(
    client: AsyncCNGN, router: respx.MockRouter, ed25519_seed: bytes, aes_key: bytes
) -> None:
    data = {"trxRef": "wd-1", "address": "0xabc"}
    route = router.post("/withdraw").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    result = await client.withdraw(amount=10, address="0xabc", network_id="n1")
    params = decrypt_request(json.loads(route.calls.last.request.content), aes_key)
    assert params["shouldSaveAddress"] is False
    assert result.trx_ref == "wd-1"


async def test_verify_withdrawal(
    client: AsyncCNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    data = {"id": "tx1", "status": "pending", "trx_type": "withdrawal"}
    route = router.get("/withdraw/verify/wd-1").mock(
        return_value=httpx.Response(200, json=success_payload(data, ed25519_seed))
    )
    result = await client.verify_withdrawal("wd-1")
    assert route.called
    assert result.status == "pending"


async def test_bridge_and_quote(
    client: AsyncCNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    router.post("/bridge-quote").mock(
        return_value=httpx.Response(
            200,
            json=success_payload(
                {"amountReceivable": "9", "networkFee": "0.5", "bridgeFee": "0.5"},
                ed25519_seed,
            ),
        )
    )
    router.post("/bridge").mock(
        return_value=httpx.Response(
            200,
            json=success_payload(
                {"receivableAddress": "0xr", "transactionId": "t", "reference": "b"},
                ed25519_seed,
            ),
        )
    )
    quote = await client.get_bridge_quote(10, "n1", "n2", "0xabc")
    assert quote.bridge_fee == "0.5"
    result = await client.bridge("n1", "n2", "0xabc")
    assert result.receivable_address == "0xr"


async def test_get_networks_and_whitelist(
    client: AsyncCNGN, router: respx.MockRouter, ed25519_seed: bytes
) -> None:
    router.get("/networks").mock(
        return_value=httpx.Response(
            200,
            json=success_payload([{"id": "n1", "name": "Base"}], ed25519_seed),
        )
    )
    networks = await client.get_networks(include_blockchain=True)
    assert networks[0].name == "Base"

    router.get("/whitelisted").mock(
        return_value=httpx.Response(
            200, json=success_payload([{"id": "w1", "publicKey": "0xabc"}], ed25519_seed)
        )
    )
    entries = await client.get_whitelisted_addresses()
    assert entries[0].id == "w1"


async def test_context_manager_closes(openssh_pem: str) -> None:
    async with AsyncCNGN(
        api_key=API_KEY, encryption_key=ENCRYPTION_KEY, private_key=openssh_pem
    ) as c:
        http = c._http
    assert http.is_closed
