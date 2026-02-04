"""
WizNet S2E Tool - Command Set Definition

CMDSET 상속 구조:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
common_cmdset (기본 명령어 집합, BR: 0-15)
├─ WIZ75X_CMDSET (단일 포트 기본 장치)
├─ WIZ752_CMDSET (2포트 장치, BR/EB: 0-13)
└─ WIZ5XX_RP_CMDSET (보안 장치 기본, BR: 0-15)
    ├─ [WIZ510SSL, WIZ5XXSR-RP, W232N, IP20 등] ← 그대로 사용
    └─ W55RP20_CMDSET (고속 BR 지원, BR: 0-19)
        └─ W55RP20_2CH_CMDSET (2채널, BR/EB: 0-19)

장치별 Baudrate 지원:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- WIZ752 계열:       BR/EB 0-13  (최대 230400 bps)
- 일반 장치:         BR 0-15     (최대 921600 bps)
- W55RP20-S2E:       BR 0-19     (최대 8M bps)
- W55RP20-S2E-2CH:   BR/EB 0-19  (최대 8M bps)
"""

import re
from utils import logger
from WIZMakeCMD import (
    ONE_PORT_DEV,
    TWO_PORT_DEV,
    SECURITY_DEVICE,
    version_compare,
)
from collections import namedtuple

# ==================== Pattern Definitions ====================
ip_pattern = r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"
port_pattern = r"^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$"

# W55RP20 high-speed baudrate pattern (BR/EB index 0-19: 300bps ~ 8Mbps)
# W55RP20-S2E와 W55RP20-S2E-2CH의 BR/EB에서 동일하게 사용
w55rp20_baudrate_pattern = r"^([0-9]|1[0-9])$"
baudrate_option = {
    "0": "300",
    "1": "600",
    "2": "1200",
    "3": "1800",
    "4": "2400",
    "5": "4800",
    "6": "9600",
    "7": "14400",
    "8": "19200",
    "9": "28800",
    "10": "38400",
    "11": "57600",
    "12": "115200",
    "13": "230400",
    "14": "460800",
    "15": "921600",
}
opmode_option = {"0": "TCP Client mode", "1": "TCP Server mode", "2": "TCP Mixed mode", "3": "UDP mode"}

