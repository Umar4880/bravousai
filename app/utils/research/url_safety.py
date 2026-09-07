from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class URLSafetyError(ValueError):
    pass


LOCALHOST_NAMES = {"localhost", "localhost.localdomain"}


def validate_url_for_fetch(url: str, *, resolver=None) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise URLSafetyError("Invalid URL.") from exc

    if parsed.scheme not in {"http", "https"}:
        raise URLSafetyError(f"Unsupported URL scheme: {parsed.scheme or 'missing'}.")

    hostname = (parsed.hostname or "").lower().strip(".")
    if not hostname:
        raise URLSafetyError("URL hostname is missing.")
    if hostname in LOCALHOST_NAMES:
        raise URLSafetyError("Localhost URLs are blocked.")

    ip_addresses = _resolve_hostname(hostname, resolver=resolver or socket.getaddrinfo)
    for ip_address in ip_addresses:
        if _is_blocked_ip(ip_address):
            raise URLSafetyError(f"Blocked IP address: {ip_address}.")

    return url


def _resolve_hostname(hostname: str, *, resolver) -> list[ipaddress._BaseAddress]:
    try:
        literal = ipaddress.ip_address(hostname)
        return [literal]
    except ValueError:
        pass

    try:
        records = resolver(hostname, None)
    except socket.gaierror as exc:
        raise URLSafetyError(f"Hostname resolution failed: {hostname}.") from exc

    addresses: list[ipaddress._BaseAddress] = []
    for record in records:
        sockaddr = record[4]
        if not sockaddr:
            continue
        try:
            addresses.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue
    if not addresses:
        raise URLSafetyError(f"Hostname resolution returned no addresses: {hostname}.")
    return addresses


def _is_blocked_ip(ip_address: ipaddress._BaseAddress) -> bool:
    return any(
        (
            ip_address.is_loopback,
            ip_address.is_private,
            ip_address.is_link_local,
            ip_address.is_reserved,
            ip_address.is_multicast,
            ip_address.is_unspecified,
        )
    )
