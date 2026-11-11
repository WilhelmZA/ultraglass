"""Identify the client that sent a request through reverse proxies or a CDN."""

# Standard Library
import typing as t
import ipaddress

# Project
from hyperglass.state import use_state

if t.TYPE_CHECKING:
    # Third Party
    from litestar import Request

    # Project
    from hyperglass.models.config.web import ClientIP

__all__ = ("client_address", "resolve_client_address")

IPAddress = t.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


def _parse(value: t.Optional[str]) -> t.Optional[IPAddress]:
    """Parse an address, reading an IPv4-mapped IPv6 address as IPv4."""
    try:
        address = ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def _is_trusted(address: t.Optional[IPAddress], settings: "ClientIP") -> bool:
    if address is None:
        return False
    return any(
        address.version == network.version and address in network
        for network in settings.trusted_proxies
    )


def _forwarded_for(value: str, settings: "ClientIP") -> t.Optional[str]:
    """Pick the client entry from an X-Forwarded-For list.

    Each proxy appends the address it received the request from, so only the entries
    that trusted proxies added are reliable. With trusted proxies, the client is the
    last entry that is not itself a trusted proxy. Without them, it is the first entry.
    """
    entries = [entry.strip() for entry in value.split(",") if entry.strip()]
    if not settings.trusted_proxies:
        entries = entries[:1]
    for entry in reversed(entries):
        address = _parse(entry)
        if address is None:
            return None
        if not _is_trusted(address, settings):
            return entry
    return None


def resolve_client_address(
    headers: t.Mapping[str, str], peer: t.Optional[str], settings: "ClientIP"
) -> t.Optional[str]:
    """Resolve the client address from request headers and the socket peer.

    The order is the configured header, `X-Real-IP`, `X-Forwarded-For`, then the peer.
    A header value that is not an IP address is skipped. When trusted proxies are
    configured, headers are read only if the peer is one of them.
    """
    if settings.trusted_proxies and not _is_trusted(_parse(peer), settings):
        return peer

    for name in (settings.header, "x-real-ip"):
        value = (headers.get(name) or "").strip() if name else ""
        if _parse(value) is not None:
            return value

    forwarded = _forwarded_for(headers.get("x-forwarded-for") or "", settings)
    if forwarded is not None:
        return forwarded

    return peer


def client_address(request: "Request") -> str:
    """Identify the client of a request, using the `web.client_ip` configuration."""
    settings = use_state("params").web.client_ip
    peer = request.client.host if request.client else None
    return resolve_client_address(request.headers, peer, settings) or "anonymous"
