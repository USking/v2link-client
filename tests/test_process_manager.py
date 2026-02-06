from __future__ import annotations

import shutil
import socket

import pytest

from v2link_client.core.errors import PortInUseError
from v2link_client.core.process_manager import (
    ensure_port_available,
    find_xray_binary,
    validate_xray_config,
)
from v2link_client.core.storage import save_json


def test_ensure_port_available_detects_in_use_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        host, port = sock.getsockname()
        with pytest.raises(PortInUseError):
            ensure_port_available(host, port)


def test_validate_xray_config_smoke(tmp_path) -> None:
    if not shutil.which("xray"):
        pytest.skip("xray not installed")

    cfg = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "listen": "127.0.0.1",
                "port": 10809,
                "protocol": "socks",
                "settings": {"auth": "noauth"},
            }
        ],
        "outbounds": [{"protocol": "freedom", "settings": {}}],
    }
    cfg_path = tmp_path / "xray.json"
    save_json(cfg_path, cfg)

    xray = find_xray_binary()
    validate_xray_config(xray, cfg_path)

