from __future__ import annotations

import pytest

from v2link_client.core.errors import InvalidLinkError, UnsupportedSchemeError
from v2link_client.core.link_parser import VlessLink, parse_link


def test_parse_vless_basic() -> None:
    link = (
        "vless://b345f204-4df1-4d31-8243-dae7845099ad@prime.example.com:443"
        "?security=tls&allowInsecure=0&encryption=none&type=tcp&sni=aka.ms&fp=chrome&headerType=none"
        "#UdayaSri"
    )
    parsed = parse_link(link)
    assert isinstance(parsed, VlessLink)
    assert parsed.user_id == "b345f204-4df1-4d31-8243-dae7845099ad"
    assert parsed.host == "prime.example.com"
    assert parsed.port == 443
    assert parsed.security == "tls"
    assert parsed.allow_insecure is False
    assert parsed.transport == "tcp"
    assert parsed.sni == "aka.ms"
    assert parsed.fingerprint == "chrome"
    assert parsed.name == "UdayaSri"


def test_parse_vless_rejects_invalid_uuid() -> None:
    link = "vless://not-a-uuid@prime.example.com:443?security=tls"
    with pytest.raises(InvalidLinkError):
        parse_link(link)


def test_parse_rejects_unsupported_scheme() -> None:
    with pytest.raises(UnsupportedSchemeError):
        parse_link("http://example.com")


def test_parse_rejects_unimplemented_scheme() -> None:
    with pytest.raises(UnsupportedSchemeError):
        parse_link("vmess://abcd")

