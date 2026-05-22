#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIZ550MSGHandler.py — WIZ550SR/S2E/WEB UDP 프로토콜 핸들러

프로토콜:
  - UDP 포트 6550 전용 (WIZ5xxSR:50001, WIZ1x0SR:1460과 분리)
  - XOR 암호화: valid[bit7]=1 → 암호화됨, key=valid&0x7F
  - 헤더: [STX=0xA5][valid][unicast][op_code][0xAA/0x55][len_LSB][len_MSB]
  - 검색: DISCOVERY_ALL(0xA1) 브로드캐스트, 응답 product_code로 장치 타입 판별
  - 읽기: GET_INFO(0xB0) 유니캐스트, recv[6~7] 재파싱 (Java MSB 버그 우회)
  - 쓰기: SET_INFO(0xC0) 유니캐스트
  - 리셋: REMOTE_RESET(0xE0)/FACTORY_RESET(0xF0) 유니캐스트
"""

import socket
import select
import time
import random
import struct

import ifaddr
from PyQt5.QtCore import QThread, pyqtSignal

from utils import logger


# ─────────────────────────────────────────────────────────────────
# 프로토콜 상수
# ─────────────────────────────────────────────────────────────────
WIZ550_PORT    = 6550
STX            = 0xA5
WIZNET_REQUEST = 0xAA
WIZNET_REPLY   = 0x55

# op_code 상수
OP_DISCOVERY_ALL = 0xA1
OP_GET_INFO      = 0xB0
OP_SET_INFO      = 0xC0
OP_FW_UPLOAD     = 0xD1
OP_REMOTE_RESET  = 0xE0
OP_FACTORY_RESET = 0xF0

# product_code → 장치 타입 (D-03)
PRODUCT_CODE_SR  = bytes([0x02, 0x00, 0x00])
PRODUCT_CODE_S2E = bytes([0x00, 0x00, 0x00])
PRODUCT_CODE_WEB = bytes([0x01, 0x02, 0x00])


# ─────────────────────────────────────────────────────────────────
# XOR 헬퍼 함수 (D-06, D-07)
# ─────────────────────────────────────────────────────────────────

def _make_valid_and_key() -> tuple:
    """valid 바이트(0x80~0xFE)와 XOR 키(0x00~0x7E) 생성 (D-06)"""
    valid = 0x80 + random.randint(0, 0x7E)  # 0x80~0xFE
    key = valid & 0x7F                       # 0x00~0x7E
    return valid, key


def _encrypt(buf: bytearray, key: int) -> None:
    """
    헤더(offset 7) 이후 payload를 XOR 암호화 (D-07).
    buf를 in-place 수정. 헤더 7B는 변경 없음.
    """
    for i in range(7, len(buf)):
        buf[i] ^= key


def _decrypt(payload: bytes, key: int, length: int) -> bytes:
    """
    offset 0부터 length바이트를 XOR 복호화 (D-07).
    parse_header shift 이후 호출. 새 bytes 반환.
    """
    return bytes(b ^ key for b in payload[:length])


# ─────────────────────────────────────────────────────────────────
# 헤더 빌드 헬퍼 (PROTO-02)
# ─────────────────────────────────────────────────────────────────

def _build_header_with_payload(op_code: int, unicast: bool, payload: bytes) -> bytes:
    """
    7B 헤더 + 암호화된 payload 조립.
    반환: 완성된 패킷 bytes
    """
    payload_len = len(payload)
    valid, key = _make_valid_and_key()
    buf = bytearray(7 + payload_len)
    buf[0] = STX
    buf[1] = valid
    buf[2] = 0x01 if unicast else 0x00
    buf[3] = op_code
    buf[4] = WIZNET_REQUEST
    buf[5] = payload_len & 0xFF           # length LSB
    buf[6] = (payload_len >> 8) & 0xFF    # length MSB
    if payload_len > 0:
        buf[7:] = payload
        _encrypt(buf, key)
    return bytes(buf)


# ─────────────────────────────────────────────────────────────────
# 패킷 빌더 함수 (PROTO-04)
# ─────────────────────────────────────────────────────────────────

def _mac_str_to_bytes(mac_str: str) -> bytes:
    """'AA:BB:CC:DD:EE:FF' 또는 'AA-BB-CC-DD-EE-FF' → 6B bytes"""
    return bytes(int(x, 16) for x in mac_str.replace('-', ':').split(':'))


def _build_discovery_all(unicast: bool = False) -> bytes:
    """
    DISCOVERY_ALL(0xA1) 패킷 — 7B, payload 없음 (PROTO-04).
    unicast=False: 브로드캐스트용(0x00), unicast=True: IP Address 직접 전송용(0x01).
    payload 없으므로 암호화 불필요.
    """
    valid, _ = _make_valid_and_key()
    buf = bytearray(7)
    buf[0] = STX
    buf[1] = valid
    buf[2] = 0x01 if unicast else 0x00
    buf[3] = OP_DISCOVERY_ALL
    buf[4] = WIZNET_REQUEST
    buf[5] = 0x00        # length LSB
    buf[6] = 0x00        # length MSB
    return bytes(buf)


def _build_get_info(target_mac: str) -> bytes:
    """
    GET_INFO(0xB0) 패킷 — 7B 헤더 + 6B MAC payload = 13B (PROTO-04).
    Java 원본: 255.255.255.255로 브로드캐스트 전송 (Pitfall 4 참조).
    """
    mac_b = _mac_str_to_bytes(target_mac)  # 6B
    return _build_header_with_payload(OP_GET_INFO, unicast=False, payload=mac_b)


def _build_set_info(target_mac: str, password: str, config_data: bytes) -> bytes:
    """
    SET_INFO(0xC0) 패킷 — payload: dst_mac[6] + pw_len[1] + pw[16] + config_data (PROTO-04).
    총 payload = 6+1+16+len(config_data) 바이트.
    """
    mac_b  = _mac_str_to_bytes(target_mac)
    pw_enc = password.encode('ascii', errors='replace')[:16].ljust(16, b'\x00')
    pw_len = min(len(password.strip()), 16)
    payload = mac_b + bytes([pw_len]) + pw_enc + config_data
    return _build_header_with_payload(OP_SET_INFO, unicast=True, payload=payload)


def _build_reset(op_code: int, target_mac: str, password: str) -> bytes:
    """
    REMOTE_RESET(0xE0) 또는 FACTORY_RESET(0xF0) 패킷 (PROTO-04).
    payload 23B: dst_mac[6] + pw_len[1] + pw[16]
    op_code은 OP_REMOTE_RESET 또는 OP_FACTORY_RESET만 허용 (T-04-01-05).
    """
    if op_code not in (OP_REMOTE_RESET, OP_FACTORY_RESET):
        raise ValueError(f"op_code 오류: {op_code:#04x}. OP_REMOTE_RESET 또는 OP_FACTORY_RESET만 허용.")
    mac_b  = _mac_str_to_bytes(target_mac)
    pw_enc = password.encode('ascii', errors='replace')[:16].ljust(16, b'\x00')
    pw_len = min(len(password.strip()), 16)
    payload = mac_b + bytes([pw_len]) + pw_enc  # 6+1+16 = 23B
    return _build_header_with_payload(op_code, unicast=True, payload=payload)


def build_fw_upload_pkt(target_mac: str, server_ip: str, server_port: int,
                        file_name: str, password: str = "") -> bytes:
    """
    FIRMWARE_UPLOAD_INIT(0xD1) 패킷 — 86바이트 (FW-02).

    payload 79B: dst_mac[6] + pw_len[1] + pw[16] + server_ip[4]
                 + server_port LE[2] + file_name[50]

    server_port는 리틀엔디안 (LSB first).
    Java 원본: data[i++]=(byte)port; data[i++]=(byte)(port>>8);
    """
    mac_b    = _mac_str_to_bytes(target_mac)
    pw_bytes = password.encode('ascii', errors='replace')[:16]
    pw_enc   = pw_bytes.ljust(16, b'\x00')
    pw_len   = min(len(password.strip()), 16)
    ip_b     = bytes(int(x) for x in server_ip.split('.'))
    port_b   = struct.pack('<H', server_port)
    fname_b  = file_name.encode('ascii', errors='replace')[:50].ljust(50, b'\x00')
    payload  = mac_b + bytes([pw_len]) + pw_enc + ip_b + port_b + fname_b
    assert len(payload) == 79, f"payload must be 79B, got {len(payload)}"
    # unicast=True: Java 원본 §4.3 — firmware_upload()는 항상 유니캐스트 (SET_INFO와 동일)
    return _build_header_with_payload(OP_FW_UPLOAD, unicast=True, payload=payload)


# ─────────────────────────────────────────────────────────────────
# 응답 파싱 함수 (PROTO-05, D-08)
# ─────────────────────────────────────────────────────────────────

def _parse_discovery_reply(data: bytes):
    """
    Discovery 응답(최소 19B) 파싱.
    수신: 7B 헤더 + 12B payload (product_code[3] + fw_ver[3] + mac[6])
    product_code가 SR/S2E/WEB 이외이면 None 반환 (D-03 무시 정책).
    반환 dict: device_type, product_code, fw_version, fw_str, mac, mac_bytes, _proto

    보안: data[0]!=STX, data[4]!=WIZNET_REPLY 검증 (T-04-01-01).
    """
    if len(data) < 7 + 12:
        return None
    if data[0] != STX:
        return None
    if data[4] != WIZNET_REPLY:
        return None

    valid   = data[1]
    payload = bytearray(data[7:7 + 12])

    # 복호화 (valid bit7=1 → 암호화됨)
    if valid & 0x80:
        key = valid & 0x7F
        for i in range(len(payload)):
            payload[i] ^= key

    product_code = bytes(payload[0:3])
    fw_version   = bytes(payload[3:6])
    mac_bytes    = bytes(payload[6:12])

    if product_code == PRODUCT_CODE_SR:
        device_type = 'WIZ550SR'
    elif product_code == PRODUCT_CODE_S2E:
        device_type = 'WIZ550S2E'
    elif product_code == PRODUCT_CODE_WEB:
        device_type = 'WIZ550WEB'
    else:
        return None  # WIZ550 계열 아님 → 무시 (D-03)

    mac_str  = ':'.join(f'{b:02X}' for b in mac_bytes)
    _is_boot = fw_version[0] > 100
    fw_str   = (f'Bootloader {fw_version[0]-100}.{fw_version[1]}.{fw_version[2]}'
                if _is_boot else
                f'{fw_version[0]}.{fw_version[1]}.{fw_version[2]}')

    return {
        'device_type':  device_type,
        'product_code': product_code,
        'fw_version':   fw_version,
        'is_boot':      _is_boot,
        'fw_str':       fw_str,
        'mac':          mac_str,
        'mac_bytes':    mac_bytes,
        '_proto':       'wiz550',
    }


def _parse_get_info_reply(data: bytes, device_type: str) -> dict:
    """
    GET_INFO(0xB0) 응답 파싱.

    응답 구조 (7B 헤더 이후 payload):
      payload[0~5]  = src_mac[6]
      payload[6]    = config_len LSB  (D-08: Java MSB 버그 우회, 직접 재파싱)
      payload[7]    = config_len MSB
      payload[8~]   = system_info (Config 본체)

    D-08: 헤더 내 length(data[5~6])를 신뢰하지 않고 payload[6~7]에서 직접 재파싱.
    보안: len(data) < 7+8 체크 후 파싱 진행 (T-04-01-02).
    """
    if len(data) < 7 + 8:  # 헤더 7B + MAC 6B + len 2B 최소
        return {}
    if data[0] != STX:
        return {}

    valid = data[1]
    # 헤더 내 payload 전체 길이 (복호화 범위 계산용)
    total_payload_len = (data[5] & 0xFF) + ((data[6] & 0xFF) << 8)

    # payload shift (헤더 7B 제외)
    payload = bytearray(data[7:])

    # 복호화 (D-07)
    if valid & 0x80:
        key = valid & 0x7F
        for i in range(min(len(payload), total_payload_len)):
            payload[i] ^= key

    # D-08: payload[6~7]에서 Config 크기 재파싱 (Java parse_header MSB 버그 우회)
    if len(payload) < 8:
        return {}
    config_len = (payload[6] & 0xFF) + ((payload[7] & 0xFF) << 8)

    src_mac = ':'.join(f'{b:02X}' for b in payload[0:6])

    # system_info: payload[6]부터 config_len 바이트 (RESEARCH Pattern 4 기준)
    # payload[6~7]=config_len(2B) 자체가 SR_FORMAT의 packet_size H 필드이므로
    # system_info는 payload[6]에서 시작 (payload[8]부터 하면 2B 오프셋 오류 발생)
    system_info = bytes(payload[6:6 + config_len])

    if not system_info or len(system_info) < 5:
        logger.warning(f"[WIZ550] GET_INFO system_info 부족: {len(system_info)}B")
        return {}

    # WIZ550Profile에서 파싱 — Wave 2 구현 후 실제 동작
    try:
        from WIZ550Profile import parse_sr, parse_s2e, parse_web
        if device_type == 'WIZ550SR':
            return parse_sr(system_info)
        elif device_type == 'WIZ550S2E':
            return parse_s2e(system_info)
        elif device_type == 'WIZ550WEB':
            return parse_web(system_info)
    except ImportError:
        logger.warning("[WIZ550] WIZ550Profile 미구현 — GET_INFO 파싱 불가 (Wave 2 완료 후 동작)")
        # Wave 2 이전에는 raw dict 반환
        return {
            'mac': src_mac,
            'local_ip': '0.0.0.0',
            '_proto': 'wiz550',
            '_raw_config': system_info,
        }
    return {}


def _parse_set_reply(data: bytes) -> bool:
    """
    SET_INFO(0xC0) / RESET 응답 파싱.
    응답 수신 = 성공. payload: src_mac[6]만 (6B).
    """
    if len(data) < 7 + 6:
        return False
    if data[0] != STX:
        return False
    if data[4] != WIZNET_REPLY:
        return False
    return True


# ─────────────────────────────────────────────────────────────────
# QThread 클래스 (PROTO-06, D-01, D-05)
# ─────────────────────────────────────────────────────────────────

class WIZ550Searcher(QThread):
    """
    WIZ550 검색 스레드.
    DISCOVERY_ALL(0xA1) 브로드캐스트 → product_code 기반 SR/S2E/WEB 판별.
    search_done 시그널: [device_dict, ...] (D-01)
    """
    search_done = pyqtSignal(list)

    def __init__(self, iface_ip: str = "", timeout: float = 15.0,
                 target_ip: str = ""):
        super().__init__()
        self.iface_ip  = iface_ip
        self.timeout   = timeout   # D-05: 브로드캐스트 검색은 15초 (여러 장치 응답 수집)
        self.target_ip = target_ip  # 비어있으면 broadcast, 설정 시 unicast 추가 전송

    def run(self):
        results = {}   # mac_str → device_dict (MAC 기반 중복 제거)

        # 모든 non-loopback NIC에서 브로드캐스트 전송
        # selected_eth가 다른 서브넷에 바인딩되어 있어도 WIZ550을 발견하기 위함
        bind_ips = []
        try:
            for adapter in ifaddr.get_adapters():
                for ip in adapter.ips:
                    if isinstance(ip.ip, str) and not ip.ip.startswith('127.'):
                        bind_ips.append(ip.ip)
        except Exception as e:
            logger.warning(f"[WIZ550] NIC 열거 실패: {e}")
        if not bind_ips:
            bind_ips = [self.iface_ip] if self.iface_ip else ['']

        pkt_bcast   = _build_discovery_all(unicast=False)
        pkt_unicast = _build_discovery_all(unicast=True)
        socks = []
        try:
            for bind_ip in bind_ips:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
                    s.bind((bind_ip, 0))
                    s.sendto(pkt_bcast, ('255.255.255.255', WIZ550_PORT))
                    logger.debug(f"[WIZ550] DISCOVERY_ALL → 255.255.255.255:{WIZ550_PORT} (NIC={bind_ip})")
                    socks.append(s)
                except OSError as e:
                    logger.debug(f"[WIZ550] NIC {bind_ip} skip: {e}")

            # IP Address 유니캐스트 모드: 지정 IP로 직접 전송 (브로드캐스트와 병행)
            if self.target_ip:
                try:
                    su = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    su.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    su.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
                    try:
                        _probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        _probe.connect((self.target_ip, 1))
                        bind_ip = _probe.getsockname()[0]
                        _probe.close()
                    except Exception:
                        bind_ip = ''
                    su.bind((bind_ip, 0))
                    su.sendto(pkt_unicast, (self.target_ip, WIZ550_PORT))
                    logger.debug(f"[WIZ550] DISCOVERY_ALL(unicast) → {self.target_ip}:{WIZ550_PORT} (NIC={bind_ip})")
                    socks.append(su)
                except OSError as e:
                    logger.debug(f"[WIZ550] unicast 소켓 skip: {e}")

            if not socks:
                logger.error("[WIZ550] 사용 가능한 소켓 없음")
                self.search_done.emit([])
                return

            deadline = time.time() + self.timeout
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                ready, _, _ = select.select(socks, [], [], remaining)
                if not ready:
                    break
                for s in ready:
                    try:
                        data, addr = s.recvfrom(512)
                    except OSError:
                        continue

                    info = _parse_discovery_reply(data)
                    if info is None:
                        logger.debug(f"[WIZ550] Discovery 무시: {addr}")
                        continue

                    mac = info['mac']
                    if mac not in results:
                        logger.debug(f"[WIZ550] 발견: {mac} ({addr[0]}) type={info['device_type']} fw={info['fw_str']}")
                        results[mac] = info

        except Exception as e:
            logger.error(f"[WIZ550] Searcher 오류: {e}")
        finally:
            for s in socks:
                try:
                    s.close()
                except OSError:
                    pass

        result_list = list(results.values())
        logger.info(f"[WIZ550] 검색 완료: {len(result_list)}개")
        self.search_done.emit(result_list)


class WIZ550Getter(QThread):
    """
    WIZ550 설정 읽기 스레드.
    GET_INFO(0xB0) → WIZ550Profile 파싱 → get_done 시그널(dict).
    Java 원본: GET_INFO도 255.255.255.255 브로드캐스트 전송 (Pitfall 4).
    D-08: recv[6~7] 재파싱으로 Java MSB 버그 우회.
    """
    get_done = pyqtSignal(dict)  # parse_sr/s2e/web 반환값 (D-01)

    def __init__(self, target_mac: str, device_type: str,
                 iface_ip: str = "", timeout: float = 5.0):
        super().__init__()
        self.target_mac  = target_mac   # "AA:BB:CC:DD:EE:FF"
        self.device_type = device_type  # "WIZ550SR" / "WIZ550S2E" / "WIZ550WEB"
        self.iface_ip    = iface_ip
        self.timeout     = timeout  # D-05: unicast 단일 응답 — 5초

    def run(self):
        result = {}
        bind_ips = []
        try:
            for adapter in ifaddr.get_adapters():
                for ip in adapter.ips:
                    if isinstance(ip.ip, str) and not ip.ip.startswith('127.'):
                        bind_ips.append(ip.ip)
        except Exception:
            pass
        if not bind_ips:
            bind_ips = [self.iface_ip] if self.iface_ip else ['']

        pkt = _build_get_info(self.target_mac)
        socks = []
        try:
            for bind_ip in bind_ips:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
                    s.bind((bind_ip, 0))
                    s.sendto(pkt, ('255.255.255.255', WIZ550_PORT))
                    logger.debug(f"[WIZ550] GET_INFO → {self.target_mac} (NIC={bind_ip})")
                    socks.append(s)
                except OSError as e:
                    logger.debug(f"[WIZ550] Getter NIC {bind_ip} skip: {e}")

            if not socks:
                logger.error(f"[WIZ550] Getter: 사용 가능한 소켓 없음")
                self.get_done.emit({})
                return

            deadline = time.time() + self.timeout
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                ready, _, _ = select.select(socks, [], [], remaining)
                if not ready:
                    logger.warning(f"[WIZ550] GET_INFO 응답 타임아웃: {self.target_mac}")
                    break
                for s in ready:
                    try:
                        data, _ = s.recvfrom(1024)
                    except OSError:
                        continue
                    result = _parse_get_info_reply(data, self.device_type)
                    if result:
                        logger.debug(f"[WIZ550] GET_INFO 파싱 완료: {self.target_mac}")
                        self.get_done.emit(result)
                        return
                    else:
                        logger.warning(f"[WIZ550] GET_INFO 응답 파싱 실패: {self.target_mac}")

        except Exception as e:
            logger.error(f"[WIZ550] Getter 오류: {e}")
        finally:
            for s in socks:
                try:
                    s.close()
                except OSError:
                    pass

        self.get_done.emit(result)


class WIZ550Setter(QThread):
    """
    WIZ550 설정 쓰기 스레드.
    SET_INFO(0xC0) 유니캐스트 → 응답 확인.
    set_done 시그널: True=성공, False=실패 (D-01)
    """
    set_done = pyqtSignal(bool)

    def __init__(self, target_ip: str, target_mac: str, password: str,
                 config_data: bytes, iface_ip: str = "", timeout: float = 5.0):
        super().__init__()
        self.target_ip   = target_ip
        self.target_mac  = target_mac
        self.password    = password
        self.config_data = config_data
        self.iface_ip    = iface_ip
        self.timeout     = timeout  # D-05: 5초

    def run(self):
        success = False
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)

            # 대상 IP 기반 OS 라우팅으로 최적 NIC 자동 선택 — selected_eth가 다른 서브넷이어도 동작
            try:
                _probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                _probe.connect((self.target_ip, 1))
                bind_ip = _probe.getsockname()[0]
                _probe.close()
            except Exception:
                bind_ip = self.iface_ip or ''
            sock.bind((bind_ip, 0))

            pkt = _build_set_info(self.target_mac, self.password, self.config_data)
            sock.sendto(pkt, (self.target_ip, WIZ550_PORT))
            logger.info(f"[WIZ550] SET_INFO → {self.target_ip} MAC={self.target_mac}")

            ready, _, _ = select.select([sock], [], [], self.timeout)
            if ready:
                data, _ = sock.recvfrom(256)
                success = _parse_set_reply(data)
                if success:
                    logger.info(f"[WIZ550] SET_INFO 성공: {self.target_mac}")
                else:
                    logger.warning(f"[WIZ550] SET_INFO 응답 오류: {data[:4]!r}")
            else:
                logger.warning(f"[WIZ550] SET_INFO 응답 타임아웃: {self.target_mac}")

        except Exception as e:
            logger.error(f"[WIZ550] Setter 오류: {e}")
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

        self.set_done.emit(success)


class WIZ550Resetter(QThread):
    """
    WIZ550 리셋 스레드.
    op_code 파라미터로 REMOTE_RESET(0xE0)/FACTORY_RESET(0xF0) 선택 (D-01).
    reset_done 시그널: True=성공, False=실패 (D-01)
    """
    reset_done = pyqtSignal(bool)

    def __init__(self, target_ip: str, target_mac: str, password: str,
                 op_code: int = OP_REMOTE_RESET,
                 iface_ip: str = "", timeout: float = 5.0):
        super().__init__()
        self.target_ip  = target_ip
        self.target_mac = target_mac
        self.password   = password
        self.op_code    = op_code    # OP_REMOTE_RESET 또는 OP_FACTORY_RESET
        self.iface_ip   = iface_ip
        self.timeout    = timeout  # D-05: 5초

    def run(self):
        success = False
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)

            # 대상 IP 기반 OS 라우팅으로 최적 NIC 자동 선택
            try:
                _probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                _probe.connect((self.target_ip, 1))
                bind_ip = _probe.getsockname()[0]
                _probe.close()
            except Exception:
                bind_ip = self.iface_ip or ''
            sock.bind((bind_ip, 0))

            op_name = "FACTORY_RESET" if self.op_code == OP_FACTORY_RESET else "REMOTE_RESET"
            pkt = _build_reset(self.op_code, self.target_mac, self.password)
            sock.sendto(pkt, (self.target_ip, WIZ550_PORT))
            logger.info(f"[WIZ550] {op_name} → {self.target_ip} MAC={self.target_mac}")

            ready, _, _ = select.select([sock], [], [], self.timeout)
            if ready:
                data, _ = sock.recvfrom(256)
                success = _parse_set_reply(data)  # 리셋 응답도 동일 구조
                if success:
                    logger.info(f"[WIZ550] {op_name} 성공: {self.target_mac}")
                else:
                    logger.warning(f"[WIZ550] {op_name} 응답 오류: {data[:4]!r}")
            else:
                logger.warning(f"[WIZ550] {op_name} 응답 타임아웃: {self.target_mac}")

        except Exception as e:
            logger.error(f"[WIZ550] Resetter 오류: {e}")
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

        self.reset_done.emit(success)