common_cmdset = {
    "MC": ["MAC address", "^([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})$", {}, "RO"],
    "VR": ["Firmware Version", "", {}, "RO"],
    "MN": ["Product Name", "", {}, "RO"],
    "ST": ["Operation status", "", {}, "RO"],
    "UN": ["UART Interface(Str)", "", {}, "RO"],
    "UI": ["UART Interface(Code)", "", {}, "RO"],
    # WIZ750SR: F/W 1.2.0 verison or later
    "TR": ["TCP Retransmission Retry count", "^([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-5][0-5])$", {}, "RW"],
    "OP": ["Network Operation Mode", "^[0-3]$", opmode_option, "RW"],
    "IM": ["IP address Allocation Mode", "^[0-1]$", {"0": "Static IP", "1": "DHCP"}, "RW"],
    "LI": ["Local IP address", ip_pattern, {}, "RW"],
    "SM": ["Subnet mask", ip_pattern, {}, "RW"],
    "GW": ["Gateway address", ip_pattern, {}, "RW"],
    "DS": ["DNS Server address", ip_pattern, {}, "RW"],
    "LP": ["Local port number", port_pattern, {}, "RW"],
    "RH": ["Remote Host IP address", ip_pattern, {}, "RW"],
    "RP": ["Remote Host Port number", port_pattern, {}, "RW"],
    "BR": ["UART Baud rate", "^([0-9]|1[0-5])$", baudrate_option, "RW"],
    "DB": ["UART Data bit length", "^[0-1]$", {"0": "7-bit", "1": "8-bit"}, "RW"],
    "PR": ["UART Parity bit", "^[0-2]$", {"0": "NONE", "1": "ODD", "2": "EVEN"}, "RW"],
    "SB": ["UART Stop bit length", "^[0-1]$", {"0": "1-bit", "1": "2-bit"}, "RW"],
    "FL": [
        "UART Flow Control",
        "^[0-4]$",
        {"0": "NONE", "1": "XON/XOFF", "2": "RTS/CTS", "3": "RTS on TX", "4": "RTS on TX (invert)"},
        "RW"
    ],
    "PT": ["Time Delimiter", port_pattern, {}, "RW"],
    "PS": ["Size Delimiter", "^([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", {}, "RW"],
    # "PD" : ["Char Delimiter", "^([0-7][0-9a-fA-F])$", {}, "RW"],
    "PD": ["Char Delimiter", "^([0-9a-fA-F][0-9a-fA-F])$", {}, "RW"],
    "IT": ["Inactivity Timer Value", port_pattern, {}, "RW"],
    "CP": ["Connection Password Enable", "^[0-1]$", {}, "RW"],
    "NP": ["Connection Password", "", {}, "RW"],
    "SP": ["Search ID Code", "", {}, "RW"],
    # "DG" : ["Serial Debug Message Enable", "^[0-1]$", {}, "RW"],
    # debug msg test
    "DG": ["Serial Debug Message Enable", "^[0-4]$", {}, "RW"],
    "KA": ["TCP Keep-alive Enable", "^[0-1]$", {}, "RW"],
    "KI": ["TCP Keep-alive Initial Interval", port_pattern, {}, "RW"],
    "KE": ["TCP Keep-alive Retry Interval", port_pattern, {}, "RW"],
    "RI": ["TCP Reconnection Interval", port_pattern, {}, "RW"],
    "EC": ["Serial Command Echoback Enable", "^[0-1]$", {}, "RW"],
    "TE": ["Command mode Switch Code Enable", "^[0-1]$", {}, "RW"],
    "SS": ["Command mode Switch Code", "^(([0-9a-fA-F][0-9a-fA-F]){3})$", {}, "RW"],
    "CA": [
        "Type and Direction of User I/O pin A",
        "^[0-2]$",
        {"0": "Digital Input", "1": "Digital Output", "2": "Analog Input"},
        "RW",
    ],
    "CB": [
        "Type and Direction of User I/O pin B",
        "^[0-2]$",
        {"0": "Digital Input", "1": "Digital Output", "2": "Analog Input"},
        "RW",
    ],
    "CC": [
        "Type and Direction of User I/O pin C",
        "^[0-2]$",
        {"0": "Digital Input", "1": "Digital Output", "2": "Analog Input"},
        "RW",
    ],
    "CD": [
        "Type and Direction of User I/O pin D",
        "^[0-2]$",
        {"0": "Digital Input", "1": "Digital Output", "2": "Analog Input"},
        "RW",
    ],
    "GA": ["Status and Value of User I/O pin A", "^[0-1]$", {"0": "Low", "1": "High"}, "RW"],
    "GB": ["Status and Value of User I/O pin B", "^[0-1]$", {"0": "Low", "1": "High"}, "RW"],
    "GC": ["Status and Value of User I/O pin C", "^[0-1]$", {"0": "Low", "1": "High"}, "RW"],
    "GD": ["Status and Value of User I/O pin D", "^[0-1]$", {"0": "Low", "1": "High"}, "RW"],
    "SC": [
        "Status pin S0 and S1 Operation Mode Setting",
        "^([0-1]{2})$",
        {"00": "PHY Link Status or TCP Connection Status", "11": "DTR/DSR"},
        "RW"
    ],
    "S0": [
        "Status of pin S0 (PHY Link or DTR)",
        "^[0-1]$",
        {
            "0": "PHY Link Up or The device is not ready",
            "1": "PHY Link Down or The device ready for communication",
        },
        "RO"
    ],
    "S1": [
        "Status of pin S1 (TCP Connection or DST)",
        "^[0-1]$",
        {
            "0": "PHY Link Up or The device is not ready",
            "1": "PHY Link Down or The device ready for communication",
        },
        "RO"
    ],
    "EX": ["Command mode exit", "", {}, "WO"],
    "SV": ["Save Device Setting", "", {}, "WO"],
    "RT": ["Device Reboot", "", {}, "WO"],
    "FR": ["Device Factory Reset", "", {}, "WO"]
}

WIZ75X_CMDSET = {
    **common_cmdset,
    "TR": ["TCP Retransmission Retry count", "^([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-5][0-5])$", {}, "RW"],
}

