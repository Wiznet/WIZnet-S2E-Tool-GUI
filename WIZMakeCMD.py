# -*- coding: utf-8 -*-
from packaging.version import Version, InvalidVersion

"""
Make Serial command
"""
from utils import logger

import re

# Supported devices
ONE_PORT_DEV = [
    "WIZ750SR",
    "WIZ750SR-1xx",
    # "WIZ750SR-100",
    # "WIZ750SR-105",
    # "WIZ750SR-110",
    "WIZ750SR-T1L",
    "WIZ107SR",
    "WIZ108SR",
    "W7500-S2E",
    "W7500P-S2E",
]
SECURITY_DEVICE = [
    "WIZ510SSL",
    "WIZ5XXSR-RP",
    "WIZ5XXSR-RP_E-SAVE",
    "W55RP20-S2E",
    "W55RP20-S2E-2CH",
    "W232N",
    "IP20",
]
TWO_PORT_DEV = ["WIZ752SR-12x", "WIZ752SR-120", "WIZ752SR-125"]

"""
Command List
"""
# for pre-search
cmd_presearch = ["MC", "VR", "MN", "ST", "IM", "OP", "LI", "SM", "GW"]

# Command for bootloader
cmd_boot = ["MC", "VR", "MN", "ST", "IM", "OP", "LI", "SM", "GW", "SP", "DS"]  # cmd_presearch
# cmd_boot = ["MC", "VR", "MN", "ST", "IM", "OP", "LI", "SM", "GW"]  # cmd_presearch

# Command for each device
cmd_ch1 = [
    "MC", "VR", "MN", "UN", "ST", "IM", "OP", "CP", "DG", 
    "KA", "KI", "KE", "RI", "LI", "SM", "GW", "DS", "PI", "PP",
    "DX", "DP", "DI", "DW", "DH", "LP", "RP", "RH", "BR", "DB",
    "PR", "SB", "FL", "IT", "PT", "PS", "PD", "TE", "SS", "NP",
    "SP"
]
# WIZ107SR / WIZ108SR 전용 커맨드 목록
# refactored/specs/devices/WIZ107SR.yaml search_cmd_order 기준
# cmd_ch1 대비 추가: DD(DDNS Enable), PO(Network Protocol)
cmd_107sr = [
    "MC", "VR", "MN", "UN", "ST", "IM", "OP", "DD", "CP", "PO", "DG",
    "KA", "KI", "KE", "RI", "LI", "SM", "GW", "DS",
    "PI", "PP", "DX", "DP", "DI", "DW", "DH", "LP", "RP", "RH",
    "BR", "DB", "PR", "SB", "FL", "IT", "PT", "PS", "PD",
    "TE", "SS", "NP", "SP"
]

cmd_wiz75xsr = ["S0", "S1"]
cmd_added = ["SC", "TR"]  # for WIZ750SR F/W version 1.2.0 or later
cmd_ch2 = [
    "QS", "QO", "QH", "QP", "QL", "RV", "RA", "RE", "RR", "EN",
    "RS", "EB", "ED", "EP", "ES", "EF", "E0", "E1", "NT", "NS",
    "ND"
]

