"""Parse V2Ray-style links.

This module currently focuses on `vless://` links because they're common in
V2Ray/Xray ecosystems and are the minimal requirement to start the core.
"""

from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse

from v2link_client.core.errors import InvalidLinkError, UnsupportedSchemeError

SUPPORTED_SCHEMES: set[str] = {"vmess", "vless", "trojan", "ss"}


@dataclass(frozen=True, slots=True)
class VlessLink:
    scheme: Literal["vless"]
    name: str | None
    user_id: str
    host: str
    port: int
    encryption: str
    security: str
    transport: str
    sni: str | None
    fingerprint: str | None
    allow_insecure: bool
    header_type: str | None
    path: str | None
    ws_host: str | None
    grpc_service_name: str | None
    flow: str | None
    alpn: list[str] | None

    def display_name(self) -> str:
        return self.name or f"{self.host}:{self.port}"


ParsedLink = VlessLink


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return None


def parse_link(raw: str) -> ParsedLink:
    raw = (raw or "").strip()
    if not raw:
        raise InvalidLinkError("Empty link", user_message="Paste a vless:// link first.")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in SUPPORTED_SCHEMES:
        raise UnsupportedSchemeError(
            f"Unsupported scheme: {scheme!r}",
            user_message=f"Unsupported link scheme: {scheme or '<missing>'}://",
        )

    if scheme != "vless":
        raise UnsupportedSchemeError(
            f"Scheme not implemented: {scheme}",
            user_message="Only vless:// links are supported in this build.",
        )

    return _parse_vless(raw)


def _parse_vless(raw: str) -> VlessLink:
    parsed = urlparse(raw)

    user_id = parsed.username or ""
    host = parsed.hostname or ""
    port = parsed.port
    if not user_id or not host or port is None:
        raise InvalidLinkError(
            "Malformed vless link",
            user_message="VLESS link must include user id, host, and port.",
        )

    try:
        uuid.UUID(user_id)
    except ValueError as exc:
        raise InvalidLinkError(
            "Invalid VLESS user id",
            user_message="VLESS user id must be a UUID.",
        ) from exc

    query_raw = parse_qs(parsed.query, keep_blank_values=True)
    query = {k.lower(): v for k, v in query_raw.items()}

    encryption = _first(query, "encryption") or "none"
    security = _first(query, "security") or "none"
    transport = _first(query, "type") or _first(query, "transport") or "tcp"

    allow_insecure = _parse_bool(_first(query, "allowinsecure"))
    if allow_insecure is None:
        allow_insecure = False

    sni = _first(query, "sni") or _first(query, "servername")
    fingerprint = _first(query, "fp") or _first(query, "fingerprint")
    header_type = _first(query, "headertype")
    path = _first(query, "path")
    ws_host = _first(query, "host")
    grpc_service_name = _first(query, "servicename")
    flow = _first(query, "flow")

    alpn_raw = _first(query, "alpn")
    alpn = None
    if alpn_raw:
        alpn = [part.strip() for part in alpn_raw.split(",") if part.strip()]
        if not alpn:
            alpn = None

    name = unquote(parsed.fragment) if parsed.fragment else None

    transport = transport.lower()
    if transport not in {"tcp", "ws", "grpc"}:
        raise InvalidLinkError(
            f"Unsupported transport: {transport}",
            user_message=f"Unsupported VLESS transport: {transport}",
        )

    security = security.lower()
    if security not in {"none", "tls"}:
        raise InvalidLinkError(
            f"Unsupported security: {security}",
            user_message=f"Unsupported VLESS security: {security}",
        )

    return VlessLink(
        scheme="vless",
        name=name,
        user_id=user_id,
        host=host,
        port=port,
        encryption=encryption,
        security=security,
        transport=transport,
        sni=sni,
        fingerprint=fingerprint,
        allow_insecure=allow_insecure,
        header_type=header_type,
        path=path,
        ws_host=ws_host,
        grpc_service_name=grpc_service_name,
        flow=flow,
        alpn=alpn,
    )
