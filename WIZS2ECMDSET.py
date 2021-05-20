#!../bin/python

import re
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

oneport_addded_cmdset = {
    "TR": ["TCP Retransmission Retry count", "^([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-5][0-5])$", {}, "RW"],
}

oneport_cmdset = {
    "MC": ["MAC address", "^([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})$", {}, "RO"],
    "VR": ["Firmware Version", "", {}, "RO"],
    "MN": ["Product Name", "", {}, "RO"],
    "ST": ["Operation status for channel 0", "", {}, "RO"],
    "QS": ["Operation status for channel 1", "", {}, "RO"],
    "UN": ["UART Interface(Str) for channel 0", "", {}, "RO"],
    "EN": ["UART Interface(Str) for channel 1", "", {}, "RO"],
    "UI": ["UART Interface(Code) for channel 0", "", {}, "RO"],
    # "TR": ["TCP Retransmission Retry count", "^([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-5][0-5])$", {}, "RW"],
    "OP": [
        "Network Operation Mode",
        "^[0-3]$",
        {"0": "TCP Client mode", "1": "TCP Server mode", "2": "TCP Mixed mode", "3": "UDP mode"},
        "RW",
    ],
    "IM": ["IP address Allocation Mode", "^[0-1]$", {"0": "Static IP", "1": "DHCP"}, "RW"],
    "LI": [
        "Local IP address",
        "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",
        {},
        "RW",
    ],
    "SM": [
        "Subnet mask",
        "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",
        {},
        "RW",
    ],
    "GW": [
        "Gateway address",
        "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",
        {},
        "RW",
    ],
    "DS": [
        "DNS Server address",
        "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",
        {},
        "RW",
    ],
    "LP": [
        "Local port number",
        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
        {},
        "RW",
    ],
    "RH": [
        "Remote Host IP address",
        "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",
        {},
        "RW",
    ],
    "RP": [
        "Remote Host Port number",
        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
        {},
        "RW",
    ],
    "BR": [
        "UART Baud rate",
        "^([0-9]|1[0-4])$",
        {
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
        },
        "RW",
    ],
    "DB": ["UART Data bit length", "^[0-1]$", {"0": "7-bit", "1": "8-bit"}, "RW"],
    "PR": ["UART Parity bit", "^[0-2]$", {"0": "NONE", "1": "ODD", "2": "EVEN"}, "RW"],
    "SB": ["UART Stop bit length", "^[0-1]$", {"0": "1-bit", "1": "2-bit"}, "RW"],
    "FL": [
        "UART Flow Control",
        "^[0-4]$",
        {"0": "NONE", "1": "XON/XOFF", "2": "RTS/CTS", "3": "RTS on TX", "4": "RTS on TX (invert)"},
        "RW",
    ],
    "PT": [
        "Time Delimiter",
        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
        {},
        "RW",
    ],
    "PS": ["Size Delimiter", "^([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", {}, "RW"],
    # "PD" : ["Char Delimiter", "^([0-7][0-9a-fA-F])$", {}, "RW"],
    "PD": ["Char Delimiter", "^([0-9a-fA-F][0-9a-fA-F])$", {}, "RW"],
    "IT": [
        "Inactivity Timer Value",
        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
        {},
        "RW",
    ],
    "CP": ["Connection Password Enable", "^[0-1]$", {}, "RW"],
    "NP": ["Connection Password", "", {}, "RW"],
    "SP": ["Search ID Code", "", {}, "RW"],
    # "DG" : ["Serial Debug Message Enable", "^[0-1]$", {}, "RW"],
    # debug msg test
    "DG": ["Serial Debug Message Enable", "^[0-4]$", {}, "RW"],
    "KA": ["TCP Keep-alive Enable", "^[0-1]$", {}, "RW"],
    "KI": [
        "TCP Keep-alive Initial Interval",
        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
        {},
        "RW",
    ],
    "KE": [
        "TCP Keep-alive Retry Interval",
        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
        {},
        "RW",
    ],
    "RI": [
        "TCP Reconnection Interval",
        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
        {},
        "RW",
    ],
    "EC": ["Serial Command Echoback Enable", "^[0-1]$", {}, "RW"],
    "TE": ["Command mode Switch Code Enable", "^[0-1]$", {}, "RW"],
    "SS": ["Command mode Switch Code", "^(([0-9a-fA-F][0-9a-fA-F]){3})$", {}, "RW"],
    # "SS" : ["Command mode Switch Code", "^([0-7][0-9a-fA-F]{3})$", {}, "RW"],
    "EX": ["Command mode exit", "", {}, "WO"],
    "SV": ["Save Device Setting", "", {}, "WO"],
    "RT": ["Device Reboot", "", {}, "WO"],
    "FR": ["Device Factory Reset", "", {}, "WO"],
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
        {"00": "PHY Link Status / TCP Connection Status", "11": "DTR/DSR"},
        "RW",
    ],
    "S0": [
        "Status of pin S0 (PHY Link or DTR)",
        "^[0-1]$",
        {"0": "PHY Link Up / The device != ready", "1": "PHY Link Down / The device ready for communication",},
        "RO",
    ],
    "S1": [
        "Status of pin S1 (TCP Connection or DST)",
        "^[0-1]$",
        {"0": "PHY Link Up / The device != ready", "1": "PHY Link Down / The device ready for communication",},
        "RO",
    ],
}