# WIZ752SR-12x 개별 장치 조회(Phase 3)는 세 요청으로 나눠 보낸다.
#
# 장치 응답 버퍼 gSEGCPREP 는 CONFIG_BUF_SIZE(512, W7500 계열 common.h) 인데 펌웨어가
# 길이를 대조하지 않고 strlen 만큼 보낸다(segcp.c:1443). 61~64개를 한 번에 물으면
# 응답이 499~531B(2026-08-31~09-01 실측) 라 값 몇 개만 길어져도 넘치고, 넘친 바이트는
# UART 송신 링버퍼 포인터(txring[0].data)를 덮는다. 커맨드 몇 개를 빼는 것으로는
# 부족하다 — RH/QH 가 같은 도메인을 돌려주므로 도메인 19자만 돼도 다시 넘는다.
#
# 그래서 한 요청에 묻는 양 자체를 줄인다. 응답 크기를 예측하는 것이 아니라 상한을
# 구조적으로 낮추는 것이라, 펌웨어 값이 바뀌어도 여유가 흡수한다. 청크마다 MA/PW
# 헤더가 붙고, MC 를 넣어 응답을 같은 장치로 합친다. 실측 프로파일 기준 청크별 응답은
# 약 250 / 150 / 195B 이고 도메인 39자에서도 최대 250B 다
# (tests/test_segcp_reply_overflow.py 가 384B 상한을 고정한다).
#
# 앞 두 청크는 cmd_ch1 을 LP(채널0 Local port) 앞에서 자른 것이라 cmd_ch1 이 바뀌어도
# 따라간다. S0/S1(상태 핀 값)은 설정툴이 읽는 곳이 없어 넣지 않는다. SC 는 Options
# 탭 라디오가 읽는다.
_ch0_serial_start = cmd_ch1.index("LP")
cmd_2p_chunk_network = cmd_ch1[:_ch0_serial_start]                 # 장치·네트워크 공통 (MC 포함)
cmd_2p_chunk_ch0 = ["MC"] + cmd_ch1[_ch0_serial_start:]            # 채널0 시리얼·옵션
cmd_2p_chunk_ch1 = ["MC"] + cmd_ch2 + ["SC"]                       # 채널1 + 상태 핀 모드
cmd_2p_search_chunks = [cmd_2p_chunk_network, cmd_2p_chunk_ch0, cmd_2p_chunk_ch1]

# WIZ752SR-12x SET 확인 쿼리 전용 목록.
#
# 완료 판정(get_setting_result 의 len(mc)==17)에 MC 가 필요하므로 cmd_ch2 앞에 MC 만 붙인다.
# cmd_2p_default(전체 64개)를 쓰면 요청이 627바이트가 되어 펌웨어의
# CONFIG_BUF_SIZE(512, WIZ752SR-12x/WIZ750SR common.h)를 넘겨 gSEGCPREQ 버퍼를
# 오버플로시킨다. 실측: 오프셋 ~512 지점의 토큰부터 파싱이 깨지며 엉뚱한 커맨드명으로
# INVALIDPARAM/NOTAVAIL 이 반환됐다. (2026-08-18, 실기기 확인)
cmd_2p_setconfirm = ["MC"] + cmd_ch2

# for expansion GPIO
cmd_gpio_4pin = ["CA", "CB", "CC", "CD", "GA", "GB", "GC", "GD"]  
cmd_gpio_2pin = ["CA", "CB", "GA", "GB"]

# Security device base commands
cmd_security_base = [
    "MC", "VR", "MN", "IM", "OP", "CP", "DG", "KA", "KI", "KE",
    "RI", "LI", "SM", "GW", "DS", "DH", "LP", "RP", "RH", "BR",
    "DB", "PR", "SB", "FL", "IT", "PT", "PS", "PD", "TE", "SS",
    "NP", "SP", "UN", "ST", "EC", "SC", "TR", "QU", "QP", "QC",
    "QK", "PU", "U0", "U1", "U2", "QO", "RC", "CE"
]

# WIZ510SSL commands
cmd_wiz510ssl_added = ['BA']

# 2022.05.10
# WIZ5XXSR-RP added commands
# 전역에서 "PO" 삭제 #36
cmd_wiz5xxsr_added = ['SO', 'UF']

# W55RP20-S2E specific commands
cmd_w55rp20_added = ['SD', 'DD', 'SE']  # Send Data at Connection, Send Data at Disconnection, Ethernet Data Connection Condition

# W55RP20-S2E-2CH channel 1 specific commands
cmd_w55rp20_2ch_ch1 = [
    'QS',  # Channel 1 status
    'EN',  # Channel 1 UART interface
    'AO',  # Channel 1 operation mode (extended)
    'QL',  # Channel 1 local port
    'QH',  # Channel 1 remote host
    'AP',  # Channel 1 remote port
    'EB',  # Channel 1 baud rate
    'ED',  # Channel 1 data bit
    'EP',  # Channel 1 parity
    'ES',  # Channel 1 stop bit
    'EF',  # Channel 1 flow control
    'ND',  # Channel 1 packing delimiter
    'NS',  # Channel 1 packing size
    'AT',  # Channel 1 packing time
    'RV',  # Channel 1 inactivity timer
    'RA',  # Channel 1 keep-alive enable
    'RS',  # Channel 1 keep-alive initial interval
    'RE',  # Channel 1 keep-alive retry interval
    'RR',  # Channel 1 reconnection interval
    'RO',  # Channel 1 SSL timeout
    'EO',  # Channel 1 Modbus option
    'RD',  # Channel 1 serial connected data
    'RF',  # Channel 1 serial disconnected data
    'EE',  # Channel 1 ethernet connected data
]