WIZ510SSL_CMDSET = {
    **common_cmdset,
    # "SU": ["MQTT options - Subscribe topic", "", {}, "RW"],
    "BA": ["Current Flash Bank", "", {}, "RO"],
}

# ==================== WIZ5XX-RP Family CMDSET ====================
# 적용 장치: WIZ510SSL, WIZ5XXSR-RP, W232N, IP20
# 특징: SSL/MQTT 지원, BR 0-15 (최대 921600 bps)
WIZ5XX_RP_CMDSET = {
    **common_cmdset,
    "OP": [
        "Network Operation Mode - Extended",
        "^[0-6]$",
        {**opmode_option, "4": "SSL TCP Client mode", "5": "MQTT Client", "6": "MQTTS Client"},
        "RW",
    ],
    "SO": ["SSL receive timeout", "", {}, "RW"],
    "QU": ["MQTT Options - User name", "", {}, "RW"],
    "QP": ["MQTT options - Password", "", {}, "RW"],
    "QC": ["MQTT options - Client ID", "", {}, "RW"],
    "QK": ["MQTT Keep-Alive", "", {}, "RW"],
    "PU": ["MQTT Publish topic", "", {}, "RW"],
    "U0": ["MQTT Subscribe topic 1", "", {}, "RW"],
    "U1": ["MQTT Subscribe topic 2", "", {}, "RW"],
    "U2": ["MQTT Subscribe topic 3", "", {}, "RW"],
    "QO": ["MQTT QoS level", "^[0-2]$", {}, "RW"],
    "RC": ["Root CA Option", "^[0-2]$", {}, "RW"],
    "CE": ["Client Certificate Enable", "^[0-1]$", {}, "RW"],
    "OC": ["Root CA", "", {}, "WO"],
    "LC": ["Client Certificate", "", {}, "WO"],
    "PK": ["Private Key", "", {}, "WO"],
    "UF": ["Copy firmware from firmware binary bank to application bank", "", {}, "RW"],
    "PO": ["Status of Modbus protocol", "^[0-2]$", {}, "RW"],
    "MB": ["Status of Modbus protocol", "^[0-2]$", {}, "RW"],
    "SD": ["Send Data at Connection", "^.{0,30}$", {}, "RW"],  # W55RP20-S2E, W232N, IP20, 최대 30글자
    "DD": ["Send Data at Disconnection", "^.{0,30}$", {}, "RW"],  # W55RP20-S2E, W232N, IP20, 최대 30글자
    "SE": ["Ethernet Data Connection Condition", "^.{0,30}$", {}, "RW"],  # W55RP20-S2E, W232N, IP20, 최대 30글자
}

# ==================== W55RP20 CMDSET (Single Channel) ====================
# 적용 장치: W55RP20-S2E
# 상속: WIZ5XX_RP_CMDSET
# 특징: 고속 Baudrate 지원 (BR 0-19, 최대 8Mbps)
W55RP20_CMDSET = {
    **WIZ5XX_RP_CMDSET,
    # BR을 고속 baudrate로 재정의 (w55rp20_baudrate_pattern 사용)
    "BR": ["UART Baud rate", w55rp20_baudrate_pattern, baudrate_option, "RW"],
}

