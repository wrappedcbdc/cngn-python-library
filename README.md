# cngn

Official Python SDK for the [cNGN API](https://docs.cngn.co).

## Install

```bash
pip install cngn
```

Use `pip install "cngn[wallet]"` to include wallet helpers.

## Usage

```python
from cngn import CNGN

with CNGN(
    api_key="cngn_test_...",
    encryption_key="...",
    private_key=open("cngn_ed25519").read(),
) as client:
    print(client.get_balance())
```

Use `AsyncCNGN` for async applications. Manage API keys, encryption keys,
Ed25519 keys, and IP allowlisting at [app.cngn.co](https://app.cngn.co).

## Links

- [Documentation](https://docs.cngn.co)
- [PyPI](https://pypi.org/project/cngn/)
- [License](LICENSE)
