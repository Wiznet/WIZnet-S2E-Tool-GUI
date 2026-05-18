#!/usr/bin/python
# -*- coding: utf-8 -*-

# [사용되지 않는 기능 - 폐기 필요] TCP Multicast / Mixed search 폐기로 미사용

"""
TCP Multicast Scanner - Concurrent TCP device scanner using ThreadPoolExecutor.

This module provides parallel TCP scanning functionality for discovering WIZnet
devices across an IP range. It mimics the WIZMSGHandler interface but uses
concurrent TCP connections instead of UDP broadcast.
"""

from PyQt5.QtCore import QThread, pyqtSignal
from concurrent.futures import ThreadPoolExecutor, as_completed
from wizsocket.TCPClient import TCPClient
from constants import SockState
from utils import logger
import time
import codecs


# Packet size constant (matches WIZMSGHandler)
PACKET_SIZE = 4096


class TCPMulticastScanner(QThread):
    """
    Concurrent TCP scanner for device discovery across IP ranges.

    This class extends QThread to perform non-blocking TCP scanning of multiple
    IP addresses in parallel. It uses ThreadPoolExecutor for concurrent connections
    and maintains the same data structure as WIZMSGHandler for compatibility.

    Signals:
        search_result(int): Emitted when scan completes with total device count
        device_found(bytes): Emitted when individual device responds with data
        progress_update(int, int): Emitted periodically with (completed, total) counts
    """

    search_result = pyqtSignal(int)
    device_found = pyqtSignal(bytes)
    progress_update = pyqtSignal(int, int)

    def __init__(self, ip_list, port, cmd_list, timeout=2, max_workers=15):
        """
        Initialize TCP multicast scanner.

        Args:
            ip_list: List of IP addresses to scan (e.g., ['192.168.1.1', '192.168.1.2', ...])
            port: TCP port to connect to (typically 50001 for WIZnet devices)
            cmd_list: Command list to send to devices (same format as WIZMSGHandler)
            timeout: Connection timeout per IP in seconds (default: 2)
            max_workers: Maximum number of concurrent TCP connections (default: 15)
        """
        QThread.__init__(self)
        self.logger = logger

        self.ip_list = ip_list
        self.port = port
        self.cmd_list = cmd_list
        self.timeout = timeout
        self.max_workers = max_workers

        # Data storage - same structure as WIZMSGHandler for compatibility
        self.mac_list = []  # MAC addresses
        self.mn_list = []   # Model names
        self.vr_list = []   # Firmware versions
        self.st_list = []   # Status codes
        self.rcv_list = []  # Raw response data

    def _build_message(self):
        """
        Build command message packet.

        Replicates WIZMSGHandler.makecommands() logic to create a properly
        formatted command packet for device communication.

        Returns:
            bytes: Formatted command packet ready to send
        """
        msg = bytearray(PACKET_SIZE)
        size = 0

        try:
            for cmd in self.cmd_list:
                # Add command code (e.g., "MC", "VR", "MN")
                msg[size:] = str.encode(cmd[0])
                size += len(cmd[0])

                # Handle MAC address specially (convert to hex binary)
                if cmd[0] == "MA":
                    cmd[1] = cmd[1].replace(":", "")
                    hex_string = codecs.decode(cmd[1], "hex")
                    msg[size:] = hex_string
                    size += 6
                else:
                    # Regular parameter
                    msg[size:] = str.encode(cmd[1])
                    size += len(cmd[1])

                # Add CRLF delimiter if not already present
                if "\r\n" not in cmd[1]:
                    msg[size:] = str.encode("\r\n")
                    size += 2

        except Exception as e:
            self.logger.error(f"[ERROR] TCPMulticastScanner _build_message: {e}")

        return bytes(msg[:size])

    def _parse_response(self, data):
        """
        Parse device response data.

        Extracts MAC, model name, version, and status from device response.
        Replicates WIZMSGHandler response parsing logic.

        Args:
            data: Raw response data from device (bytes)

        Returns:
            dict: Parsed data with keys 'mac', 'mn', 'vr', 'st', or None if no MAC found
        """
        result = {}

        try:
            # Split by CRLF delimiter
            lines = data.split(b'\r\n')

            for line in lines:
                # Extract each field
                if b'MC' in line and line.startswith(b'MC'):
                    result['mac'] = line[2:]
                elif b'MN' in line and line.startswith(b'MN'):
                    result['mn'] = line[2:]
                elif b'VR' in line and line.startswith(b'VR'):
                    result['vr'] = line[2:]
                elif b'ST' in line and line.startswith(b'ST'):
                    result['st'] = line[2:]

        except Exception as e:
            self.logger.error(f"[ERROR] TCPMulticastScanner _parse_response: {e}")

        # Return None if no MAC address found (invalid device response)
        return result if 'mac' in result else None

    def _scan_single_ip(self, ip):
        """
        Scan a single IP address via TCP.

        Attempts to connect to the IP, send search command, and receive response.
        This method is executed in parallel by ThreadPoolExecutor.

        Args:
            ip: IP address to scan (string)

        Returns:
            tuple: (ip, data) where data is response bytes or None if failed
        """
        try:
            # Create TCP client with specified timeout
            client = TCPClient(self.timeout, ip, self.port, self.logger)

            # Open socket
            client.open()
            time.sleep(0.1)  # Brief delay for socket initialization

            # Attempt connection
            if client.state == SockState.SOCK_OPEN:
                client.connect()

            # If connected, send command and receive response
            if client.state == SockState.SOCK_CONNECT:
                msg = self._build_message()
                client.write(msg)

                # Wait for response
                time.sleep(0.5)

                # Read response
                data = client.recvfrom()

                # Clean up connection
                client.shutdown()

                if data:
                    return (ip, data)

        except Exception as e:
            # Connection failures are expected for non-responsive IPs
            # Log at debug level to avoid cluttering logs
            self.logger.debug(f"TCP scan failed for {ip}: {e}")

        return (ip, None)

    def run(self):
        """
        Execute parallel TCP scan across all IPs.

        Main thread execution method. Creates a thread pool and scans all IPs
        concurrently, emitting progress updates as results come in.
        """
        total = len(self.ip_list)
        completed = 0

        self.logger.info(f"Starting TCP multicast scan: {total} IPs, {self.max_workers} workers")

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all scan tasks
                future_to_ip = {
                    executor.submit(self._scan_single_ip, ip): ip
                    for ip in self.ip_list
                }

                # Process results as they complete
                for future in as_completed(future_to_ip):
                    completed += 1

                    try:
                        ip, data = future.result()

                        # If device responded, parse and store data
                        if data:
                            parsed = self._parse_response(data)

                            if parsed:
                                # Add to result lists
                                self.mac_list.append(parsed['mac'])
                                self.mn_list.append(parsed.get('mn', b''))
                                self.vr_list.append(parsed.get('vr', b''))
                                self.st_list.append(parsed.get('st', b''))
                                self.rcv_list.append(data)

                                # Emit individual device found signal
                                self.device_found.emit(data)

                                self.logger.info(f"Device found at {ip}: {parsed['mac']}")

                    except Exception as e:
                        self.logger.error(f"Error processing result for {future_to_ip[future]}: {e}")

                    # Emit progress update
                    self.progress_update.emit(completed, total)

        except Exception as e:
            self.logger.error(f"[ERROR] TCPMulticastScanner run: {e}")

        # Brief delay before emitting final result
        self.msleep(500)

        # Emit final result count
        device_count = len(self.mac_list)
        self.logger.info(f"TCP multicast scan complete: {device_count} devices found")
        self.search_result.emit(device_count)
