"""Build core configuration files.

At the moment, the app targets Xray-core because it is widely available on
Linux distros and supports VLESS well. Configuration is written as JSON.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from v2link_client.core.errors import ConfigBuildError
from v2link_client.core.link_parser import ParsedLink, VlessLink
from v2link_client.core.storage import get_logs_dir

DEFAULT_LISTEN = "127.0.0.1"
DEFAULT_SOCKS_PORT = 1080
DEFAULT_HTTP_PORT = 8080


def build_xray_config(
    link: ParsedLink,
    *,
    listen: str = DEFAULT_LISTEN,
    socks_port: int = DEFAULT_SOCKS_PORT,
    http_port: int = DEFAULT_HTTP_PORT,
    logs_dir: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(link, VlessLink):
        raise ConfigBuildError(
            f"Unsupported link type: {type(link).__name__}",
            user_message="Unsupported link type for Xray config.",
        )

    logs_dir = logs_dir or get_logs_dir()

    outbound: dict[str, Any] = {
        "tag": "proxy",
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": link.host,
                    "port": link.port,
                    "users": [
                        {
                            "id": link.user_id,
                            "encryption": link.encryption,
                            **({"flow": link.flow} if link.flow else {}),
                        }
                    ],
                }
            ]
        },
        "streamSettings": _build_xray_stream_settings(link),
    }

    sniffing = {"enabled": True, "destOverride": ["http", "tls", "quic"]}

    config: dict[str, Any] = {
        "log": {
            "loglevel": "warning",
            "access": str(logs_dir / "xray_access.log"),
            "error": str(logs_dir / "xray_error.log"),
        },
        "inbounds": [
            {
                "tag": "socks-in",
                "listen": listen,
                "port": socks_port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
                "sniffing": sniffing,
            },
            {
                "tag": "http-in",
                "listen": listen,
                "port": http_port,
                "protocol": "http",
                "settings": {},
                "sniffing": sniffing,
            },
        ],
        "outbounds": [
            outbound,
            {"tag": "direct", "protocol": "freedom", "settings": {}},
            {"tag": "block", "protocol": "blackhole", "settings": {}},
        ],
    }

    return config


def _build_xray_stream_settings(link: VlessLink) -> dict[str, Any]:
    stream: dict[str, Any] = {"network": link.transport}

    if link.transport == "ws":
        path = link.path or "/"
        headers: dict[str, str] = {}
        if link.ws_host:
            headers["Host"] = link.ws_host
        ws_settings: dict[str, Any] = {"path": path}
        if headers:
            ws_settings["headers"] = headers
        stream["wsSettings"] = ws_settings
    elif link.transport == "grpc":
        if not link.grpc_service_name:
            raise ConfigBuildError(
                "Missing gRPC serviceName",
                user_message="VLESS gRPC links must include serviceName=...",
            )
        stream["grpcSettings"] = {"serviceName": link.grpc_service_name}
    elif link.transport == "tcp":
        header_type = (link.header_type or "none").strip().lower()
        if header_type not in {"none", ""}:
            if header_type != "http":
                raise ConfigBuildError(
                    f"Unsupported TCP header type: {header_type}",
                    user_message=f"Unsupported TCP headerType: {header_type}",
                )

            request: dict[str, Any] = {}
            if link.path:
                request["path"] = [link.path]
            if link.ws_host:
                request["headers"] = {"Host": [link.ws_host]}
            stream["tcpSettings"] = {"header": {"type": "http", "request": request}}
    else:  # pragma: no cover - defensive (parser blocks this)
        raise ConfigBuildError(
            f"Unsupported transport: {link.transport}",
            user_message=f"Unsupported transport: {link.transport}",
        )

    if link.security == "tls":
        tls_settings: dict[str, Any] = {
            "allowInsecure": link.allow_insecure,
            "serverName": link.sni or link.host,
        }
        if link.fingerprint:
            tls_settings["fingerprint"] = link.fingerprint
        if link.alpn:
            tls_settings["alpn"] = link.alpn
        stream["security"] = "tls"
        stream["tlsSettings"] = tls_settings

    return stream
