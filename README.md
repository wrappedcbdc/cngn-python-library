# cngn-python-library

CNGnManager is a Python library for interacting with a CNGN API. It provides a simple interface for various operations such as checking balance, swapping between chains, depositing for redemption, creating virtual accounts, and more.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Available Methods](#available-methods)
- [Testing](#testing)
- [Error Handling](#error-handling)
- [Types](#types)
- [Security](#security)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

## Installation

To install CNGnManager and its dependencies, run:

```bash
pip install cngn-manager
```

## Usage

First, import the `CNGnManager` class using it namespace WrappedCBDC\CNGNManager: and all necessary constants.

```python
from cngn_manager import CNGnManager, Network, ProviderType
```

Then, create an instance of `CNGnManager` with your secrets:

```python
import os

api_key = "cngn_live_sk**********"
encryption_key = "yourencryptionkey"
ssh_private_key = """-----BEGIN OPENSSH PRIVATE KEY-----
your ssh key
-----END OPENSSH PRIVATE KEY-----"""

# NOTE: You can also get your private key from a file using
# ssh_private_key = os.open("/path/to/sshkey.key").read()

manager = CNGnManager(api_key, ssh_private_key, encryption_key)
# Example: Get balance
balance = manager.get_balance()
print(balance)
```

## Available Methods

### Get Balance

```python
balance = manager.get_balance()
print(balance)
```

### Get Transaction History

```python
transactions = manager.get_transaction_history()
print(transactions)

```

### Swap Between Chains

```python
swap_params = {
    "amount": 100,
    "address": "0x1234...",
    "network": Network.BSC
}

swap_result = manager.swap_between_chains(swap_params)
print(swap_result)

```

### Deposit for Redemption

```python
deposit_params = {
    "amount": 1000,
    "bank": "Example Bank",
    "accountNumber": "1234567890"
}

deposit_result = manager.deposit_for_redemption(deposit_params)
print(deposit_result)

```

### Create Virtual Account

```python
mint_params = {
    "provider": ProviderType.KORAPAY
}

virtual_account = manager.create_virtual_account(mint_params)
print(virtual_account)

```

### Whitelist Address

```python
whitelist_params = {
    "bscAddress": "0x1234...",
    "bankName": "Example Bank",
    "bankAccountNumber": "1234567890"
}

whitelist_result = manager.whitelist_address(whitelist_params)
print(whitelist_result)

```

## Testing

This project uses Jest for testing. To run the tests, follow these steps:

1. Run the test command:

```bash
python3 -m unittest discover tests
```

This will run all tests in the `tests` directory.

### Test Structure

The tests are located in the `tests` directory. They cover various aspects of the CNGnManager class, including:

- API calls for different endpoints (GET and POST requests)
- Encryption and decryption of data
- Error handling for various scenarios


## Error Handling

The library uses a custom error handling mechanism. All API errors are caught and thrown as `Error` objects with descriptive messages.

## Types

The library includes python definitions for all parameters and return types. Please refer to the type definitions in the source code for more details.

## Security

This library uses AES encryption for request payloads and Ed25519 decryption for response data. Ensure that your `encryptionKey` and `privateKey` are kept secure.

## Contributing

Contributions, issues, and feature requests are welcome. Feel free to check [issues page](https://github.com/wrappedcbdc/cngn-python-library/issues) if you want to contribute.

## Support

If you have any questions or need help using the library, please open an issue in the GitHub repository.

## License

[MIT](https://choosealicense.com/licenses/mit/)
