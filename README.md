# cngn-manager (cNGN Python SDK)

The official Python SDK for the [cNGN API](https://docs.cngn.co) — cNGN is a
regulated Nigerian Naira stablecoin from Wrapped CBDC.

- Sync (`CNGN`) and async (`AsyncCNGN`) clients over a single shared pipeline.
- Automatic request encryption (AES-256-CBC) and response decryption (NaCl Box).
- Typed pydantic models for every resource; amounts stay strings exactly as the
  API returns them (no float conversion, no precision loss).
- Environment inferred from the API-key prefix — test credentials can never
  touch production.
- Automatic retries for rate limits (429), transient outages and 5xx errors.
- Framework-agnostic webhook signature verification.
- Optional `[wallet]` extra for HD wallet generation/validation.

Requires Python 3.10+.

## Installation

```bash
pip install cngn-manager
# with the optional HD wallet helpers:
pip install "cngn-manager[wallet]"
```

## Getting credentials

1. Log in to the [cNGN merchant dashboard](https://dashboard.cngn.co) and open
   **Settings → API Key** tab.
2. Generate an API key. Sandbox keys are prefixed `cngn_test_`, production keys
   `cngn_live_`; each environment has its own key, encryption key and SSH key —
   credentials never cross environments.
3. Copy the environment's **encryption key** from the same tab.
4. Generate an Ed25519 keypair (unencrypted private key):

   ```bash
   ssh-keygen -t ed25519 -f cngn_test_key -N ""
   ```

5. Upload the **public** key (`cngn_test_key.pub`) to the dashboard for that
   environment. Repeat per environment with separate keys.
6. Whitelist your server's source IP address on the dashboard, or every call
   fails with `403 "IP address not whitelisted"`.

## Quickstart (sync)

```python
from cngn import CNGN

with CNGN(
    api_key="cngn_test_...",
    encryption_key="...",
    private_key=open("cngn_test_key").read(),  # OpenSSH PEM
) as client:
    print(client.get_balance()[0].balance)  # "150000.00"

    page = client.get_transactions(page=1, limit=10)
    for tx in page.data:
        print(tx.trx_ref, tx.amount, tx.status)

    account = client.create_temporary_virtual_account(
        amount=5000,
        customer_email="user@example.com",
        customer_name="Ada Lovelace",
        account_name="CNGN/ACME",
        narration="invoice-42",
    )
    print(account.account_number, account.bank_name, account.expires_at)
```

## Quickstart (async)

```python
import asyncio

from cngn import AsyncCNGN


async def main() -> None:
    async with AsyncCNGN(
        api_key="cngn_test_...",
        encryption_key="...",
        private_key=open("cngn_test_key").read(),
    ) as client:
        balances = await client.get_balance()
        async for tx in client.iter_transactions(limit=100):
            print(tx.id)


asyncio.run(main())
```

## Environments

One base URL serves both environments; the API key prefix selects the
environment. The SDK infers it from the key and refuses cross-environment
mistakes before any HTTP call:

```python
from cngn import CNGN, EnvironmentMismatchError

CNGN(api_key="cngn_test_...", encryption_key="...", private_key=pem, environment="live")
# raises EnvironmentMismatchError immediately
```

## Error handling

Every API failure raises a subclass of `cngn.CNGNError`; nothing is swallowed
into `{"success": False}` dicts.

```python
from cngn import CNGN, CNGNError, PermissionDeniedError, RateLimitError, ValidationError

try:
    client.redeem_asset(amount=100, bank_code="058", account_number="0123456789")
except ValidationError as exc:
    print(exc.field_errors)  # {"amount": "Number must be greater than or equal to 1"}
except PermissionDeniedError as exc:
    print(exc.permission)  # "Redeem" — enable it on the dashboard
except RateLimitError as exc:
    print(exc.retry_after)  # 60 — the key is blocked for a minute
except CNGNError as exc:
    print(exc.status, exc.message)
```

The hierarchy: `AuthenticationError`, `IPWhitelistError`, `PermissionDeniedError`,
`RateLimitError`, `ValidationError`, `EncryptionError`, `DecryptionError`,
`ServiceUnavailableError`, `TransactionNotFoundError`, `NetworkError`,
`EnvironmentMismatchError`, `APIError` — all subclass `CNGNError`.

## Webhooks

cNGN signs webhooks with `X-cNGN-Signature: sha256=<hex>` — an HMAC-SHA256 of
the **raw** request body keyed with your dashboard signing secret. Payloads are
unsigned when no secret is configured. Always capture the raw body before any
JSON parsing; the SDK verifies bytes in, boolean out.

```python
from cngn import parse_webhook, verify_webhook_signature

# Flask:    raw = request.get_data()
# FastAPI:  raw = await request.body()

if not verify_webhook_signature(raw, request.headers.get("X-cNGN-Signature"), secret):
    return "invalid signature", 401

event = parse_webhook(raw)
match event.event:
    case "deposit.completed":
        credit_user(event.data.transaction_id, event.data.amount)
    case "redemption.completed" | "withdrawal.completed":
        mark_settled(event.data.trx_ref)
    case "transaction.failed":
        flag(event.data.trx_ref, event.data.reason)
```

Events: `deposit.received`, `deposit.completed`, `redemption.completed`,
`withdrawal.completed`, `transaction.failed`.

## Rate limits

The API allows **20 requests per 60 seconds per API key**. Exceeding it blocks
the key for 60 seconds (`429 "Too many requests. Please try again later."`).
The client retries 429s automatically after the block, and 5xx/transient errors
with exponential backoff (`max_retries`, `backoff_base`, `backoff_cap` are
constructor options). Other 4xx errors are never retried blindly — money-moving
endpoints should be reconciled explicitly after a failure.

To stay under the limit, cache slow-changing resources:

```python
banks = client.get_banks()  # cache for the process lifetime
networks = client.get_networks()  # cache likewise
```

## Wallet helpers (optional extra)

```python
from cngn.wallet import Network, generate_wallet_address, validate_address

wallet = generate_wallet_address(Network.BASE)  # EVM path m/44'/60'/0'/0/0
validate_address(wallet.address, Network.BASE)  # True
```

Ethereum, Base, BSC and Polygon share the EVM derivation path; Tron derives at
`m/44'/195'/0'/0/0` and Stellar follows SEP-0005. The heavy wallet dependencies
(`mnemonic`, `bip32utils`, `tronpy`, `stellar-sdk`) are only installed with the
`[wallet]` extra and only imported inside `cngn.wallet`.

## Migrating from v1

v2 is a ground-up rewrite. Highlights:

- `import cngn_manager` → `import cngn` (package name on PyPI is unchanged:
  `pip install cngn-manager`).
- Errors are now **raised** as typed exceptions instead of returned as
  `{"success": False}` dicts.
- Wallet helpers moved to the optional `[wallet]` extra; `Network.BASE` now
  works.
- One base URL with environment inferred from the key prefix (no hardcoded
  production URL).
- Encrypted OpenSSH private keys are rejected with a clear error; keys are
  parsed structurally, not by marker slicing.
- All requests have timeouts and automatic retries.

Method renames:

| v1 (`cngn_manager`)       | v2 (`cngn`)                            |
|---------------------------|----------------------------------------|
| `get_balance`             | `get_balance`                          |
| `get_transaction_history` | `get_transactions` (+`iter_transactions`) |
| `withdraw`                | `withdraw`                             |
| `verify_withdrawal`       | `verify_withdrawal`                    |
| `redeem_assets`           | `redeem_asset`                         |
| `create_virtual_account`  | `create_temporary_virtual_account`     |
| `update_external_accounts`| `update_bank_account`                  |
| `get_banks`               | `get_banks`                            |
| `swap_asset`              | `bridge`                               |
| `swap_quote`              | `get_bridge_quote`                     |

## Changelog

### 2.0.0

- Complete rewrite: sync + async clients over one shared pipeline.
- Environment inference from API-key prefix with `EnvironmentMismatchError`.
- Structural OpenSSH key parsing; encrypted keys rejected explicitly.
- Typed exception hierarchy replacing `{"success": False}` dicts.
- Fixed the malformed `?page{page}` pagination parameter.
- Timeouts, retries (429/5xx/transport) with configurable backoff.
- Pydantic v2 models; amounts preserved as strings; extra fields tolerated.
- Webhook signature verification (`verify_webhook_signature`) and parsing.
- Wallet helpers isolated behind the `[wallet]` extra; Base network supported.
- Removed bogus `hashlib` PyPI dependency and undeclared transitive imports.

## License

MIT — © Wrapped CBDC / Convexity.
