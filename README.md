# cngn-python-library

CNGnManager is a Python library for interacting with a CNGN API. It provides a simple interface for various operations such as checking balance, swapping between chains, depositing for redemption, creating virtual accounts, and more.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Available Methods](#available-methods)
    - [cNGNManager Methods](#cngnmanager-methods)
    - [WalletManager Methods](#walletmanager-methods)
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

First, import the `CNGnManager` `WalletManager` class using and all necessary constants.

```python
from cngn_manager import CNGnManager, WalletManager, Network, ProviderType, AssetType
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

## Networks

The library supports multiple blockchain networks:

- `Network.BSC` - Binance Smart Chain
- `Network.ATC` - Asset Chain
- `Network.XBN` - Bantu Chain
- `Network.ETTH` - Ethereum
- `Network.MATIC` - Polygon (Matic)
- `Network.TRX` - Tron
- `Network.BASE` - Base

## Available Methods

### cNGNManager Methods

#### Get Balance

```python
balance = manager.get_balance()
print(balance)
```

#### Get Transaction History

```python
page = 1
limit = 10
transactions = manager.get_transaction_history(page, limit)
print(transactions)

```

#### Withdraw from chains

```python
withdraw_params = {
    "amount": 100,
    "address": "0x1234...",
    "network": Network.BSC,
    "shouldSaveAddress": True
}

withdraw_result = manager.withdraw(withdraw_params)
print(withdraw_result)

```

#### Redeem Asset

```python
deposit_params = {
    "amount": 1000,
    "bankCode": "123",
    "accountNumber": "1234567890",
    "saveDetails": True
}

deposit_result = manager.redeem_assets(deposit_params)
print(deposit_result)

```

NOTE: to get bank codes please use the getBanks method to fetch the list of banks and ther codes 

#### Create Virtual Account

```python
mint_params = {
    "provider": ProviderType.KORAPAY,
    "bank_code": '011'
}

virtual_account = manager.create_virtual_account(mint_params)
print(virtual_account)

```
NOTE: before creating the virtual account you need to have updated your BVN on the dashboard

#### Swap Asset

```python
swap_data = {
    "destinationNetwork": Network.BSC,
    "destinationAddress": '0x123...',
    "originNetwork": Network.ETH,
    "callbackUrl": 'https://your-callback-url.com' // optional
}

swap_result = manager.swap_asset(swap_data)
print(swap_result)

```
NOTE: before creating the virtual account you need to have updated your BVN on the dashboard


#### Update Business

Address Options:
- "xbnAddress": "string";
- "bscAddress": "string";
- "atcAddress": "string";
- "polygonAddress": "string";
- "ethAddress": "string";
- "tronAddress": "string";
- "baseAddress": "string";
- "bantuUserId": "string";

```python

updateData  = {
    "walletAddress": {
        "bscAddress": "0x1234...",
        #other chain addresses...
    },
    "bankDetails": {
        "bankName": 'Test Bank',
        "bankAccountName": 'Test Account',
        "bankAccountNumber": '1234567890'
    }
}

updateResult = manager.update_external_accounts(updateData)
print(updateResult)

```

#### Get banks
```python

banklist = manager.get_banks()
print(banklist)

```


### WalletManager Methods

#### Generate Wallet Address
```python
    wallet = WalletManager.generate_wallet_address(Network.bsc);
```

Response format:
```python
 {
    "mnemonic" : "string";
    "address": "string";
    "network": Network;
    "privateKey": "string";
}
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

## Constants

The library includes python constant classes for all parameters:

- `Network` - token network
- `AssetType` - Asset constants
- `ProviderType` - provider constants

## Security

- Uses AES encryption for request data
- Implements Ed25519 decryption for responses
- Requires secure storage of API credentials

## Contributing

To contribute:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Create a Pull Request

## Support

For support, please:
- Open an issue in the GitHub repository
- Check existing documentation
- Contact the support team

## License

[MIT](https://choosealicense.com/licenses/mit/)
