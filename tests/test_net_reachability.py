# -*- coding: utf-8 -*-
"""net_reachability — ping.exe 서브프로세스 없이 도달성을 확인한다.

배경(2026-10-14): 예전 `net_check_ping()` 은 검색/Apply 마다 ping.exe 를 띄웠다. 빌드된
exe(-w, 콘솔 없음)에서는 그때마다 콘솔 창이 깜빡였고, 같은 서브넷에 응답 없는 호스트를
ping.exe 가 성공(rc=0)으로 오판했다(ARP 재시도로 3초 가까이 걸린 뒤 성공 보고).

- tcp_probe : 설정 포트로 직접 TCP 연결 — "설정이 가능한가"에 ping 보다 직접 답한다.
- icmp_ping : Windows 는 IcmpSendEcho(ctypes), 서브프로세스를 쓰지 않는다.

같은 서브넷 무응답 호스트의 거짓양성은 네트워크가 있어야 재현되므로 여기서 시험하지 않고,
"서브프로세스를 쓰지 않는다"와 "연결 가능/불가의 판정"만 고정한다.
"""
import socket
import subprocess
import sys

import pytest

from net_reachability import icmp_ping, tcp_probe


@pytest.fixture
def listening_port():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    yield srv.getsockname()[1]
    srv.close()


def _closed_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()          # 닫은 직후의 포트는 연결 거부가 난다
    return port


def test_tcp_probe_succeeds_on_open_port(listening_port):
    assert tcp_probe("127.0.0.1", listening_port, timeout=1.0) == 0


def test_tcp_probe_fails_on_closed_port():
    assert tcp_probe("127.0.0.1", _closed_port(), timeout=1.0) == 1


def test_tcp_probe_does_not_raise_on_bad_address():
    """이름을 못 푸는 주소도 예외가 아니라 실패(1)로 돌려준다 — 호출부가 분기로만 다룬다."""
    assert tcp_probe("256.256.256.256", 5001, timeout=0.5) == 1


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 에서만 IcmpSendEcho 를 쓴다")
def test_icmp_ping_never_spawns_a_subprocess(monkeypatch):
    """콘솔 창 깜빡임 회귀 방지 — Windows 에서 icmp_ping 이 프로세스를 띄우면 실패한다."""

    def _forbidden(*a, **k):
        raise AssertionError("icmp_ping 이 서브프로세스를 띄웠다 (콘솔 창이 깜빡인다)")

    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    assert icmp_ping("127.0.0.1", timeout_ms=1000) == 0


def test_icmp_ping_reports_failure_not_exception_for_unusable_target():
    """무응답/잘못된 대상은 예외가 아니라 1."""
    rc = icmp_ping("192.0.2.1", timeout_ms=300)   # TEST-NET-1, 응답 없음
    assert rc == 1
