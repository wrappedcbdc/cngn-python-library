from .CryptoWallet import CryptoWallet

class WalletManager:

    def generate_wallet_address(self, network: str) -> str:
        response =  CryptoWallet.generate_wallet_with_mnemonic_details(network)
        return {
            "success": True,
            "data": response
        }

    def validate_address(self, address, network):
        return CryptoWallet.validate_address(address, network)
