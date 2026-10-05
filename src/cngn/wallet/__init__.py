"""Optional HD wallet helpers for cNGN-supported networks.

Requires the ``wallet`` extra: ``pip install cngn[wallet]``.
Wallet dependencies are loaded when this package is imported.
"""

from ._hd import GeneratedWallet, Network, generate_wallet_address, validate_address

__all__ = ["GeneratedWallet", "Network", "generate_wallet_address", "validate_address"]
