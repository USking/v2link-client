"""Apply and restore system proxy settings.

This is how we make the local Xray inbounds affect the whole desktop, not just
apps where the user manually configured proxy settings.

Currently supported:
- GNOME (and many desktops using libproxy) via `gsettings`.

We keep this module dependency-free by shelling out to the system tools.
"""

from __future__ import annotations

from dataclasses import dataclass
import ast
import logging
from pathlib import Path
import shutil
import subprocess
from typing import Final, Literal

from v2link_client.core.errors import ProxyApplyError
from v2link_client.core.storage import get_state_dir, load_json, save_json

logger = logging.getLogger(__name__)

SNAPSHOT_FILE: Final[str] = "system_proxy_snapshot.json"

ProxyBackendName = Literal["gsettings"]


@dataclass(frozen=True, slots=True)
class SystemProxyConfig:
    http_host: str
    http_port: int
    socks_host: str
    socks_port: int
    bypass_hosts: list[str]


def _run(cmd: list[str], *, timeout_s: float = 3.0) -> subprocess.CompletedProcess[str]:
    logger.info("Running command: %s", cmd)
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProxyApplyError(
            f"Command timed out: {cmd}",
            user_message="Timed out while applying system proxy settings.",
        ) from exc
    except OSError as exc:
        raise ProxyApplyError(
            f"Command failed: {cmd}: {exc}",
            user_message="Failed to apply system proxy settings (missing tools/permissions).",
        ) from exc

    if result.returncode != 0:
        detail = (result.stderr or "").strip() or (result.stdout or "").strip() or "unknown error"
        raise ProxyApplyError(
            f"Command failed: {cmd}: {detail}",
            user_message=f"Failed to apply system proxy settings: {detail}",
        )

    return result


def _gsettings_available() -> bool:
    if shutil.which("gsettings") is None:
        return False
    try:
        out = _run(["gsettings", "list-keys", "org.gnome.system.proxy"], timeout_s=2.0).stdout
    except ProxyApplyError:
        return False
    return "mode" in out


_GSETTINGS_KEYS: Final[list[tuple[str, str]]] = [
    ("org.gnome.system.proxy", "mode"),
    ("org.gnome.system.proxy", "ignore-hosts"),
    ("org.gnome.system.proxy", "use-same-proxy"),
    ("org.gnome.system.proxy.http", "enabled"),
    ("org.gnome.system.proxy.http", "host"),
    ("org.gnome.system.proxy.http", "port"),
    ("org.gnome.system.proxy.https", "host"),
    ("org.gnome.system.proxy.https", "port"),
    ("org.gnome.system.proxy.socks", "host"),
    ("org.gnome.system.proxy.socks", "port"),
]


def _gsettings_get(schema: str, key: str) -> str:
    return _run(["gsettings", "get", schema, key], timeout_s=2.5).stdout.strip()


def _gsettings_set(schema: str, key: str, value: str) -> None:
    _run(["gsettings", "set", schema, key, value], timeout_s=2.5)


def _format_gsettings_str(value: str) -> str:
    # gsettings expects strings quoted with single quotes.
    value = (value or "").replace("'", "\\'")
    return f"'{value}'"


def _format_gsettings_str_list(values: list[str]) -> str:
    quoted = ", ".join(_format_gsettings_str(v) for v in values)
    return f"[{quoted}]"


