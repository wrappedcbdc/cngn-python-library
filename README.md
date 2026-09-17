# cngn

Official Python SDK for the [cNGN API](https://docs.cngn.co), the regulated Nigerian Naira stablecoin. Async-first, with a synchronous client exposing the same surface. Requires Python 3.10+.

## Install

```bash
pip install cngn
```

or `uv add cngn`. For the optional HD wallet helpers, install `cngn[wallet]`.

## Credentials

Create and manage credentials at [app.cngn.co](https://app.cngn.co). Three pieces are required:

1. API key, prefixed `cngn_test_` or `cngn_live_`. The environment is inferred from the prefix, and test and live credentials are separate.
2. Encryption key, from the same dashboard page.
3. An unencrypted OpenSSH Ed25519 private key that you generate with `ssh-keygen -t ed25519` and register the `.pub` half on the dashboard. The SDK uses it to decrypt API responses locally, so the private key stays inside your process.

## Quickstart

```python
import asyncio

from cngn import AsyncCNGN


async def main() -> None:
    async with AsyncCNGN(
        api_key="cngn_test_...",
        encryption_key="...",
        private_key=open("cngn_ed25519").read(),
    ) as client:
        print(await client.get_balance())
        print(await client.get_transactions(page=1, limit=10))


asyncio.run(main())
```

For synchronous code, use `CNGN` with the same methods:

```python
from cngn import CNGN

with CNGN(api_key=..., encryption_key=..., private_key=...) as client:
    print(client.get_balance())
```

## Common operations

```python
# Onramp: temporary NGN virtual account, deposits auto-convert to cNGN
account = await client.create_temporary_virtual_account(
    amount=5000,
    customer_email="user@example.com",
    customer_name="Ada Obi",
    account_name="ACME Checkout",
)

# Offramp: redeem cNGN to a bank account
verification = await client.verify_bank_account(bank_code="058", account_number="0123456789")
result = await client.redeem_asset(amount=1000, bank_code="058", account_number="0123456789")

# On-chain: withdraw to a whitelisted address
await client.whitelist_address(network_id="...", address="0x...")
withdrawal = await client.withdraw(amount=250, address="0x...", network_id="...")
status = await client.verify_withdrawal(withdrawal.trx_ref)

# Cross-network bridge
quote = await client.get_bridge_quote(
    amount=250,
    origin_network_id="...",
    destination_network_id="...",
    destination_address="0x...",
)
bridged = await client.bridge(
    origin_network_id="...",
    destination_network_id="...",
    destination_address="0x...",
)
```

## Idempotency

The money-moving methods (`create_temporary_virtual_account`, `redeem_asset`, `withdraw`, `bridge`) accept an `idempotency_key` that travels upstream as the `Idempotency-Key` header. Pass one for any call you might retry, so a retry carrying the same key executes once:

```python
await client.redeem_asset(
    amount=1000, bank_code="058", account_number="0123456789",
    idempotency_key="order-1234-redeem",
)
```

A client-level default can be set with `AsyncCNGN(..., idempotency_key=...)`.

## Webhooks

```python
from cngn import parse_webhook, verify_webhook_signature

if not verify_webhook_signature(raw_body, headers.get("X-cNGN-Signature"), signing_secret):
    raise Forbidden()
event = parse_webhook(raw_body)
```

## Errors

Every API failure raises a subclass of `CNGNError`. Credential and access problems surface as `AuthenticationError`, `IPWhitelistError` (caller IP missing from the dashboard allowlist) or `PermissionDeniedError`. Request problems surface as `ValidationError`, whose `field_errors` maps fields to messages, and `TransactionNotFoundError` for unknown references. `RateLimitError` carries a `retry_after` in seconds. Crypto mismatches raise `EncryptionError` or `DecryptionError`, upstream outages raise `ServiceUnavailableError`, transport failures raise `NetworkError`, and anything else raises `APIError`.

The client retries idempotent requests automatically with exponential backoff, tunable through the `max_retries`, `backoff_base` and `backoff_cap` constructor parameters.

## Wallet helpers

With the `wallet` extra installed:

```python
from cngn.wallet import Network, generate_wallet_address, validate_address

wallet = generate_wallet_address(Network.BSC)
ok = validate_address(Network.TRON, "T...")
```

API docs live at <https://docs.cngn.co>, the dashboard at <https://app.cngn.co>, and the source at <https://github.com/wrappedcbdc/cngn-python-library>.