wiz2000_added_cmdset = {
    # WIZ2000
    "MB": [
        "Modbus options for channel 0",
        "^[0-2]$",
        {"0": "Serial to Ethernet", "1": "Modbus RTU to TCP converter", "2": "Modbus ASCII to TCP converter"},
        "RW",
    ],
    "MM": [
        "Modbus options for channel 1",
        "^[0-2]$",
        {"0": "Serial to Ethernet", "1": "Modbus RTU to TCP converter", "2": "Modbus ASCII to TCP converter"},
        "RW",
    ],
    "SE": ["SSL/TLS 1.2 enable", "^[0-1]$", {}, "RW"],
    "CE": ["Cloud connection enable", "^[0-1]$", {}, "RW"],
    # "CT" : ["Cloud Service Type", "", {}, "RW"],
    "N0": ["Network Time server domain 0", "", {}, "RW"],
    "N1": ["Network Time server domain 1", "", {}, "RW"],
    "N2": ["Network Time server domain 2", "", {}, "RW"],
    "LF": ["Local Port Fix for channel 0 (TCP client only)", "^[0-1]$", {}, "RW"],
    "QF": ["Local Port Fix for channel 1 (TCP client only)", "^[0-1]$", {}, "RW"],
    "AE": ["Setting Password Enable", "^[0-1]$", {}, "RW"],
    "AP": ["Setting Password", "", {}, "RW"],
    "AL": ["Device Alias", "", {}, "RW"],
    "GR": ["Device Group", "", {}, "RW"],
    "AM": [
        "TCP Connection Auto Message",
        "^[0-6]$",
        {
            "0": "None",
            "1": "Device Name",
            "2": "Mac Address",
            "3": "IP Address",
            "4": "Device ID(type+mac)",
            "5": "Device Alias",
            "6": "Device Group",
        },
        "RW",
    ],
    "CS": [
        "Cloud Monitor Update Interval",
        "^([1-9][0-9] | [1-9][0-9][0-9] | [1-2][0-9][0-9][0-9] | 3[0-6]00 )$",
        {},
        "RW",
    ],
    "CM": ["Cloud Monitor Enable", "^[0-4]$", {}, "RW"],
    # "^([0-9] | [1-9][0-9] | 1[0-9][0-9] | 2[0-5][0-5])$"
    "C0": ["Cloud Monitor Slave Channel 1 ID", "", {}, "RW"],
    "C1": ["Cloud Monitor Slave Channel 2 ID", "", {}, "RW"],
    "C2": ["Cloud Monitor Slave Channel 3 ID", "", {}, "RW"],
    "C3": ["Cloud Monitor Slave Channel 4 ID", "", {}, "RW"],
}

