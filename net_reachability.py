#!/usr/bin/python
# -*- coding: utf-8 -*-
"""네트워크 도달성 확인 — ping.exe 서브프로세스를 쓰지 않는 두 가지 체크.

배경(2026-10-14): 기존 net_check_ping()은 매 검색/Apply마다 ping.exe를 서브프로세스로
띄웠다. 빌드된 exe(-w, 콘솔 없음)에서는 그때마다 새 콘솔 창이 깜빡였고, 같은 서브넷에
응답 없는 호스트를 ping.exe가 성공(rc=0)으로 오판하는 거짓양성도 있었다(ARP 재시도
지연으로 3초 가까이 걸린 뒤 성공 보고). 실측(스크래치패드 ping_alternatives_test.py):
같은 서브넷 무응답 호스트에 ping.exe rc=0(거짓양성, 3038ms) vs IcmpSendEcho rc=1(995ms,
정확).

- icmp_ping(): Windows는 iphlpapi.IcmpSendEcho(ctypes, 관리자 권한 불필요) — 서브프로세스/
  콘솔창 없음. 그 외 플랫폼은 ping 서브프로세스 유지(콘솔창 문제가 없는 OS).
- tcp_probe(): 순수 stdlib socket.create_connection — ctypes도 서브프로세스도 안 씀.
  "이 포트에 설정 접속이 가능한가"를 ping보다 직접적으로 답한다(ping 성공해도 포트가
  닫혀 있으면 설정은 못 하는 경우가 있어 unicast TCP 검색에는 이게 더 맞는 체크다).
"""
import socket
import subprocess
import sys

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes as wintypes
    import struct

    _iphlpapi = ctypes.windll.iphlpapi

    _iphlpapi.IcmpCreateFile.restype = wintypes.HANDLE
    _iphlpapi.IcmpCreateFile.argtypes = []

    _iphlpapi.IcmpCloseHandle.restype = wintypes.BOOL
    _iphlpapi.IcmpCloseHandle.argtypes = [wintypes.HANDLE]

    _iphlpapi.IcmpSendEcho.restype = wintypes.DWORD
    _iphlpapi.IcmpSendEcho.argtypes = [
        wintypes.HANDLE,   # IcmpHandle
        wintypes.ULONG,    # DestinationAddress
        wintypes.LPVOID,   # RequestData
        wintypes.WORD,     # RequestSize
        wintypes.LPVOID,   # RequestOptions
        wintypes.LPVOID,   # ReplyBuffer
        wintypes.DWORD,    # ReplySize
        wintypes.DWORD,    # Timeout
    ]

    class _IpOptionInformation(ctypes.Structure):
        _fields_ = [
            ("Ttl", ctypes.c_ubyte),
            ("Tos", ctypes.c_ubyte),
            ("Flags", ctypes.c_ubyte),
            ("OptionsSize", ctypes.c_ubyte),
            ("OptionsData", ctypes.c_void_p),
        ]

    class _IcmpEchoReply(ctypes.Structure):
        _fields_ = [
            ("Address", ctypes.c_ulong),
            ("Status", ctypes.c_ulong),
            ("RoundTripTime", ctypes.c_ulong),
            ("DataSize", ctypes.c_ushort),
            ("Reserved", ctypes.c_ushort),
            ("Data", ctypes.c_void_p),
            ("Options", _IpOptionInformation),
        ]

    def icmp_ping(dst_ip: str, timeout_ms: int = 1000) -> int:
        """0=응답 있음, 1=실패/타임아웃. ctypes IcmpSendEcho, 서브프로세스/콘솔창 없음."""
        dst_addr = struct.unpack("<L", socket.inet_aton(dst_ip))[0]
        hicmp = _iphlpapi.IcmpCreateFile()
        if not hicmp or hicmp == wintypes.HANDLE(-1).value:
            return 1
        try:
            send_data = b"wizconfig-ping"
            reply_size = ctypes.sizeof(_IcmpEchoReply) + len(send_data) + 8
            reply_buf = ctypes.create_string_buffer(reply_size)
            n_replies = _iphlpapi.IcmpSendEcho(
                hicmp, dst_addr, send_data, len(send_data), None,
                reply_buf, reply_size, timeout_ms,
            )
            if n_replies == 0:
                return 1
            reply = _IcmpEchoReply.from_buffer_copy(reply_buf)
            if reply.Status == 0 and reply.Address == dst_addr:
                return 0
            return 1
        finally:
            _iphlpapi.IcmpCloseHandle(hicmp)

else:
    def icmp_ping(dst_ip: str, timeout_ms: int = 1000) -> int:
        """0=응답 있음, 1=실패/타임아웃. 콘솔창 문제가 없는 플랫폼이라 ping 서브프로세스 유지."""
        return subprocess.Popen(
            ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), dst_ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).wait()


def tcp_probe(dst_ip: str, port: int, timeout: float = 1.0) -> int:
    """0=연결 성공, 1=실패/타임아웃. 순수 stdlib socket, ctypes/서브프로세스 없음."""
    try:
        with socket.create_connection((dst_ip, port), timeout=timeout):
            return 0
    except OSError:
        return 1