# ==================== W55RP20 2-Channel CMDSET ====================
# 적용 장치: W55RP20-S2E-2CH
# 상속: W55RP20_CMDSET
# 특징: 2채널 지원, 양쪽 채널 모두 고속 Baudrate (BR/EB 0-19, 최대 8Mbps)
W55RP20_2CH_CMDSET = {
    **W55RP20_CMDSET,
    "QS": ["Operation status for channel 1", "", {}, "RO"],
    "EN": ["UART Interface(Str) for channel 1", "", {}, "RO"],
    "AO": [
        "Network Operation Mode for channel 1 - Extended",
        "^[0-6]$",
        {**opmode_option, "4": "SSL TCP Client mode", "5": "MQTT Client", "6": "MQTTS Client"},
        "RW",
    ],
    "QL": ["Local port number for channel 1", port_pattern, {}, "RW"],
    "QH": ["Remote Host IP address for channel 1", ip_pattern, {}, "RW"],
    "AP": ["Remote Host Port number for channel 1", port_pattern, {}, "RW"],
    # EB: BR과 동일한 패턴 사용 (w55rp20_baudrate_pattern, 0-19 지원)
    "EB": ["UART channel 1 Baud rate", w55rp20_baudrate_pattern, baudrate_option, "RW"],
    "ED": ["UART channel 1 Data bit length", "^[0-1]$", {"0": "7-bit", "1": "8-bit"}, "RW"],
    "EP": ["UART channel 1 Parity bit", "^[0-2]$", {"0": "NONE", "1": "ODD", "2": "EVEN"}, "RW"],
    "ES": ["UART channel 1 Stop bit length", "^[0-1]$", {"0": "1-bit", "1": "2-bit"}, "RW"],
    "EF": ["UART channel 1 Flow Control", "^[0-2]$", {"0": "NONE", "1": "XON/XOFF", "2": "RTS/CTS"}, "RW"],
    "ND": ["Char Delimiter for channel 1", "^([0-9a-fA-F][0-9a-fA-F])$", {}, "RW"],
    "NS": ["Size Delimiter for channel 1", "^([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", {}, "RW"],
    "AT": ["Time Delimiter for channel 1", port_pattern, {}, "RW"],
    "RV": ["Inactivity Timer Value for channel 1", port_pattern, {}, "RW"],
    "RA": ["TCP Keep-alive Enable for channel 1", "^[0-1]$", {}, "RW"],
    "RS": ["TCP Keep-alive Initial Interval for channel 1", port_pattern, {}, "RW"],
    "RE": ["TCP Keep-alive Retry Interval for channel 1", port_pattern, {}, "RW"],
    "RR": ["TCP Reconnection Interval for channel 1", port_pattern, {}, "RW"],
    "RO": ["Channel 1 SSL receive timeout", "", {}, "RW"],
    "EO": ["Channel 1 Modbus protocol", "^[0-2]$", {}, "RW"],
    "RD": ["Channel 1 Serial Connected Data", "^.{0,30}$", {}, "RW"],
    "RF": ["Channel 1 Serial Disconnected Data", "^.{0,30}$", {}, "RW"],
    "EE": ["Channel 1 Ethernet Connected Data", "^.{0,30}$", {}, "RW"],
}

# boot mode
BOOT_CMDSET = {
    "MC": common_cmdset["MC"],
    "VR": common_cmdset["VR"],
    "MN": common_cmdset["MN"],
    "ST": common_cmdset["ST"],
    "IM": common_cmdset["IM"],
    "OP": common_cmdset["OP"],
    "LI": common_cmdset["LI"],
    "SM": common_cmdset["SM"],
    "GW": common_cmdset["GW"],
    "SP": common_cmdset["SP"],
    "DS": common_cmdset["DS"],
}

