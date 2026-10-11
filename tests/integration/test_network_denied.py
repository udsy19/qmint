"""Offline mode: network denied by default, cooperative check and socket-level guard."""

import socket

import pytest

from qmint.core.config import (
    NetworkDisabledError,
    PaidHardwareDisabledError,
    load_config,
    network_guard,
    require_network,
    require_paid_hardware,
)


def test_network_denied_by_default():
    cfg = load_config(env={})
    assert cfg.allow_network is False and cfg.allow_paid_hardware is False
    with pytest.raises(NetworkDisabledError):
        require_network(cfg, "zenodo fetch")
    with pytest.raises(PaidHardwareDisabledError):
        require_paid_hardware(cfg, "ionq job")


@pytest.mark.parametrize("raw,expected", [("1", True), ("true", True), ("0", False), ("no", False), ("", False)])
def test_network_flag_parsing(raw, expected):
    assert load_config(env={"QMINT_ALLOW_NETWORK": raw}).allow_network is expected


def test_garbage_flag_rejected():
    with pytest.raises(ValueError):
        load_config(env={"QMINT_ALLOW_NETWORK": "maybe"})


def test_offline_overrides_env():
    assert load_config(env={"QMINT_ALLOW_NETWORK": "1"}).offline().allow_network is False


def test_socket_guard_blocks_connections():
    with network_guard():
        with pytest.raises(NetworkDisabledError):
            socket.create_connection(("127.0.0.1", 9), timeout=0.1)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(NetworkDisabledError):
                s.connect(("127.0.0.1", 9))
        finally:
            s.close()
    assert socket.create_connection.__name__ == "create_connection"  # restored


def test_requests_blocked_in_guard():
    requests = pytest.importorskip("requests")
    with network_guard():
        with pytest.raises((NetworkDisabledError, requests.exceptions.ConnectionError)) as ei:
            requests.get("http://127.0.0.1:9/", timeout=0.1)
    assert "network access denied" in str(ei.value)
