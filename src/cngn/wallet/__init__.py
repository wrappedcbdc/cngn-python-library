"""Optional HD wallet helpers for cNGN-supported networks.

Requires the ``wallet`` extra: ``pip install cngn[wallet]``
(mnemonic, bip32utils, tronpy, stellar-sdk). These heavy dependencies are
imported lazily inside this package only; the core SDK never touches them.
"""

from ._hd import GeneratedWallet, Network, generate_wallet_address, validate_address

__all__ = ["GeneratedWallet", "Network", "generate_wallet_address", "validate_address"]