# WIZ5XXSR-RP_E-SAVE commands (MQTT Subscribe topic 4~10)
# E-SAVE 지원은 `E-Save` 브랜치에서만 유지한다. 이 계열에서 비활성인 것이
# 정상이며, 아래 search()/setcommand() 안의 주석 블록도 같은 이유다.
# 되살리려면 커맨드 정의는 specs/ 가 주인이므로 여기가 아니라 그쪽부터 손대야
# 한다. 요구사항·재구현 절차:
# research/2026-08-25-esave-branch-requirements-extraction.md
#cmd_wiz5xxsr_esave = ['U3', 'U4', 'U5', 'U6', 'U7', 'U8', 'U9']


"""
Command Set
"""
cmd_1p_boot = cmd_boot
cmd_1p_default = cmd_ch1
cmd_1p_advanced = cmd_ch1 + cmd_wiz75xsr + cmd_added
cmd_2p_default = cmd_ch1 + cmd_ch2

# Security devices
cmd_wiz510ssl = cmd_security_base + cmd_wiz510ssl_added
cmd_wiz5xxsr = cmd_security_base + cmd_wiz5xxsr_added
cmd_w55rp20 = cmd_security_base + cmd_wiz5xxsr_added + cmd_w55rp20_added
cmd_w55rp20_2ch = cmd_w55rp20 + cmd_w55rp20_2ch_ch1


def _safe_version(v: str) -> Version:
    try:
        return Version(v)
    except InvalidVersion:
        # PEP 440 비표준 접미사(예: "1.2.2wiz") → 숫자 부분만 추출
        m = re.match(r'[\d.]+', v)
        return Version(m.group(0).rstrip('.')) if m else Version("0")


def version_compare(version1: str, version2: str) -> int:
    """버전을 비교해서 앞이 크면 1 뒤가 크면 -1 같으면 0을 반환
    Args:
        version1 (str): 첫번째 버전
        version2 (str): 두번째 버전
    """
    if not version1 or not version2:
        return 0
    v1, v2 = _safe_version(version1), _safe_version(version2)
    return 0 if v1 == v2 else (-1 if v1 < v2 else 1)


