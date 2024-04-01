import re
from utils import logger
from WIZMakeCMD import ONE_PORT_DEV, TWO_PORT_DEV, SECURITY_DEVICE


ip_pattern = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"
port_pattern = "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$"
baudrate_option = {"0": "300", "1": "600", "2": "1200", "3": "1800", "4": "2400", "5": "4800", "6": "9600", "7": "14400", "8": "19200", "9": "28800", "10": "38400", "11": "57600", "12": "115200", "13": "230400"}
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
    "BR": ["UART Baud rate", "^([0-9]|1[0-4])$", baudrate_option, "RW"],
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
    "PO": ["Status of Modbus protocol", "^[0-2]$", {}, "RO"],
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

    def get_cmdset(self, name):
        if name in ONE_PORT_DEV:
            logger.debug('One port device')
            self.cmdset = WIZ75X_CMDSET
        elif name in SECURITY_DEVICE:
            logger.debug('Security device')
            self.cmdset = WIZ5XX_RP_CMDSET
        elif name in TWO_PORT_DEV:
            logger.debug('Two port device')
            self.cmdset = WIZ752_CMDSET
        else:
            logger.debug('Default device')
            self.cmdset = WIZ75X_CMDSET

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