def _parse_gsettings_str_list(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        parsed = ast.literal_eval(raw)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    out: list[str] = []
    for item in parsed:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _gsettings_snapshot() -> dict[str, str]:
    snap: dict[str, str] = {}
    for schema, key in _GSETTINGS_KEYS:
        snap[f"{schema}:{key}"] = _gsettings_get(schema, key)
    return snap


def _gsettings_restore(snapshot: dict[str, str]) -> None:
    # Restore non-mode keys first, then mode last to avoid transient broken proxy states.
    mode_value = snapshot.get("org.gnome.system.proxy:mode")
    for schema, key in _GSETTINGS_KEYS:
        if schema == "org.gnome.system.proxy" and key == "mode":
            continue
        raw_value = snapshot.get(f"{schema}:{key}")
        if raw_value is None:
            continue
        _gsettings_set(schema, key, raw_value)
    if mode_value is not None:
        _gsettings_set("org.gnome.system.proxy", "mode", mode_value)


def _gsettings_apply(cfg: SystemProxyConfig) -> None:
    # Merge bypass list with existing ignore-hosts.
    existing = _parse_gsettings_str_list(_gsettings_get("org.gnome.system.proxy", "ignore-hosts"))
    merged: list[str] = []
    for item in existing + list(cfg.bypass_hosts or []):
        item = (item or "").strip()
        if not item:
            continue
        if item not in merged:
            merged.append(item)

    # Set per-protocol first, then switch mode to manual last.
    _gsettings_set("org.gnome.system.proxy.http", "enabled", "true")
    _gsettings_set("org.gnome.system.proxy.http", "host", _format_gsettings_str(cfg.http_host))
    _gsettings_set("org.gnome.system.proxy.http", "port", str(int(cfg.http_port)))
    _gsettings_set("org.gnome.system.proxy.https", "host", _format_gsettings_str(cfg.http_host))
    _gsettings_set("org.gnome.system.proxy.https", "port", str(int(cfg.http_port)))
    _gsettings_set("org.gnome.system.proxy.socks", "host", _format_gsettings_str(cfg.socks_host))
    _gsettings_set("org.gnome.system.proxy.socks", "port", str(int(cfg.socks_port)))
    _gsettings_set("org.gnome.system.proxy", "use-same-proxy", "true")
    _gsettings_set("org.gnome.system.proxy", "ignore-hosts", _format_gsettings_str_list(merged))
    _gsettings_set("org.gnome.system.proxy", "mode", "'manual'")


class SystemProxyManager:
    def __init__(self, *, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or get_state_dir()

        backend: ProxyBackendName | None = None
        if _gsettings_available():
            backend = "gsettings"
        self._backend = backend

    @property
    def backend(self) -> ProxyBackendName | None:
        return self._backend

    @property
    def snapshot_path(self) -> Path:
        return self._state_dir / SNAPSHOT_FILE

    def is_supported(self) -> bool:
        return self._backend is not None

    def restore_if_needed(self) -> bool:
        """Restore system proxy if we have a snapshot from a previous run."""
        if not self.snapshot_path.exists():
            return False
        try:
            self.restore()
        except ProxyApplyError:
            # If restore fails, keep the snapshot so user/dev can investigate.
            raise
        return True

    def apply(self, cfg: SystemProxyConfig) -> None:
        if self._backend != "gsettings":
            raise ProxyApplyError(
                f"Unsupported system proxy backend: {self._backend}",
                user_message="System proxy apply not supported on this desktop yet.",
            )

        # Prevent stacking snapshots if apply is called multiple times.
        if self.snapshot_path.exists():
            logger.info("Existing system proxy snapshot found; restoring first")
            try:
                self.restore()
            except ProxyApplyError:
                # Keep going: user likely wants to re-apply.
                pass

        snapshot = _gsettings_snapshot()
        save_json(self.snapshot_path, {"backend": "gsettings", "snapshot": snapshot})

        try:
            _gsettings_apply(cfg)
        except ProxyApplyError:
            # Best-effort rollback.
            try:
                _gsettings_restore(snapshot)
            except ProxyApplyError:
                logger.exception("Failed to rollback system proxy settings")
            raise

    def restore(self) -> None:
        data = load_json(self.snapshot_path, None)
        if not isinstance(data, dict):
            return
        backend = data.get("backend")
        snapshot = data.get("snapshot")
        if backend != "gsettings" or not isinstance(snapshot, dict):
            raise ProxyApplyError(
                f"Invalid system proxy snapshot: backend={backend!r}",
                user_message="System proxy snapshot is invalid; can't restore.",
            )

        if self._backend is None:
            # If the current session can't access gsettings, we still try.
            self._backend = "gsettings"

        _gsettings_restore({str(k): str(v) for k, v in snapshot.items()})
        try:
            self.snapshot_path.unlink()
        except OSError:
            logger.exception("Failed to remove system proxy snapshot: %s", self.snapshot_path)

