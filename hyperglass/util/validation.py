"""Validation Utilities."""

# Standard Library
import typing as t

# Third Party
from netmiko.ssh_dispatcher import CLASS_MAPPER  # type: ignore

# Project
from hyperglass.constants import DRIVER_MAP

if t.TYPE_CHECKING:
    # Standard Library
    from ipaddress import IPv4Address, IPv6Address


def validate_platform(_type: str) -> t.Tuple[bool, t.Union[None, str]]:
    """Validate device type is supported."""

    all_device_types = {*DRIVER_MAP.keys(), *CLASS_MAPPER.keys()}

    result = (False, None)

    if _type in all_device_types:
        result = (True, DRIVER_MAP.get(_type, "netmiko"))

    return result


def get_driver(_type: str, driver: t.Optional[str]) -> str:
    """Determine the appropriate driver for a device."""

    if driver is None:
        # If no driver is set, use the driver map with netmiko as
        # fallback.
        return DRIVER_MAP.get(_type, "netmiko")

    all_drivers = {*DRIVER_MAP.values(), "netmiko"}

    if driver in all_drivers:
        # If a driver is set and it is valid, allow it.
        return driver

    # Otherwise, fail validation.
    raise ValueError("{} is not a supported driver.".format(driver))


def resolve_hostname(
    hostname: str,
) -> t.Generator[t.Union["IPv4Address", "IPv6Address"], None, None]:
    """Resolve a hostname via DNS/hostfile."""
    # Standard Library
    from socket import gaierror, getaddrinfo
    from ipaddress import ip_address

    # Project
    from hyperglass.log import log

    log.bind(hostname=hostname).debug("Ensuring hostname is resolvable")

    ip4 = None
    ip6 = None
    try:
        res = getaddrinfo(hostname, None)
        for sock in res:
            if sock[0].value == 2 and ip4 is None:
                ip4 = ip_address(sock[4][0])
            elif sock[0].value in (10, 30) and ip6 is None:
                ip6 = ip_address(sock[4][0])
    except (gaierror, ValueError, IndexError) as err:
        log.debug(str(err))
        pass

    yield ip4
    yield ip6


def parse_asn(value: t.Union[int, str]) -> t.Optional[int]:
    """Convert an asplain or asdot ASN to an integer.

    Returns `None` for anything that is not an ASN, such as origin codes or
    AS_SET and confederation delimiters.
    """
    if isinstance(value, int):
        return value if 0 <= value <= 4294967295 else None
    value = value.strip()
    if value.isdecimal():
        asn = int(value)
        return asn if asn <= 4294967295 else None
    high, sep, low = value.partition(".")
    if sep and high.isdecimal() and low.isdecimal():
        high_value, low_value = int(high), int(low)
        if high_value <= 65535 and low_value <= 65535:
            return high_value * 65536 + low_value
    return None


def parse_as_path(value: t.Union[str, t.Sequence[t.Union[int, str]]]) -> t.List[int]:
    """Convert an AS path string or list to integer ASNs, skipping non-ASN tokens."""
    tokens = value.split() if isinstance(value, str) else value
    return [asn for asn in (parse_asn(token) for token in tokens) if asn is not None]
