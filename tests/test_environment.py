"""Environment inference and mismatch tests."""

from __future__ import annotations

import pytest

from cngn import CNGN, AsyncCNGN, CNGNError, Environment, EnvironmentMismatchError
from conftest import ENCRYPTION_KEY


def test_infers_test_environment(openssh_pem: str) -> None:
    client = CNGN(api_key="cngn_test_abc", encryption_key=ENCRYPTION_KEY, private_key=openssh_pem)
    assert client.environment is Environment.TEST
    client.close()


def test_infers_live_environment(openssh_pem: str) -> None:
    client = CNGN(api_key="cngn_live_abc", encryption_key=ENCRYPTION_KEY, private_key=openssh_pem)
    assert client.environment is Environment.LIVE
    client.close()


def test_unknown_prefix_raises(openssh_pem: str) -> None:
    with pytest.raises(CNGNError, match="Cannot infer environment"):
        CNGN(api_key="sk_something", encryption_key=ENCRYPTION_KEY, private_key=openssh_pem)


def test_test_key_with_live_environment_raises_before_http(openssh_pem: str) -> None:
    with pytest.raises(EnvironmentMismatchError) as exc_info:
        CNGN(
            api_key="cngn_test_abc",
            encryption_key=ENCRYPTION_KEY,
            private_key=openssh_pem,
            environment="live",
        )
    # raised in the constructor, before any HTTP client exists
    assert isinstance(exc_info.value, ValueError)


def test_live_key_with_test_environment_raises(openssh_pem: str) -> None:
    with pytest.raises(EnvironmentMismatchError):
        AsyncCNGN(
            api_key="cngn_live_abc",
            encryption_key=ENCRYPTION_KEY,
            private_key=openssh_pem,
            environment="test",
        )


def test_matching_explicit_environment_ok(openssh_pem: str) -> None:
    client = CNGN(
        api_key="cngn_test_abc",
        encryption_key=ENCRYPTION_KEY,
        private_key=openssh_pem,
        environment=Environment.TEST,
    )
    assert client.environment is Environment.TEST
    client.close()
