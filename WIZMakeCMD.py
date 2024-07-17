# -*- coding: utf-8 -*-
from packaging.version import Version

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
    "WIZ107SR",
    "WIZ108SR",
    "W7500-S2E",
    "W7500P-S2E",
]
SECURITY_DEVICE = ["WIZ510SSL", "WIZ5XXSR-RP", "WIZ5XXSR-RP_E-SAVE"]
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
    "MC", "VR", "MN", "UN", "ST", "IM", "OP", "CP", "PO", "DG", 
    "KA", "KI", "KE", "RI", "LI", "SM", "GW", "DS", "PI", "PP",
    "DX", "DP", "DI", "DW", "DH", "LP", "RP", "RH", "BR", "DB",
    "PR", "SB", "FL", "IT", "PT", "PS", "PD", "TE", "SS", "NP",
    "SP"
]
cmd_wiz75xsr = ["S0", "S1"]
cmd_added = ["SC", "TR"]  # for WIZ750SR F/W version 1.2.0 or later
cmd_ch2 = [
    "QS", "QO", "QH", "QP", "QL", "RV", "RA", "RE", "RR", "EN",
    "RS", "EB", "ED", "EP", "ES", "EF", "E0", "E1", "NT", "NS",
    "ND"
]

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

# WIZ5XXSR-RP_E-SAVE commands
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


# @TODO:@BUG 아래 경우 1을 반환해야 하는데 -1을 반환함
# >>> version_compare("1.10.8.1.9", "1.2.8")
# version_compare: obj1 = ['1', '10', '8', '1', '9'] , obj2 = ['1', '2', '8'] , obj1 > obj2 = 0 obj1 < obj2 = 1
# -1
def version_compare_old(version1: str, version2: str):
    """버전을 비교해서 앞이 크면 1 뒤가 크면 -1 같으면 0을 반환
    Args:
        version1 (str): 첫번째 버전
        version2 (str): 두번째 버전
    """
    def normalize(v):
        # return [x for x in re.sub(r'(\.0+)*$','',v).split('.')]
        return [x for x in re.sub(r"(\.0+\.[dev])*$", "", v).split(".")]
    obj1 = normalize(version1)
    obj2 = normalize(version2)
    print("version_compare: obj1 =", obj1, ", obj2 =", obj2, ", obj1 > obj2 =", int(obj1 > obj2), "obj1 < obj2 =", int(obj1 < obj2))
    return (obj1 > obj2) - (obj1 < obj2)
    # if return value < 0: version2 upper than version1


# 이슈 수정 중 함수 버그 발견해서 수정함 #36
def version_compare(version1: str, version2: str):
    """버전을 비교해서 앞이 크면 1 뒤가 크면 -1 같으면 0을 반환
    Args:
        version1 (str): 첫번째 버전
        version2 (str): 두번째 버전
    """
    return 0 if version1 == version2 else -1 if Version(version1) < Version(version2) else 1


class WIZMakeCMD:
    def __init__(self):
        self.logger = logger

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

    def search(self, mac_addr, idcode, devname, version, devstatus=None):
        # Search All Devices on the network
        # print('search()', mac_addr, idcode, devname, version)
        cmd_list = self.make_header(mac_addr, idcode)

        if devname in ONE_PORT_DEV:
            # WIZ107SR/WIZ108SR
            if "WIZ107SR" in devname or "WIZ108SR" in devname:
                for cmd in cmd_1p_default:
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
            self.logger.info(f'[Search] Security device: {devname}')
            if 'WIZ510SSL' in devname:
                for cmd in cmd_wiz510ssl:
                    cmd_list.append([cmd, ""])
            elif 'WIZ5XXSR' in devname:
                print(f"search::devstatus={devstatus}")
                if devstatus == 'BOOT':
                    for cmd in cmd_1p_boot:
                        cmd_list.append([cmd, ""])
                    print(f"search::cmd_list={cmd_list}")
                    return cmd_list
                # 버전이 1.0.8 이상인 경우에만 "PO" 추가 #36
                temp_cmd_wiz5xxsr = (cmd_wiz5xxsr + ["PO"]) if version_compare("1.0.8", version) <= 0  else cmd_wiz5xxsr
                for cmd in temp_cmd_wiz5xxsr:
                    cmd_list.append([cmd, ""])
                print(f"search::cmd_list2={cmd_list}")
                # Commands for E-SAVE
                #if 'E-SAVE' in devname:
                #    for cmd in cmd_wiz5xxsr_esave:
                #        cmd_list.append([cmd, ""])
        else:
            pass
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
        print(f"devname={devname}, cmds={cmd_list}")
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
                # WIZ107SR/WIZ108SR
                if "WIZ107SR" in devname or "WIZ108SR" in devname:
                    for cmd in cmd_1p_default:
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
                # for WIZ752SR-12x
                for cmd in cmd_ch2:
                    cmd_list.append([cmd, ""])
            elif devname in SECURITY_DEVICE:
                if 'WIZ510SSL' in devname:
                    for cmd in cmd_wiz510ssl:
                        cmd_list.append([cmd, ""])
                elif 'WIZ5XXSR' in devname:
                    if status != "BOOT":
                        for cmd in cmd_wiz5xxsr:
                            cmd_list.append([cmd, ""])
                    else:
                        for cmd in cmd_1p_boot:
                            cmd_list.append([cmd, ""])
                    # Commands for E-SAVE
                    #if 'E-SAVE' in devname:
                    #    for cmd in cmd_wiz5xxsr_esave:
                    #        cmd_list.append([cmd, ""])
            # if status == "BOOT":
            #     return cmd_list
            cmd_list.append(["SV", ""])  # save device setting
            cmd_list.append(["RT", ""])  # Device reboot
            # print("setcommand()", cmd_list)
            return cmd_list
        except Exception as e:
            self.logger.error("[ERROR] setcommand(): %r\r\n" % e)

    def reset(self, mac_addr, idcode, set_pw, devname):
        self.logger.info(f'Reset: {mac_addr}')
        try:
            print("reset", mac_addr, idcode, set_pw, devname)
            cmd_list = self.make_header(mac_addr, idcode, devname=devname, set_pw=set_pw)
            cmd_list.append(["RT", ""])
        except Exception as e:
            self.logger.error(e)
        return cmd_list

    def factory_reset(self, mac_addr, idcode, set_pw, devname, param):
        self.logger.info(f'Factory: {mac_addr}')
        try:
            cmd_list = self.make_header(mac_addr, idcode, devname=devname, set_pw=set_pw)
            cmd_list.append(["FR", param])
        except Exception as e:
            self.logger.error(e)
        return cmd_list