wiz510ssl_added_cmdset = {
    # part of wiz2000 commands
    # "SE": ["SSL/TLS 1.2 enable", "^[0-1]$", {}, "RW"],
    "AE": ["Setting Password Enable", "^[0-1]$", {}, "RW"],
    "AP": ["Setting Password", "", {}, "RW"],
    "AL": ["Device Alias", "", {}, "RW"],
    "GR": ["Device Group", "", {}, "RW"],
    # ----------------------------------------------
    "RC": ["Root CA Option", "^[0-2]$", {}, "RW"],
    "CE": ["Client Certificate Enable", "^[0-1]$", {}, "RW"],
    "OP": [
        "Network Operation Mode - Extended",
        "^[0-6]$",
        {"0": "TCP Client mode", "1": "TCP Server mode", "2": "TCP Mixed mode", "3": "UDP mode", "4": "SSL TCP Client mode", "5": "MQTT Client", "6": "MQTTS Client"},
        "RW",
    ],
    "QU": ["MQTT Options - User name", "", {}, "RW"],
    "QP": ["MQTT options - Password", "", {}, "RW"],
    "QC": ["MQTT options - Client ID", "", {}, "RW"],
    "QK": ["MQTT options - Keep Alive", "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$", {}, "RW"],
    "PU": ["MQTT options - Publish topic", "", {}, "RW"],
    "SU": ["MQTT options - Subscribe topic", "", {}, "RW"],
}


class WIZS2ECMDSET:
    def __init__(self, log_level):

        self.log_level = log_level

        self.wiz750sr_cmdset = {**oneport_cmdset, **oneport_addded_cmdset}
        self.wiz752sr_cmdset = {**oneport_cmdset}
        self.wiz2000_cmdset = {**oneport_cmdset, **wiz2000_added_cmdset}
        self.wiz510ssl_cmdset = {**self.wiz750sr_cmdset, **wiz510ssl_added_cmdset}

        self.cmdset = self.wiz2000_cmdset.copy()

    def isvalidcommand(self, cmdstr):
        if cmdstr in self.cmdset.keys():
            return 1
        return 0

    def isvalidparameter(self, cmdstr, param):
        if self.log_level == logging.DEBUG:
            logger.debug("Command: %s\r\n" % cmdstr)
            logger.debug("Parameter: %s\r\n" % param)

        if self.isvalidcommand(cmdstr) == 1:
            prog = re.compile(self.cmdset[cmdstr][1])
            # for domain name
            if cmdstr == "RH":
                # ! Need check size
                return True
            if prog.match(param):
                if self.log_level == logging.DEBUG:
                    logger.debug("Valid %s\r\n" % self.cmdset[cmdstr][0])
                return True
            else:
                if self.log_level == logging.DEBUG:
                    logger.debug("Invalid %s\r\n" % self.cmdset[cmdstr][0])
                return False

        if self.log_level == logging.DEBUG:
            logger.debug("Invalid command\r\n")
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
    cmdsetObj = WIZS2ECMDSET(logging.DEBUG)

    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:33")
    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:3z")
    # cmdsetObj.isvalidparameter("MC", "00:08-dc:11:22:33")
    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:33:")
    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:33:aa")
    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:0")
    # cmdsetObj.isvalidparameter("MA", "00:08:dc:11:22:00")

    print(cmdsetObj.getcmddescription("BR"))
    print(cmdsetObj.getparamdescription("BR", "3"))

    cmd_set = cmdsetObj.cmdset
    cmdlist = cmd_set.keys()

    # f = open('cmd_twoport-.txt', 'w')
    # for i in range(len(cmd_set)):
    # 	cmd = "%s\r\n" % (cmdlist[i])
    # 	print(cmd)
    # 	f.write(cmd)
    # f.close()

