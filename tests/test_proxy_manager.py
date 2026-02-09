from __future__ import annotations

import json
import subprocess

import pytest

import v2link_client.core.proxy_manager as pm
from v2link_client.core.errors import ProxyApplyError
from v2link_client.core.proxy_manager import SystemProxyConfig, SystemProxyManager


def test_system_proxy_apply_unsupported_backend(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pm.shutil, "which", lambda _name: None)
    mgr = SystemProxyManager(state_dir=tmp_path)
    with pytest.raises(ProxyApplyError):
        mgr.apply(
            SystemProxyConfig(
                http_host="127.0.0.1",
                http_port=8080,
                socks_host="127.0.0.1",
                socks_port=1080,
                bypass_hosts=["localhost"],
            )
        )


def test_system_proxy_apply_and_restore_gsettings(tmp_path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, check, capture_output, text, timeout):  # noqa: ANN001
        calls.append(list(cmd))

        if cmd[:3] == ["gsettings", "list-keys", "org.gnome.system.proxy"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="mode\nignore-hosts\n", stderr="")

        if cmd[:2] == ["gsettings", "get"]:
            schema = cmd[2]
            key = cmd[3]
            if (schema, key) == ("org.gnome.system.proxy", "mode"):
                return subprocess.CompletedProcess(cmd, 0, stdout="'none'\n", stderr="")
            if (schema, key) == ("org.gnome.system.proxy", "ignore-hosts"):
                return subprocess.CompletedProcess(cmd, 0, stdout="['localhost']\n", stderr="")
            if (schema, key) == ("org.gnome.system.proxy", "use-same-proxy"):
                return subprocess.CompletedProcess(cmd, 0, stdout="false\n", stderr="")
            if key == "enabled":
                return subprocess.CompletedProcess(cmd, 0, stdout="false\n", stderr="")
            if key == "host":
                return subprocess.CompletedProcess(cmd, 0, stdout="''\n", stderr="")
            if key == "port":
                return subprocess.CompletedProcess(cmd, 0, stdout="0\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="''\n", stderr="")

        if cmd[:2] == ["gsettings", "set"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(pm.shutil, "which", lambda _name: "/usr/bin/gsettings")
    monkeypatch.setattr(pm.subprocess, "run", fake_run)

    mgr = SystemProxyManager(state_dir=tmp_path)
    mgr.apply(
        SystemProxyConfig(
            http_host="127.0.0.1",
            http_port=8080,
            socks_host="127.0.0.1",
            socks_port=1080,
            bypass_hosts=["localhost", "127.0.0.0/8", "::1"],
        )
    )

    snap_path = tmp_path / pm.SNAPSHOT_FILE
    assert snap_path.exists()
    payload = json.loads(snap_path.read_text(encoding="utf-8"))
    assert payload["backend"] == "gsettings"

    # Ensure we enabled manual mode and set ignore-hosts with our bypass entries.
    set_cmds = [c for c in calls if c[:2] == ["gsettings", "set"]]
    assert ["gsettings", "set", "org.gnome.system.proxy", "mode", "'manual'"] in set_cmds
    assert any(
        c[:4] == ["gsettings", "set", "org.gnome.system.proxy", "ignore-hosts"]
        and "127.0.0.0/8" in c[4]
        and "::1" in c[4]
        for c in set_cmds
    )

    calls.clear()
    mgr.restore()
    assert not snap_path.exists()

    set_cmds = [c for c in calls if c[:2] == ["gsettings", "set"]]
    assert ["gsettings", "set", "org.gnome.system.proxy", "mode", "'none'"] in set_cmds

