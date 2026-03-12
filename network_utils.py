#!/usr/bin/python
# -*- coding: utf-8 -*-

# [사용되지 않는 기능 - 폐기 필요] TCP Multicast / Mixed search 폐기로 미사용

"""
Network utility functions for subnet calculation and IP address operations.
Used by Device Search functionality for TCP multicast and mixed search modes.
"""

import ipaddress
from typing import List, Tuple, Optional
import ifaddr


def get_subnet_hosts(ip_address: str, network_prefix: int = 24) -> List[str]:
    """
    Calculate all host IPs in the subnet (excluding network and broadcast addresses).

    Args:
        ip_address: IP address within the subnet (e.g., "192.168.1.10")
        network_prefix: Subnet mask prefix (e.g., 24 for /24, 16 for /16)

    Returns:
        List of all valid host IP addresses in the subnet as strings.
        For /24: 254 hosts, for /16: 65534 hosts

    Examples:
        >>> get_subnet_hosts('192.168.1.10', 24)
        ['192.168.1.1', '192.168.1.2', ..., '192.168.1.254']
    """
    try:
        # Create network object with strict=False to allow host bits set
        network = ipaddress.IPv4Network(f'{ip_address}/{network_prefix}', strict=False)
        # Return all host IPs (excludes network address and broadcast address)
        return [str(ip) for ip in network.hosts()]
    except Exception as e:
        print(f"Error calculating subnet hosts: {e}")
        return []


def get_adapter_subnet_info(adapter_ip: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Get subnet information for a given network adapter IP address.

    Args:
        adapter_ip: The selected adapter IP address (e.g., "192.168.1.100")

    Returns:
        Tuple of (ip, network_prefix):
        - ip: The adapter's IP address
        - network_prefix: Subnet prefix if available (e.g., 24), or None if not provided by ifaddr

    Examples:
        >>> get_adapter_subnet_info('192.168.1.100')
        ('192.168.1.100', 24)

        >>> get_adapter_subnet_info('10.0.0.5')
        ('10.0.0.5', None)  # If ifaddr doesn't provide network_prefix
    """
    try:
        adapters = ifaddr.get_adapters()
        for adapter in adapters:
            for ip in adapter.ips:
                # Check if this is the matching adapter
                if hasattr(ip, 'ip') and ip.ip == adapter_ip:
                    # Try to get network_prefix attribute
                    # Note: ifaddr may or may not provide this attribute
                    prefix = getattr(ip, 'network_prefix', None)
                    return (ip.ip, prefix)
    except Exception as e:
        print(f"Error getting adapter subnet info: {e}")

    return (None, None)


def extract_ip_from_device_response(data: bytes) -> Optional[str]:
    """
    Extract device IP address from WIZnet device response data.

    Looks for the LI (Local IP) field in the device response packet.

    Args:
        data: Raw response data from device (bytes)

    Returns:
        IP address as string if found, None otherwise

    Examples:
        >>> data = b'MC001122334455\\r\\nLI192.168.1.100\\r\\nVR1.0.0\\r\\n'
        >>> extract_ip_from_device_response(data)
        '192.168.1.100'
    """
    try:
        # Split response by CRLF delimiter
        lines = data.split(b'\r\n')

        for line in lines:
            # Look for LI (Local IP) field
            if line.startswith(b'LI'):
                # Extract IP after "LI" prefix (2 bytes)
                ip_str = line[2:].decode('utf-8')
                return ip_str
    except Exception as e:
        print(f"Error extracting IP from response: {e}")

    return None


def calculate_ip_range_size(network_prefix: int) -> int:
    """
    Calculate the number of usable host addresses for a given subnet prefix.

    Args:
        network_prefix: Subnet mask prefix (e.g., 24, 16, 8)

    Returns:
        Number of usable host addresses

    Examples:
        >>> calculate_ip_range_size(24)
        254
        >>> calculate_ip_range_size(16)
        65534
    """
    # Total addresses in subnet: 2^(32 - prefix)
    # Usable hosts: total - 2 (network address and broadcast address)
    total_addresses = 2 ** (32 - network_prefix)
    usable_hosts = total_addresses - 2
    return usable_hosts


def is_valid_ipv4(ip_str: str) -> bool:
    """
    Validate if a string is a valid IPv4 address.

    Args:
        ip_str: IP address string to validate

    Returns:
        True if valid IPv4 address, False otherwise

    Examples:
        >>> is_valid_ipv4('192.168.1.1')
        True
        >>> is_valid_ipv4('256.1.1.1')
        False
    """
    try:
        ipaddress.IPv4Address(ip_str)
        return True
    except ValueError:
        return False
