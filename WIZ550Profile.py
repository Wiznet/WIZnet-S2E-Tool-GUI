#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIZ550Profile.py — WIZ550SR/S2E/WEB Config 구조체 변환

3종 장치 Config bytes <-> Python dict 변환.
Java 원본: WIZ550SR_Config.java / WIZ550S2E_Config.java / WIZ550WEB_Config.java

공개 함수:
  parse_sr(data) / build_sr(d)   — SR 162B
  parse_s2e(data) / build_s2e(d) — S2E 162~232B 가변
  parse_web(data) / build_web(d) — WEB 133B

내부 헬퍼:
  _parse_base_162(data) — SR과 S2E 공유 기본 구조 (D-02)

주의:
  - baud_rate: 'I' (unsigned int 4B LE) — Pitfall 3
  - local_port/remote_port: 'H' (unsigned short 2B LE) — Pitfall 3
  - WEB에는 pw_connect 없음 — Pitfall 6
"""

import struct
import ipaddress


# ─────────────────────────────────────────────────────────────────
# WIZ550SR 162B (module_type = [0x02, 0x00, 0x00])
# 04-RESEARCH.md Pattern 5 기준 [VERIFIED: struct.calcsize = 162]
# ─────────────────────────────────────────────────────────────────
SR_FORMAT = (
    '<'
    'H'    # packet_size LE [0~1]
    '3s'   # module_type[3] [2~4]
    '25s'  # module_name[25] [5~29]
    '3s'   # fw_ver[3] [30~32]
    '6s'   # mac[6] [33~38]
    '4s'   # local_ip[4] [39~42]
    '4s'   # gateway[4] [43~46]
    '4s'   # subnet[4] [47~50]
    'B'    # working_mode [51]
    'B'    # state [52]
    '4s'   # remote_ip[4] [53~56]
    'H'    # local_port LE [57~58]
    'H'    # remote_port LE [59~60]
    'H'    # inactivity LE [61~62]
    'H'    # reconnection LE [63~64]
    'H'    # packing_time LE [65~66]
    'B'    # packing_size [67]
    '4s'   # packing_delimiter[4] [68~71]
    'B'    # packing_delimiter_length [72]
    'B'    # packing_data_appendix [73]
    'I'    # baud_rate 4B LE [74~77]  <- 'I' (unsigned) Pitfall 3
    'B'    # data_bits [78]
    'B'    # parity [79]
    'B'    # stop_bits [80]
    'B'    # flow_control [81]
    '10s'  # pw_setting[10] [82~91]
    '10s'  # pw_connect[10] [92~101]
    'B'    # dhcp_use [102]
    'B'    # dns_use [103]
    '4s'   # dns_server_ip[4] [104~107]
    '50s'  # dns_domain_name[50] [108~157]
    'B'    # serial_command [158]
    '3s'   # serial_trigger[3] [159~161]
)
SR_SIZE = 162
assert struct.calcsize(SR_FORMAT) == SR_SIZE, \
    f"SR struct 크기 오류: {struct.calcsize(SR_FORMAT)} != {SR_SIZE}"


# ─────────────────────────────────────────────────────────────────
# WIZ550WEB 133B (module_type = [0x01, 0x02, 0x00])
# ─────────────────────────────────────────────────────────────────
WEB_FORMAT = (
    '<'
    'H'    # packet_size LE [0~1]
    '3s'   # module_type[3] [2~4]
    '25s'  # module_name[25] [5~29]
    '3s'   # fw_ver[3] [30~32]
    '6s'   # mac[6] [33~38]
    '4s'   # local_ip[4] [39~42]
    '4s'   # gateway[4] [43~46]
    '4s'   # subnet[4] [47~50]
    'I'    # uart0_baud_rate 4B LE [51~54]  <- 'I' (unsigned)
    'B'    # uart0_data_bits [55]
    'B'    # uart0_parity [56]
    'B'    # uart0_stop_bits [57]
    'B'    # uart0_flow_control [58]
    'I'    # uart1_baud_rate 4B LE [59~62]
    'B'    # uart1_data_bits [63]
    'B'    # uart1_parity [64]
    'B'    # uart1_stop_bits [65]
    'B'    # uart1_flow_control [66]
    '10s'  # pw_setting[10] [67~76]
    'B'    # dhcp_use [77]
    'B'    # dns_use [78]
    '4s'   # dns_server_ip[4] [79~82]
    '50s'  # dns_domain_name[50] [83~132]
)
WEB_SIZE = 133
assert struct.calcsize(WEB_FORMAT) == WEB_SIZE, \
    f"WEB struct 크기 오류: {struct.calcsize(WEB_FORMAT)} != {WEB_SIZE}"


# ─────────────────────────────────────────────────────────────────
# WIZ550S2E 확장 포맷
# ─────────────────────────────────────────────────────────────────
S2E_BASE_SIZE = SR_SIZE  # 기본 162B — SR과 동일 구조

MQTT_FORMAT = '<10s10s25s25s'   # mqtt_user(10)+mqtt_pw(10)+pub_topic(25)+sub_topic(25)
MQTT_SIZE = 70
assert struct.calcsize(MQTT_FORMAT) == MQTT_SIZE, \
    f"MQTT struct 크기 오류: {struct.calcsize(MQTT_FORMAT)} != {MQTT_SIZE}"

MODBUS_FORMAT = '<BB'            # modbus_use(1) + modbus_mode(1)
MODBUS_SIZE = 2
assert struct.calcsize(MODBUS_FORMAT) == MODBUS_SIZE


# ─────────────────────────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────────────────────────

def _ip_bytes_to_str(ip4: bytes) -> str:
    return '.'.join(str(b) for b in ip4)


def _ip_str_to_bytes(ip_str: str) -> bytes:
    try:
        return ipaddress.IPv4Address(ip_str.strip()).packed
    except ValueError:
        return b'\x00\x00\x00\x00'


def _cstr_to_str(raw: bytes) -> str:
    return raw.rstrip(b'\x00').decode('ascii', errors='replace')


def _str_to_cstr(s: str, length: int) -> bytes:
    return s.encode('ascii', errors='replace')[:length].ljust(length, b'\x00')


def _mac_str_to_bytes(mac_str: str) -> bytes:
    return bytes(int(x, 16) for x in mac_str.replace('-', ':').split(':'))[:6]


# ─────────────────────────────────────────────────────────────────
# 내부 헬퍼 (D-02: SR과 S2E 공유)
# ─────────────────────────────────────────────────────────────────

def _parse_base_162(data: bytes) -> dict:
    """
    SR/S2E 공유 162B 기본 구조 파싱 내부 헬퍼.
    data는 system_info (packet_size[2] 포함, 총 162B).
    len(data) < SR_SIZE -> 빈 dict 반환 (예외 없음).
    """
    if len(data) < SR_SIZE:
        return {}
    try:
        fields = struct.unpack(SR_FORMAT, data[:SR_SIZE])
    except struct.error:
        return {}

    (packet_size, module_type, module_name, fw_ver,
     mac, local_ip, gateway, subnet,
     working_mode, state, remote_ip,
     local_port, remote_port, inactivity, reconnection,
     packing_time, packing_size, packing_delimiter,
     packing_delimiter_length, packing_data_appendix,
     baud_rate,
     data_bits, parity, stop_bits, flow_control,
     pw_setting, pw_connect,
     dhcp_use, dns_use, dns_server_ip, dns_domain_name,
     serial_command, serial_trigger) = fields

    return {
        'packet_size':              packet_size,
        'module_type':              module_type.hex(),
        'module_name':              _cstr_to_str(module_name),
        'fw_ver':                   fw_ver,
        'fw_str':                   f'{fw_ver[0]}.{fw_ver[1]}.{fw_ver[2]}',
        'mac':                      ':'.join(f'{b:02X}' for b in mac),
        'local_ip':                 _ip_bytes_to_str(local_ip),
        'gateway':                  _ip_bytes_to_str(gateway),
        'subnet':                   _ip_bytes_to_str(subnet),
        'working_mode':             working_mode,
        'state':                    state,
        'remote_ip':                _ip_bytes_to_str(remote_ip),
        'local_port':               local_port,
        'remote_port':              remote_port,
        'inactivity':               inactivity,
        'reconnection':             reconnection,
        'packing_time':             packing_time,
        'packing_size':             packing_size,
        'packing_delimiter':        packing_delimiter,
        'packing_delimiter_length': packing_delimiter_length,
        'packing_data_appendix':    packing_data_appendix,
        'baud_rate':                baud_rate,
        'data_bits':                data_bits,
        'parity':                   parity,
        'stop_bits':                stop_bits,
        'flow_control':             flow_control,
        'pw_setting':               _cstr_to_str(pw_setting),
        'pw_connect':               _cstr_to_str(pw_connect),
        'dhcp_use':                 dhcp_use,
        'dns_use':                  dns_use,
        'dns_server_ip':            _ip_bytes_to_str(dns_server_ip),
        'dns_domain_name':          _cstr_to_str(dns_domain_name),
        'serial_command':           serial_command,
        'serial_trigger':           serial_trigger,
        '_proto':                   'wiz550',
    }


# ─────────────────────────────────────────────────────────────────
# WIZ550SR — 162B
# ─────────────────────────────────────────────────────────────────

def parse_sr(data: bytes) -> dict:
    """WIZ550SR 162B -> dict. len 부족 시 빈 dict 반환."""
    d = _parse_base_162(data)
    if d:
        d['device_type'] = 'WIZ550SR'
    return d


def build_sr(d: dict) -> bytes:
    """dict -> WIZ550SR 162B bytes. 왕복 검증: build_sr(parse_sr(data)) == data[:162]"""
    raw = struct.pack(
        SR_FORMAT,
        d.get('packet_size', SR_SIZE),
        bytes.fromhex(d.get('module_type', '020000'))[:3],
        _str_to_cstr(d.get('module_name', ''), 25),
        d.get('fw_ver', b'\x00\x00\x00')[:3],
        _mac_str_to_bytes(d.get('mac', '00:00:00:00:00:00')),
        _ip_str_to_bytes(d.get('local_ip', '0.0.0.0')),
        _ip_str_to_bytes(d.get('gateway', '0.0.0.0')),
        _ip_str_to_bytes(d.get('subnet', '255.255.255.0')),
        d.get('working_mode', 0),
        d.get('state', 0),
        _ip_str_to_bytes(d.get('remote_ip', '0.0.0.0')),
        d.get('local_port', 0),
        d.get('remote_port', 0),
        d.get('inactivity', 0),
        d.get('reconnection', 0),
        d.get('packing_time', 0),
        d.get('packing_size', 0),
        d.get('packing_delimiter', b'\x00\x00\x00\x00')[:4],
        d.get('packing_delimiter_length', 0),
        d.get('packing_data_appendix', 0),
        d.get('baud_rate', 115200),
        d.get('data_bits', 8),
        d.get('parity', 0),
        d.get('stop_bits', 1),
        d.get('flow_control', 0),
        _str_to_cstr(d.get('pw_setting', ''), 10),
        _str_to_cstr(d.get('pw_connect', ''), 10),
        d.get('dhcp_use', 0),
        d.get('dns_use', 0),
        _ip_str_to_bytes(d.get('dns_server_ip', '0.0.0.0')),
        _str_to_cstr(d.get('dns_domain_name', ''), 50),
        d.get('serial_command', 0),
        d.get('serial_trigger', b'\x00\x00\x00')[:3],
    )
    assert len(raw) == SR_SIZE
    return raw


# ─────────────────────────────────────────────────────────────────
# WIZ550WEB — 133B (pw_connect 없음 — Pitfall 6)
# ─────────────────────────────────────────────────────────────────

def parse_web(data: bytes) -> dict:
    """WIZ550WEB 133B -> dict. len 부족 시 빈 dict 반환."""
    if len(data) < WEB_SIZE:
        return {}
    try:
        fields = struct.unpack(WEB_FORMAT, data[:WEB_SIZE])
    except struct.error:
        return {}

    (packet_size, module_type, module_name, fw_ver,
     mac, local_ip, gateway, subnet,
     uart0_baud_rate, uart0_data_bits, uart0_parity, uart0_stop_bits, uart0_flow_control,
     uart1_baud_rate, uart1_data_bits, uart1_parity, uart1_stop_bits, uart1_flow_control,
     pw_setting, dhcp_use, dns_use, dns_server_ip, dns_domain_name) = fields

    return {
        'packet_size':          packet_size,
        'module_type':          module_type.hex(),
        'module_name':          _cstr_to_str(module_name),
        'fw_ver':               fw_ver,
        'fw_str':               f'{fw_ver[0]}.{fw_ver[1]}.{fw_ver[2]}',
        'mac':                  ':'.join(f'{b:02X}' for b in mac),
        'local_ip':             _ip_bytes_to_str(local_ip),
        'gateway':              _ip_bytes_to_str(gateway),
        'subnet':               _ip_bytes_to_str(subnet),
        'uart0_baud_rate':      uart0_baud_rate,
        'uart0_data_bits':      uart0_data_bits,
        'uart0_parity':         uart0_parity,
        'uart0_stop_bits':      uart0_stop_bits,
        'uart0_flow_control':   uart0_flow_control,
        'uart1_baud_rate':      uart1_baud_rate,
        'uart1_data_bits':      uart1_data_bits,
        'uart1_parity':         uart1_parity,
        'uart1_stop_bits':      uart1_stop_bits,
        'uart1_flow_control':   uart1_flow_control,
        'pw_setting':           _cstr_to_str(pw_setting),
        # pw_connect 없음 (WEB 구조체 미포함 — Pitfall 6)
        'dhcp_use':             dhcp_use,
        'dns_use':              dns_use,
        'dns_server_ip':        _ip_bytes_to_str(dns_server_ip),
        'dns_domain_name':      _cstr_to_str(dns_domain_name),
        'device_type':          'WIZ550WEB',
        '_proto':               'wiz550',
    }


def build_web(d: dict) -> bytes:
    """dict -> WIZ550WEB 133B bytes. 왕복 검증: build_web(parse_web(data)) == data[:133]"""
    raw = struct.pack(
        WEB_FORMAT,
        d.get('packet_size', WEB_SIZE),
        bytes.fromhex(d.get('module_type', '010200'))[:3],
        _str_to_cstr(d.get('module_name', ''), 25),
        d.get('fw_ver', b'\x00\x00\x00')[:3],
        _mac_str_to_bytes(d.get('mac', '00:00:00:00:00:00')),
        _ip_str_to_bytes(d.get('local_ip', '0.0.0.0')),
        _ip_str_to_bytes(d.get('gateway', '0.0.0.0')),
        _ip_str_to_bytes(d.get('subnet', '255.255.255.0')),
        d.get('uart0_baud_rate', 9600),
        d.get('uart0_data_bits', 8),
        d.get('uart0_parity', 0),
        d.get('uart0_stop_bits', 1),
        d.get('uart0_flow_control', 0),
        d.get('uart1_baud_rate', 9600),
        d.get('uart1_data_bits', 8),
        d.get('uart1_parity', 0),
        d.get('uart1_stop_bits', 1),
        d.get('uart1_flow_control', 0),
        _str_to_cstr(d.get('pw_setting', ''), 10),
        d.get('dhcp_use', 0),
        d.get('dns_use', 0),
        _ip_str_to_bytes(d.get('dns_server_ip', '0.0.0.0')),
        _str_to_cstr(d.get('dns_domain_name', ''), 50),
    )
    assert len(raw) == WEB_SIZE
    return raw


# ─────────────────────────────────────────────────────────────────
# WIZ550S2E — 162~232B 가변 (D-04 이중 판별)
# ─────────────────────────────────────────────────────────────────

def parse_s2e(data: bytes) -> dict:
    """
    WIZ550S2E 가변 구조 -> dict.

    D-04 이중 판별 (데이터 길이 우선 + fw_ver[1] 홀짝 검증):
      len>=232 AND fw_ver[1]%2!=0 -> MQTT 70B 확장 추가 (총 232B)
      len>=164 AND fw_ver[1]%2==0 -> Modbus 2B 확장 추가 (총 164B)
      기본 -> s2e_variant='base' (162B)

    주의: 데이터 길이가 주방어선 (트런케이션 오파싱 방지).
          fw_ver[1] 홀짝은 검증용 보조 조건.
    """
    d = _parse_base_162(data)
    if not d:
        return {}
    d['device_type'] = 'WIZ550S2E'

    fw_ver = d.get('fw_ver', b'\x00\x00\x00')

    # D-04: 데이터 길이 우선 -> fw_ver[1] 홀짝 검증
    if len(data) >= S2E_BASE_SIZE + MQTT_SIZE and (fw_ver[1] % 2 != 0):
        # MQTT 70B 확장 파싱
        try:
            ext = data[S2E_BASE_SIZE:S2E_BASE_SIZE + MQTT_SIZE]
            mqtt_user, mqtt_pw, mqtt_pub, mqtt_sub = struct.unpack(MQTT_FORMAT, ext)
            d['mqtt_user']      = _cstr_to_str(mqtt_user)
            d['mqtt_pw']        = _cstr_to_str(mqtt_pw)
            d['mqtt_pub_topic'] = _cstr_to_str(mqtt_pub)
            d['mqtt_sub_topic'] = _cstr_to_str(mqtt_sub)
            d['s2e_variant']    = 'mqtt'
        except struct.error:
            d['s2e_variant'] = 'base'
    elif len(data) >= S2E_BASE_SIZE + MODBUS_SIZE and (fw_ver[1] % 2 == 0):
        # Modbus 2B 확장 파싱
        try:
            ext = data[S2E_BASE_SIZE:S2E_BASE_SIZE + MODBUS_SIZE]
            modbus_use, modbus_mode = struct.unpack(MODBUS_FORMAT, ext)
            d['modbus_use']  = modbus_use
            d['modbus_mode'] = modbus_mode
            d['s2e_variant'] = 'modbus'
        except struct.error:
            d['s2e_variant'] = 'base'
    else:
        d['s2e_variant'] = 'base'

    return d


def build_s2e(d: dict) -> bytes:
    """
    dict -> WIZ550S2E bytes (가변 길이).
    s2e_variant에 따라 162B/164B/232B 반환.

    Pitfall 5: fw_ver[0]는 원본값 유지 (Java updateFromPanel에서 주석 처리됨).
    """
    # 기본 162B 빌드 (SR_FORMAT 재사용 — module_type만 S2E로 변경)
    raw = struct.pack(
        SR_FORMAT,
        d.get('packet_size', S2E_BASE_SIZE),
        bytes.fromhex(d.get('module_type', '000000'))[:3],  # S2E: [0x00, 0x00, 0x00]
        _str_to_cstr(d.get('module_name', ''), 25),
        d.get('fw_ver', b'\x00\x00\x00')[:3],  # Pitfall 5: fw_ver[0] 원본값 유지
        _mac_str_to_bytes(d.get('mac', '00:00:00:00:00:00')),
        _ip_str_to_bytes(d.get('local_ip', '0.0.0.0')),
        _ip_str_to_bytes(d.get('gateway', '0.0.0.0')),
        _ip_str_to_bytes(d.get('subnet', '255.255.255.0')),
        d.get('working_mode', 0),
        d.get('state', 0),
        _ip_str_to_bytes(d.get('remote_ip', '0.0.0.0')),
        d.get('local_port', 0),
        d.get('remote_port', 0),
        d.get('inactivity', 0),
        d.get('reconnection', 0),
        d.get('packing_time', 0),
        d.get('packing_size', 0),
        d.get('packing_delimiter', b'\x00\x00\x00\x00')[:4],
        d.get('packing_delimiter_length', 0),
        d.get('packing_data_appendix', 0),
        d.get('baud_rate', 115200),
        d.get('data_bits', 8),
        d.get('parity', 0),
        d.get('stop_bits', 1),
        d.get('flow_control', 0),
        _str_to_cstr(d.get('pw_setting', ''), 10),
        _str_to_cstr(d.get('pw_connect', ''), 10),
        d.get('dhcp_use', 0),
        d.get('dns_use', 0),
        _ip_str_to_bytes(d.get('dns_server_ip', '0.0.0.0')),
        _str_to_cstr(d.get('dns_domain_name', ''), 50),
        d.get('serial_command', 0),
        d.get('serial_trigger', b'\x00\x00\x00')[:3],
    )
    assert len(raw) == S2E_BASE_SIZE

    variant = d.get('s2e_variant', 'base')
    if variant == 'mqtt':
        # MQTT 70B 확장 추가
        ext = struct.pack(
            MQTT_FORMAT,
            _str_to_cstr(d.get('mqtt_user', ''), 10),
            _str_to_cstr(d.get('mqtt_pw', ''), 10),
            _str_to_cstr(d.get('mqtt_pub_topic', ''), 25),
            _str_to_cstr(d.get('mqtt_sub_topic', ''), 25),
        )
        assert len(ext) == MQTT_SIZE
        return raw + ext  # 232B
    elif variant == 'modbus':
        # Modbus 2B 확장 추가
        ext = struct.pack(MODBUS_FORMAT,
                          d.get('modbus_use', 0),
                          d.get('modbus_mode', 0))
        return raw + ext  # 164B
    else:
        return raw  # 162B
