#!../bin/python
# -*- coding: utf-8 -*-

import re
import sys

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()


class WIZ750CMDSET:
    def __init__(self, log_level):

        self.log_level = log_level

        self.cmdset = { "MC" : ["MAC address",
                                "^([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})$",
                                {}, "RO"],
                        "VR" : ["Firmware Version", "", {}, "RO"],
                        "MN" : ["Product Name", "", {}, "RO"],
                        "ST" : ["Operation status", "", {}, "RO"],
                        "UN" : ["UART Interface(Str)", "", {}, "RO"],
                        "UI" : ["UART Interface(Code)", "", {}, "RO"],
                        "OP" : ["Network Operation Mode",
                                        "^[0-3]$",
                                        {"0": "TCP Client mode", "1" : "TCP Server mode", "2" : "TCP Mixed mode", "3" : "UDP mode"},
                                        "RW"],
                        "IM" : ["IP address Allocation Mode",
                                        "^[0-1]$",
                                        {"0" : "Static IP", "1" : "DHCP"},
                                        "RW"],
                        "LI" : ["Local IP address",
                                        "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",
                                        {}, "RW"],
                        "SM" : ["Subnet mask",
                                        "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",
                                        {}, "RW"],
                        "GW" : ["Gateway address",
                                        "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",
                                        {}, "RW"],
                        "DS" : ["DNS Server address",
                                        "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",
                                        {}, "RW"],
                        "LP" : ["Local port number",
                                        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
                                        {}, "RW"],
                        "RH" : ["Remote Host IP address",
                                        "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",
                                        {}, "RW"],
                        "RP" : ["Remote Host Port number",
                                        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
                                        {}, "RW"],
                        "BR" : ["UART Baud rate",
                                        "^([0-9]|1[0-4])$",
                                        {"0" : "300", "1" : "600", "2" : "1200", "3" : "1800", "4" : "2400", "5" : "4800", "6" : "9600", "7" : "14400",
                                         "8" : "19200", "9" : "28800", "10" : "38400", "11" : "57600", "12" : "115200", "13" : "230400", "14" : "460800"},
                                        "RW"],
                        "DB" : ["UART Data bit length", "^[0-1]$", {"0" : "7-bit", "1" : "8-bit"}, "RW"],
                        "PR" : ["UART Parity bit", "^[0-2]$", {"0" : "NONE", "1" : "ODD", "2" : "EVEN"}, "RW"],
                        "SB" : ["UART Stop bit length", "^[0-1]$", {"0" : "1-bit", "1" : "2-bit"}, "RW"],
                        "FL" : ["UART Flow Control", "^[0-2]$", {"0" : "NONE", "1" : "XON/XOFF", "2" : "RTS/CTS"}, "RW"],
                        "PT" : ["Time Delimiter",
                                        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
                                        {}, "RW"],
                        "PS" : ["Size Delimiter", "^([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", {}, "RW"],
                        "PD" : ["Char Delimiter", "^([0-7][0-9a-fA-F])$", {}, "RW"],
                        "IT" : ["Inactivity Timer Value",
                                        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
                                        {}, "RW"],
                        "CP" : ["Connection Password Enable", "^[0-1]$", {}, "RW"],
                        "NP" : ["Connection Password", "", {}, "RW"],
                        "SP" : ["Search ID Code", "", {}, "RW"],
                        "DG" : ["Serial Debug Message Enable", "^[0-1]$", {}, "RW"],
                        "KA" : ["TCP Keep-alive Enable", "^[0-1]$", {}, "RW"],
                        "KI" : ["TCP Keep-alive Initial Interval",
                                        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
                                        {}, "RW"],
                        "KE" : ["TCP Keep-alive Retry Interval",
                                        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
                                        {}, "RW"],
                        "RI" : ["TCP Reconnection Interval",
                                        "^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9][0-9][0-9]|65[0-4][0-9][0-9]|655[0-2][0-9]|6553[0-5])$",
                                        {}, "RW"],
                        "EC" : ["Serial Command Echoback Enable", "^[0-1]$", {}, "RW"],
                        "TE" : ["Command mode Switch Code Enable", "^[0-1]$", {}, "RW"],
                        "SS" : ["Command mode Switch Code", "^(([0-7][0-9a-fA-F]){3})$", {}, "RW"],
                        # "SS" : ["Command mode Switch Code", "^([0-7][0-9a-fA-F]{3})$", {}, "RW"],
                        "EX" : ["Command mode exit", "", {}, "WO"],
                        "SV" : ["Save Device Setting", "", {}, "WO"],
                        "RT" : ["Device Reboot", "", {}, "WO"],
                        "FR" : ["Device Factory Reset", "", {}, "WO"],
                        "CA" : ["Type and Direction of User I/O pin A",
                                        "^[0-2]$",
                                        {"0" : "Digital Input", "1" : "Digital Output", "2" : "Analog Input"}, "RW"],
                        "CB" : ["Type and Direction of User I/O pin B",
                                        "^[0-2]$",
                                        {"0" : "Digital Input", "1" : "Digital Output", "2" : "Analog Input"}, "RW"],
                        "CC" : ["Type and Direction of User I/O pin C",
                                        "^[0-2]$",
                                        {"0" : "Digital Input", "1" : "Digital Output", "2" : "Analog Input"}, "RW"],
                        "CD" : ["Type and Direction of User I/O pin D",
                                        "^[0-2]$",
                                        {"0" : "Digital Input", "1" : "Digital Output", "2" : "Analog Input"}, "RW"],
                        "GA" : ["Status and Value of User I/O pin A", "^[0-1]$", {"0" : "Low", "1" : "High"}, "RW"],
                        "GB" : ["Status and Value of User I/O pin B", "^[0-1]$", {"0" : "Low", "1" : "High"}, "RW"],
                        "GC" : ["Status and Value of User I/O pin C", "^[0-1]$", {"0" : "Low", "1" : "High"}, "RW"],
                        "GD" : ["Status and Value of User I/O pin D", "^[0-1]$", {"0" : "Low", "1" : "High"}, "RW"],
                        "SC" : ["Status pin S0 and S1 Operation Mode Setting", "^([0-1]{2})$",
                                        {"00" : "PHY Link Status / TCP Connection Status", "11" : "DTR/DSR"}, "RW"],
                        "S0" : ["Status of pin S0 (PHY Link or DTR)",
                                        "^[0-1]$",
                                        {"0" : "PHY Link Up / The device is not ready", "1" : "PHY Link Down / The device ready for communication"}, "RO"],
                        "S1" : ["Status of pin S1 (TCP Connection or DST)",
                                        "^[0-1]$",
                                        {"0" : "PHY Link Up / The device is not ready", "1" : "PHY Link Down / The device ready for communication"}, "RO"]}

    def isvalidcommand(self, cmdstr):
        if cmdstr in self.cmdset.keys():
            return 1
        return 0

    def isvalidparameter(self, cmdstr, param):
        if self.log_level is logging.DEBUG:
            logger.debug("Command: %s\r\n" % cmdstr)
            logger.debug("Parameter: %s\r\n" % param)
            # sys.stdout.write("Command: %s\r\n" % cmdstr)
            # sys.stdout.write("Parameter: %s\r\n" % param)

        if self.isvalidcommand(cmdstr) is 1:
            prog = re.compile(self.cmdset[cmdstr][1])
            if prog.match(param) :
                if self.log_level is logging.DEBUG:
                    logger.debug("Valid %s\r\n" % self.cmdset[cmdstr][0])
                    # print("Valid: %s\r\n" % self.cmdset[cmdstr][0])
                return True
            else:
                if self.log_level is logging.DEBUG:
                    logger.debug("Invalid %s\r\n" % self.cmdset[cmdstr][0])
                    # print("Invalid: %s\r\n" % self.cmdset[cmdstr][0])
                return False

        if self.log_level is logging.DEBUG:
            logger.debug("Invalid command\r\n")
        return False

    def getparamdescription(self, cmdstr, param):
        if self.isvalidparameter(cmdstr, param) :
            if len(self.cmdset[cmdstr][2]) > 0 :
                return self.cmdset[cmdstr][2][param]
            else :
                return param

    def getcmddescription(self, cmdstr):
        if self.isvalidcommand(cmdstr) :
            return self.cmdset[cmdstr][0]
        else :
            return "Invalid command"

    def iswritable(self, cmdstr):
        if self.cmdset[cmdstr][3] is "RW":
            return True
        return False

if __name__ == '__main__':
    cmdsetObj = WIZ750CMDSET(logging.DEBUG)

    cmdlist = cmdsetObj.cmdset.items()
    # for i in range(len(cmdlist)):
    #     print(cmdlist[i])
    
    # cmd_index = cmdlist.index('BR')
    # print(cmdlist[cmd_index][0])   

    # 각 command에 대한 정보 출력 => log 기록 시 활용
    cmd = 'SS'
    print('\"%s\": %s\n %s\n' %(cmd, cmdsetObj.cmdset[cmd][0], cmdsetObj.cmdset[cmd][2]))

    # 함수 활용
    print(cmdsetObj.getcmddescription(cmd))
    print(cmdsetObj.getparamdescription(cmd,'2B2C2D'))

    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:33")
    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:34")
    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:35")
    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:36")
    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:37")
    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:08")
    # cmdsetObj.isvalidparameter("MC", "00:08:dc:11:22:GG")

    # cmdsetObj.isvalidparameter("IM", "0")
    # cmdsetObj.isvalidparameter("IM", "1")
    # cmdsetObj.isvalidparameter("IM", "2")

    # print (cmdsetObj.getparamdescription("BR", "3"))
