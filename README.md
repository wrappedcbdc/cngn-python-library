# cngn

Official Python SDK for the [cNGN API](https://docs.cngn.co).

## Install

```bash
pip install cngn
```

Use `pip install "cngn[wallet]"` to include wallet helpers.

## Async usage

```python
import asyncio

from cngn import AsyncCNGN


async def main() -> None:
    async with AsyncCNGN(
        api_key="cngn_test_...",
        encryption_key="...",
        private_key=open("cngn_ed25519").read(),
    ) as client:
        balances = await client.get_balance()
        networks = await client.get_networks()
        print(balances, networks)


asyncio.run(main())
```

`AsyncCNGN` is recommended for applications and services. Use `CNGN` for
synchronous code; it exposes the same methods without `await`.

## Features

- Balances and paginated transactions
- Dedicated and temporary virtual accounts
- Bank verification and cNGN redemption
- On-chain withdrawals and address whitelisting
- Cross-network quotes and bridges
- Webhook signature verification
- Optional wallet generation and validation

```python
account = await client.create_temporary_virtual_account(
    amount=5000,
    customer_email="user@example.com",
    customer_name="Ada Obi",
    account_name="ACME Checkout",
)

quote = await client.get_bridge_quote(
    amount=250,
    origin_network_id="...",
    destination_network_id="...",
    destination_address="0x...",
)
```

Manage API keys, encryption keys, Ed25519 keys, and IP allowlisting at
[app.cngn.co](https://app.cngn.co). Test and live credentials are separate.