# Two port devices
WIZ752_CMDSET = {
    **common_cmdset,
    "ST": ["Operation status for channel 0", "", {}, "RO"],
    "QS": ["Operation status for channel 1", "", {}, "RO"],
    "UN": ["UART Interface(Str) for channel 0", "", {}, "RO"],
    "EN": ["UART Interface(Str) for channel 1", "", {}, "RO"],
    "UI": ["UART Interface(Code) for channel 0", "", {}, "RO"],
    "TR": ["TCP Retransmission Retry count", "^([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-5][0-5])$", {}, "RW"],
    "EI": ["UART Interface(Code) for channel 1", "", {}, "RO"],
    "OP": ["Network Operation Mode for channel 0", "^[0-3]$", opmode_option, "RW"],
    "QO": ["Network Operation Mode for channel 1", "^[0-3]$", opmode_option, "RW"],
    "LP": ["Local port number for channel 0", port_pattern, {}, "RW"],
    "QL": ["Local port number for channel 1", port_pattern, {}, "RW"],
    "RH": ["Remote Host IP address for channel 0", ip_pattern, {}, "RW"],
    "QH": ["Remote Host IP address for channel 1", ip_pattern, {}, "RW"],
    "RP": ["Remote Host Port number for channel 0", port_pattern, {}, "RW"],
    "QP": ["Remote Host Port number for channel 1", port_pattern, {}, "RW"],
    "BR": ["UART channel 0 Baud rate", "^([0-9]|1[0-3])$", baudrate_option, "RW"],
    "EB": ["UART channel 1 Baud rate", "^([0-9]|1[0-3])$", baudrate_option, "RW"],
    "DB": ["UART channel 0 Data bit length", "^[0-1]$", {"0": "7-bit", "1": "8-bit"}, "RW"],
    "ED": ["UART channel 1 Data bit length", "^[0-1]$", {"0": "7-bit", "1": "8-bit"}, "RW"],
    "PR": ["UART channel 0 Parity bit", "^[0-2]$", {"0": "NONE", "1": "ODD", "2": "EVEN"}, "RW"],
    "EP": ["UART channel 1 Parity bit", "^[0-2]$", {"0": "NONE", "1": "ODD", "2": "EVEN"}, "RW"],
    "SB": ["UART channel 0 Stop bit length", "^[0-1]$", {"0": "1-bit", "1": "2-bit"}, "RW"],
    "ES": ["UART channel 1 Stop bit length", "^[0-1]$", {"0": "1-bit", "1": "2-bit"}, "RW"],
    "FL": ["UART channel 0 Flow Control", "^[0-2]$", {"0": "NONE", "1": "XON/XOFF", "2": "RTS/CTS"}, "RW"],
    "EF": ["UART channel 1 Flow Control", "^[0-2]$", {"0": "NONE", "1": "XON/XOFF", "2": "RTS/CTS"}, "RW"],
    "PT": ["Time Delimiter for channel 0", port_pattern, {}, "RW"],
    "NT": ["Time Delimiter for channel 1", port_pattern, {}, "RW"],
    "PS": ["Size Delimiter for channel 0", "^([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", {}, "RW"],
    "NS": ["Size Delimiter for channel 1", "^([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", {}, "RW"],
    "PD": ["Char Delimiter for channel 0", "^([0-9a-fA-F][0-9a-fA-F])$", {}, "RW"],
    "ND": ["Char Delimiter for channel 1", "^([0-9a-fA-F][0-9a-fA-F])$", {}, "RW"],
    "IT": ["Inactivity Timer Value for channel 0", port_pattern, {}, "RW"],
    "RV": ["Inactivity Timer Value for channel 1", port_pattern, {}, "RW"],
    "CP": ["Connection Password Enable", "^[0-1]$", {}, "RW"],
    "NP": ["Connection Password", "", {}, "RW"],
    "SP": ["Search ID Code", "", {}, "RW"],
    "DG": ["Serial Debug Message Enable", "^[0-4]$", {}, "RW"],
    "KA": ["TCP Keep-alive Enable for channel 0", "^[0-1]$", {}, "RW"],
    "RA": ["TCP Keep-alive Enable for channel 1", "^[0-1]$", {}, "RW"],
    "KI": ["TCP Keep-alive Initial Interval for channel 0", port_pattern, {}, "RW"],
    "RS": ["TCP Keep-alive Initial Interval for channel 1", port_pattern, {}, "RW"],
    "KE": ["TCP Keep-alive Retry Interval for channel 0", port_pattern, {}, "RW"],
    "RE": ["TCP Keep-alive Retry Interval for channel 1", port_pattern, {}, "RW"],
    "RI": ["TCP Reconnection Interval for channel 0", port_pattern, {}, "RW"],
    "RR": ["TCP Reconnection Interval for channel 1", port_pattern, {}, "RW"],
}


