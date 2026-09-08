"""Asynchronous front-end for the cNGN API."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Literal

import httpx

from . import _endpoints as ep
from ._client import (
    DEFAULT_BASE_URL,
    ClientConfig,
    Environment,
    PreparedRequest,
    compute_retry_delay,
    handle_response,
    is_retryable,
    prepare_request,
    resolve_config,
)
from ._exceptions import CNGNError, NetworkError
from ._models import (
    AccountVerification,
    Balance,
    Bank,
    BridgeQuote,
    BridgeResult,
    Network,
    RedeemResult,
    TemporaryAccount,
    Transaction,
    TransactionPage,
    VirtualAccount,
    WhitelistEntry,
    WithdrawResult,
)


class AsyncCNGN:
    """Asynchronous cNGN API client; same surface as :class:`CNGN`.

    See :class:`CNGN` for parameter documentation.
    """

    def __init__(
        self,
        api_key: str,
        encryption_key: str,
        private_key: str,
        *,
        environment: Literal["test", "live"] | Environment | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_cap: float = 30.0,
    ) -> None:
        self._config: ClientConfig = resolve_config(
            api_key,
            encryption_key,
            private_key,
            environment=environment,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            backoff_base=backoff_base,
            backoff_cap=backoff_cap,
        )
        self._http = httpx.AsyncClient(timeout=timeout, headers=self._config.headers)

    @property
    def environment(self) -> Environment:
        return self._config.environment

    async def __aenter__(self) -> AsyncCNGN:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _sleep(self, delay: float) -> None:
        await asyncio.sleep(delay)

    async def _send_once(self, prepared: PreparedRequest) -> Any:
        response = await self._http.request(
            prepared.method,
            prepared.url,
            params=prepared.query,
            json=prepared.json_body,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {"status": response.status_code, "message": response.text}
        if not isinstance(payload, dict):
            payload = {"status": response.status_code, "message": str(payload)}
        return handle_response(response.status_code, payload, prepared, self._config)

    async def _request(self, endpoint: ep.Endpoint, **kwargs: Any) -> Any:
        prepared = prepare_request(endpoint, self._config, **kwargs)
        attempt = 0
        last_error: BaseException | None = None
        while True:
            last_error = None
            try:
                return await self._send_once(prepared)
            except httpx.HTTPError as exc:
                last_error = NetworkError(f"Transport error: {exc}", cause=exc)
            except CNGNError as exc:
                last_error = exc
                if not is_retryable(exc.status, exc):
                    raise
            attempt += 1
            if attempt > self._config.max_retries:
                raise last_error
            await self._sleep(compute_retry_delay(attempt, self._config, last_error))

    async def get_balance(self) -> list[Balance]:
        """List cNGN balances across asset types."""
        return await self._request(ep.GET_BALANCE)

    async def get_transactions(self, page: int = 1, limit: int = 10) -> TransactionPage:
        """Fetch one page of the transaction history."""
        return await self._request(ep.GET_TRANSACTIONS, page=page, limit=limit)

    async def iter_transactions(self, limit: int = 100) -> AsyncIterator[Transaction]:
        """Yield transactions across all pages, newest first.

        Each page is one API request; the API budget is 20 requests per
        60 seconds per key, so iterating thousands of transactions can hit
        the rate limit — the client retries 429s automatically after the
        60-second block.
        """
        page = 1
        while True:
            result: TransactionPage = await self._request(
                ep.GET_TRANSACTIONS, page=page, limit=limit
            )
            for transaction in result.data:
                yield transaction
            if result.pagination.is_last_page or not result.data:
                return
            page += 1

    async def get_networks(self, include_blockchain: bool = False) -> list[Network]:
        """List supported networks (optionally with blockchain metadata)."""
        return await self._request(ep.GET_NETWORKS, include_blockchain=include_blockchain)

    async def get_virtual_account(self) -> list[VirtualAccount]:
        """List the merchant's dedicated virtual accounts."""
        return await self._request(ep.GET_VIRTUAL_ACCOUNT)

    async def create_temporary_virtual_account(
        self,
        amount: float,
        customer_email: str,
        customer_name: str,
        account_name: str,
        narration: str | None = None,
    ) -> TemporaryAccount:
        """Create a temporary NGN virtual account (min 100 NGN)."""
        return await self._request(
            ep.CREATE_TEMPORARY_VIRTUAL_ACCOUNT,
            amount=amount,
            customer_email=customer_email,
            customer_name=customer_name,
            account_name=account_name,
            narration=narration,
        )

    async def redeem_asset(
        self,
        amount: float,
        bank_code: str,
        account_number: str,
        save_details: bool = False,
    ) -> RedeemResult:
        """Redeem cNGN to a Nigerian bank account (min 1; 10-digit account)."""
        return await self._request(
            ep.REDEEM_ASSET,
            amount=amount,
            bank_code=bank_code,
            account_number=account_number,
            save_details=save_details,
        )

    async def verify_bank_account(self, bank_code: str, account_number: str) -> AccountVerification:
        """Resolve the account name for a bank code + account number."""
        return await self._request(
            ep.VERIFY_BANK_ACCOUNT, bank_code=bank_code, account_number=account_number
        )

    async def get_banks(self) -> list[Bank]:
        """List Nigerian banks with their CBN codes."""
        return await self._request(ep.GET_BANKS)

    async def update_bank_account(
        self, bank_name: str, bank_account_name: str, bank_account_number: str
    ) -> Any:
        """Update the merchant's settlement bank account."""
        return await self._request(
            ep.UPDATE_BANK_ACCOUNT,
            bank_name=bank_name,
            bank_account_name=bank_account_name,
            bank_account_number=bank_account_number,
        )

    async def withdraw(
        self,
        amount: float,
        address: str,
        network_id: str,
        should_save_address: bool = False,
    ) -> WithdrawResult:
        """Withdraw cNGN to an external wallet address."""
        return await self._request(
            ep.WITHDRAW,
            amount=amount,
            address=address,
            network_id=network_id,
            should_save_address=should_save_address,
        )

    async def verify_withdrawal(self, trx_ref: str) -> Transaction:
        """Fetch the status and full record of a withdrawal."""
        return await self._request(ep.VERIFY_WITHDRAWAL, trx_ref=trx_ref)

    async def get_bridge_quote(
        self,
        amount: float,
        origin_network_id: str,
        destination_network_id: str,
        destination_address: str,
    ) -> BridgeQuote:
        """Quote a cross-network bridge transfer."""
        return await self._request(
            ep.GET_BRIDGE_QUOTE,
            amount=amount,
            origin_network_id=origin_network_id,
            destination_network_id=destination_network_id,
            destination_address=destination_address,
        )

    async def bridge(
        self,
        origin_network_id: str,
        destination_network_id: str,
        destination_address: str,
        sender_address: str | None = None,
        callback_url: str | None = None,
    ) -> BridgeResult:
        """Bridge cNGN from one network to another."""
        return await self._request(
            ep.BRIDGE,
            origin_network_id=origin_network_id,
            destination_network_id=destination_network_id,
            destination_address=destination_address,
            sender_address=sender_address,
            callback_url=callback_url,
        )

    async def whitelist_address(self, network_id: str, address: str) -> Any:
        """Whitelist a withdrawal address for a network."""
        return await self._request(ep.WHITELIST_ADDRESS, network_id=network_id, address=address)

    async def get_whitelisted_addresses(
        self, include_network: bool = False
    ) -> list[WhitelistEntry]:
        """List whitelisted withdrawal addresses."""
        return await self._request(ep.GET_WHITELISTED_ADDRESSES, include_network=include_network)