class WIZMakeCMD:
    def __init__(self):
        self.logger = logger

    def _modbus_command(self, devname: str, version: str):
        """Return the Modbus command keyword supported by the device, if any."""
        if not devname or not version:
            return None

        # New firmware for WIZ750SR family and WIZ750SR-T1L uses the MB parameter
        if ("WIZ750" in devname or "WIZ750SR-T1L" in devname) and version_compare(version, "1.4.4") >= 0:
            return "MB"

        # Existing security product families continue to rely on PO
        if "WIZ5XXSR" in devname and version_compare("1.0.8", version) <= 0:
            return "PO"
        if "W55RP20" in devname or "W232N" in devname or "IP20" in devname:
            return "PO"

        return None

    def _append_modbus_command(self, cmd_list, devname: str, version: str):
        """Append the appropriate Modbus command if the target device supports it."""
        modbus_cmd = self._modbus_command(devname, version)
        if not modbus_cmd:
            return

        # Avoid duplicates if the command was already injected elsewhere
        if any(entry[0] == modbus_cmd for entry in cmd_list):
            return

        cmd_list.append([modbus_cmd, ""])

    def make_header(self, mac_addr, idcode, devname="", set_pw=""):
        """
        Common command set
        """
        cmd_header = []
        cmd_header.append(["MA", mac_addr])
        cmd_header.append(["PW", idcode])
        # print('reset', mac_addr, idcode, set_pw, devname)
        return cmd_header

    def presearch(self, mac_addr, idcode):
        cmd_list = self.make_header(mac_addr, idcode)
        # Search All Devices on the network
        # 장치 검색 시 필요 정보 Get
        for cmd in cmd_presearch:
            cmd_list.append([cmd, ""])
        return cmd_list

    def search_chunks(self, mac_addr, idcode, devname, version, devstatus=None):
        """개별 장치 조회 요청 **목록**. 요청 하나가 아니라 여러 개일 수 있다.

        2포트 장치(WIZ752SR-12x 계열)는 cmd_2p_search_chunks 대로 세 요청으로 나눈다 —
        한 번에 물으면 응답이 장치 버퍼 512B 를 넘긴다(그 목록의 주석 참조).
        그 외 장치는 search() 결과 하나짜리 목록이다.
        호출자는 청크를 순서대로 보내고 응답을 합친다: WIZMSGHandler.for_device_query().
        """
        if devname in TWO_PORT_DEV or "752" in devname:
            return [
                self.make_header(mac_addr, idcode) + [[cmd, ""] for cmd in chunk]
                for chunk in cmd_2p_search_chunks
            ]
        return [self.search(mac_addr, idcode, devname, version, devstatus)]

    def search(self, mac_addr, idcode, devname, version, devstatus=None):
        # Search All Devices on the network
        # print('search()', mac_addr, idcode, devname, version)
        #
        # 2포트 장치는 이 한 요청의 응답이 장치 버퍼(512B)를 넘긴다.
        # 개별 장치 조회에는 search_chunks() 를 쓸 것.
        cmd_list = self.make_header(mac_addr, idcode)

        if devname in ONE_PORT_DEV:
            # WIZ107SR/WIZ108SR: DD(DDNS Enable), PO(Network Protocol) 포함 전용 목록
            if "WIZ107SR" in devname or "WIZ108SR" in devname:
                for cmd in cmd_107sr:
                    cmd_list.append([cmd, ""])
            else:
                # WIZ750SR series / W7500(P)-S2E
                if version_compare("1.2.0", version) <= 0:
                    for cmd in cmd_1p_advanced:
                        cmd_list.append([cmd, ""])
                else:
                    for cmd in cmd_1p_default:
                        cmd_list.append([cmd, ""])
        elif devname in TWO_PORT_DEV or "752" in devname:
            for cmd in cmd_2p_default:
                cmd_list.append([cmd, ""])
        elif devname in SECURITY_DEVICE:
            # self.logger.info(f'[Search] Security device: {devname}')
            if 'WIZ510SSL' in devname:
                for cmd in cmd_wiz510ssl:
                    cmd_list.append([cmd, ""])
            elif 'WIZ5XXSR' in devname:
                self.logger.debug(f"search::devstatus={devstatus}")
                if devstatus == 'BOOT':
                    for cmd in cmd_1p_boot:
                        cmd_list.append([cmd, ""])
                    self.logger.debug(f"search::cmd_list={cmd_list}")
                    return cmd_list
                for cmd in cmd_wiz5xxsr:
                    cmd_list.append([cmd, ""])
                self.logger.debug(f"search::cmd_list2={cmd_list}")
                # Commands for E-SAVE — `E-Save` 브랜치 전용 (위 cmd_wiz5xxsr_esave 주석 참조)
                #if 'E-SAVE' in devname:
                #    for cmd in cmd_wiz5xxsr_esave:
                #        cmd_list.append([cmd, ""])
            elif 'W55RP20-S2E-2CH' in devname:
                self.logger.debug(f"search::devstatus={devstatus}")
                if devstatus == 'BOOT':
                    for cmd in cmd_1p_boot:
                        cmd_list.append([cmd, ""])
                    self.logger.debug(f"search::cmd_list={cmd_list}")
                    return cmd_list

                if version_compare(version, "1.1.8") >= 0:
                    temp_cmd_w55rp20_2ch = cmd_w55rp20_2ch
                else:
                    # 하위 버전은 채널1 확장 명령 대신 기본 명령으로 구성
                    temp_cmd_w55rp20_2ch = cmd_security_base + cmd_wiz5xxsr_added
                for cmd in temp_cmd_w55rp20_2ch:
                    cmd_list.append([cmd, ""])
                self.logger.debug(f"search::cmd_list2={cmd_list}")

            elif 'W55RP20-S2E' in devname:
                self.logger.debug(f"search::devstatus={devstatus}")
                if devstatus == 'BOOT':
                    for cmd in cmd_1p_boot:
                        cmd_list.append([cmd, ""])
                    self.logger.debug(f"search::cmd_list={cmd_list}")
                    return cmd_list
                # W55RP20-S2E는 SD 명령어 포함 (버전 1.1.8 이상인 경우에만)
                if version_compare(version, "1.1.8") >= 0:
                    temp_cmd_w55rp20 = cmd_w55rp20
                else:
                    temp_cmd_w55rp20 = cmd_security_base + cmd_wiz5xxsr_added
                for cmd in temp_cmd_w55rp20:
                    cmd_list.append([cmd, ""])
                self.logger.debug(f"search::cmd_list2={cmd_list}")
            elif 'W232N' in devname or 'IP20' in devname:
                self.logger.debug(f"search::devstatus={devstatus}")
                if devstatus == 'BOOT':
                    for cmd in cmd_1p_boot:
                        cmd_list.append([cmd, ""])
                    self.logger.debug(f"search::cmd_list={cmd_list}")
                    return cmd_list
                # W232N과 IP20도 SD, DD, SE 명령어 지원 (버전 1.1.8 이상인 경우에만)
                if version_compare(version, "1.1.8") >= 0:
                    temp_cmd_wiz5xxsr = cmd_wiz5xxsr + cmd_w55rp20_added
                else:
                    temp_cmd_wiz5xxsr = cmd_wiz5xxsr
                for cmd in temp_cmd_wiz5xxsr:
                    cmd_list.append([cmd, ""])
                self.logger.debug(f"search::cmd_list2={cmd_list}")
                # Commands for E-SAVE — `E-Save` 브랜치 전용 (위 cmd_wiz5xxsr_esave 주석 참조)
                #if 'E-SAVE' in devname:
                #    for cmd in cmd_wiz5xxsr_esave:
                #        cmd_list.append([cmd, ""])
        else:
            pass
        self._append_modbus_command(cmd_list, devname, version)
        # print("search()", cmd_list)
        return cmd_list

    def get_gpiovalue(self, mac_addr, idcode, devname):
        cmd_list = self.make_header(mac_addr, idcode)
        if 'WIZ5XX' in devname:
            for cmd in cmd_gpio_2pin:
                cmd_list.append([cmd, ""])
        else:
            for cmd in cmd_gpio_4pin:
                cmd_list.append([cmd, ""])
        self.logger.debug(f"devname={devname}, cmds={cmd_list}")
        return cmd_list

    # Set device
    # TODO: device profile 적용
    def setcommand(self, mac_addr, idcode, set_pw, command_list, param_list, devname, version, status=None):
        """
        Make device setting command set
        - set commands + get commands
        """
        cmd_list = self.make_header(mac_addr, idcode, devname=devname, set_pw=set_pw)
        # print('Macaddr: %s' % mac_addr)
        try:
            # Set commands
            for i in range(len(command_list)):
                cmd_list.append([command_list[i], param_list[i]])

            # Get commands
            if devname in ONE_PORT_DEV:
                # WIZ107SR/WIZ108SR: DD(DDNS Enable), PO(Network Protocol) 포함 전용 목록
                if "WIZ107SR" in devname or "WIZ108SR" in devname:
                    for cmd in cmd_107sr:
                        cmd_list.append([cmd, ""])
                else:
                    # WIZ750SR series / W7500(P)-S2E
                    if version_compare("1.2.0", version) <= 0:
                        for cmd in cmd_1p_advanced:
                            cmd_list.append([cmd, ""])
                    else:
                        for cmd in cmd_1p_default:
                            cmd_list.append([cmd, ""])
            elif devname in TWO_PORT_DEV or "752" in devname:
                # WIZ752SR-12x: cmd_ch2 만 붙이면 MC 가 확인 쿼리에 없어서
                # get_setting_result() 의 성공 판정(len(mc)==17)이 항상 실패한다
                # (완료 팝업이 안 뜨던 원인). MC 를 앞에 붙인 전용 목록을 쓴다.
                # 전체 목록(cmd_2p_default)은 요청이 512바이트 버퍼를 넘겨 쓸 수 없다.
                for cmd in cmd_2p_setconfirm:
                    cmd_list.append([cmd, ""])
            elif devname in SECURITY_DEVICE:
                if 'WIZ510SSL' in devname:
                    for cmd in cmd_wiz510ssl:
                        cmd_list.append([cmd, ""])
                elif 'W55RP20-S2E-2CH' in devname:
                    if status != "BOOT":
                        if version_compare(version, "1.1.8") >= 0:
                            for cmd in cmd_w55rp20_2ch:
                                cmd_list.append([cmd, ""])
                        else:
                            for cmd in cmd_security_base + cmd_wiz5xxsr_added:
                                cmd_list.append([cmd, ""])
                    else:
                        for cmd in cmd_1p_boot:
                            cmd_list.append([cmd, ""])
                elif 'W55RP20-S2E' in devname:
                    if status != "BOOT":
                        # 버전 1.1.8 이상인 경우에만 SD, DD, SE 명령어 포함
                        if version_compare(version, "1.1.8") >= 0:
                            for cmd in cmd_w55rp20:
                                cmd_list.append([cmd, ""])
                        else:
                            for cmd in cmd_security_base + cmd_wiz5xxsr_added:
                                cmd_list.append([cmd, ""])
                    else:
                        for cmd in cmd_1p_boot:
                            cmd_list.append([cmd, ""])
                elif 'WIZ5XXSR' in devname:
                    if status != "BOOT":
                        for cmd in cmd_wiz5xxsr:
                            cmd_list.append([cmd, ""])
                    else:
                        for cmd in cmd_1p_boot:
                            cmd_list.append([cmd, ""])
                elif 'W232N' in devname or 'IP20' in devname:
                    if status != "BOOT":
                        # W232N과 IP20도 SD, DD, SE 명령어 지원 (버전 1.1.8 이상인 경우에만)
                        if version_compare(version, "1.1.8") >= 0:
                            for cmd in cmd_wiz5xxsr + cmd_w55rp20_added:
                                cmd_list.append([cmd, ""])
                        else:
                            for cmd in cmd_wiz5xxsr:
                                cmd_list.append([cmd, ""])
                    else:
                        for cmd in cmd_1p_boot:
                            cmd_list.append([cmd, ""])
                    # Commands for E-SAVE — `E-Save` 브랜치 전용 (위 cmd_wiz5xxsr_esave 주석 참조)
                    #if 'E-SAVE' in devname:
                    #    for cmd in cmd_wiz5xxsr_esave:
                    #        cmd_list.append([cmd, ""])
            # if status == "BOOT":
            #     return cmd_list
            if status != "BOOT":
                self._append_modbus_command(cmd_list, devname, version)
            cmd_list.append(["SV", ""])  # save device setting
            cmd_list.append(["RT", ""])  # Device reboot
            # print("setcommand()", cmd_list)
            return cmd_list
        except Exception as e:
            self.logger.error("[ERROR] setcommand(): %r\r\n" % e)

    def reset(self, mac_addr, idcode, set_pw, devname):
        self.logger.info(f'Reset: {mac_addr}')
        cmd_list = []
        try:
            self.logger.debug(f"reset mac_addr={mac_addr} idcode={idcode} set_pw={set_pw} devname={devname}")
            cmd_list = self.make_header(mac_addr, idcode, devname=devname, set_pw=set_pw)
            cmd_list.append(["RT", ""])
        except Exception as e:
            self.logger.error(e)
        return cmd_list

    def factory_reset(self, mac_addr, idcode, set_pw, devname, param):
        self.logger.info(f'Factory: {mac_addr}')
        cmd_list = []
        try:
            cmd_list = self.make_header(mac_addr, idcode, devname=devname, set_pw=set_pw)
            cmd_list.append(["FR", param])
        except Exception as e:
            self.logger.error(e)
        return cmd_list