class Wizcmdset():
    def __init__(self, name):
        self.name = name
        self.cmdset = common_cmdset

        self.get_cmdset(self.name)

    def get_cmdset(self, name, mode=None, version=None):
        mode_str = ""
        if mode is not None:
            mode_str = mode.upper() if isinstance(mode, str) else str(mode).upper()

        # ==================== 장치별 CMDSET 매핑 ====================
        if name in ONE_PORT_DEV:
            logger.debug('One port device')
            self.cmdset = WIZ75X_CMDSET.copy()
        elif name in SECURITY_DEVICE:
            if mode_str != "BOOT":
                # W55RP20 Family: 고속 Baudrate 지원
                if name == "W55RP20-S2E-2CH":
                    # 2채널, BR/EB 0-19 (최대 8Mbps)
                    logger.debug("Security device (W55RP20-S2E-2CH)")
                    self.cmdset = W55RP20_2CH_CMDSET.copy()
                elif name == "W55RP20-S2E":
                    # 단일채널, BR 0-19 (최대 8Mbps)
                    logger.debug("Security device (W55RP20-S2E)")
                    self.cmdset = W55RP20_CMDSET.copy()
                else:
                    # 기타 보안 장치 (WIZ510SSL, W232N, IP20 등): BR 0-15 (최대 921600)
                    logger.debug("Security device")
                    self.cmdset = WIZ5XX_RP_CMDSET.copy()
            else:
                logger.debug("Security device in BOOT mode")
                self.cmdset = BOOT_CMDSET.copy()
        elif name in TWO_PORT_DEV:
            logger.debug('Two port device')
            self.cmdset = WIZ752_CMDSET.copy()
        else:
            logger.debug('Default device')
            self.cmdset = WIZ75X_CMDSET.copy()

        self._apply_version_specific_overrides(name, version, mode)

    def isvalidcommand(self, cmdstr):
        if cmdstr in self.cmdset.keys():
            return True
        return False

    def isvalidparameter(self, cmdstr, param):
        logger.debug(f'command: {cmdstr}, param: {param}')

        if self.isvalidcommand(cmdstr):
            prog = re.compile(self.cmdset[cmdstr][1])
            # for domain name
            if cmdstr == "RH":
                # ! Need check size
                return True
            if prog.match(param):
                # logger.debug("Valid %s" % self.cmdset[cmdstr][0])
                return True
            else:
                logger.debug("Invalid %s" % self.cmdset[cmdstr][0])
                return False
        else:
            logger.debug(f"## Invalid command: {cmdstr}")

        logger.debug(f"## Invalid parameter: {cmdstr}, {param}")
        return False

    def _apply_version_specific_overrides(self, name, version, mode):
        mode_str = ""
        if mode is not None:
            mode_str = mode.upper() if isinstance(mode, str) else str(mode).upper()

        if not name or not version:
            return
        if mode_str == "BOOT":
            return

        if ("WIZ750" in name or "WIZ750SR-T1L" in name) and version_compare(version, "1.4.4") >= 0:
            if "MB" not in self.cmdset:
                updated_cmdset = self.cmdset.copy()
                updated_cmdset["MB"] = [
                    "Status of Modbus protocol",
                    "^[0-2]$",
                    {},
                    "RW",
                ]
                self.cmdset = updated_cmdset

    def getparamdescription(self, cmdstr, param):
        if self.isvalidparameter(cmdstr, param):
            if len(self.cmdset[cmdstr][2]) > 0:
                return self.cmdset[cmdstr][2][param]
            else:
                return param

    def getcmddescription(self, cmdstr):
        if self.isvalidcommand(cmdstr):
            return self.cmdset[cmdstr][0]
        else:
            return "Invalid command"

    def iswritable(self, cmdstr):
        if self.cmdset[cmdstr][3] == "RW":
            return True
        return False


__devst = namedtuple("__devst", ["boot", "upgrade", "app"])
SysTabIndex = namedtuple("SysTabIndex", ["idx", "name"])
SysTabObjectText = namedtuple("SysTabObjectText", ["object", "ui_text"])
ExcludeTabInMinimum = ("advance_tab", "mqtt_tab", "certificate_tab",)
ExcludeTabInCommon = ("mqtt_tab", "certificate_tab",)
IncludeTabInCommon = ("basic_tab", "advance_tab",)
IncludeTabIn7xx = ("basic_tab", "advance_tab", "userio_tab",)
DeviceStatus = __devst("BOOT", "UPGRADE", "APP")
DeviceStatusMinimum = (DeviceStatus.boot, DeviceStatus.upgrade)

if __name__ == "__main__":
    # wizcmdset = Wizcmdset("WIZ750SR")
    wizcmdset = Wizcmdset("WIZ752SR-12x")
    cmdlist = wizcmdset.cmdset.items()

    # 각 command에 대한 정보 출력 => log 기록 시 활용
    # cmd = "SS"
    cmd = "QH"
    print('"%s": %s\n %s\n' % (cmd, wizcmdset.cmdset[cmd][0], wizcmdset.cmdset[cmd][2]))

    # 함수 활용
    print(wizcmdset.getcmddescription(cmd))
    print(wizcmdset.getparamdescription(cmd, "2B2C2D"))

    print(wizcmdset.isvalidparameter(cmd, "192.168.11.3"))

