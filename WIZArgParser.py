#!/usr/bin/python
# -*- coding: utf-8 -*-

# Argument set Module

import argparse
import logging
import sys

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

class WIZArgParser:
    # Test argument
    def test_arg(self):
        parser = argparse.ArgumentParser(description='<WIZnet CLI Test Tool>',
                                        epilog=None,
                                        formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('device', help='Serial device name (ex: /dev/ttyUSB0 or COMX)')
        parser.add_argument('-r', '--retry', type=int, default=5, help='Test retry number (default: 5)')
        # parser.add_argument('-t', '--target', help='Target IP address')
        parser.add_argument('-b', '--baud', default='115200', help='Baud rate (300 to 230400)')

        args = parser.parse_args()
        return args

    def loopback_arg(self):
        parser = argparse.ArgumentParser(description='<WIZnet CLI Multiple Test Tool>',
                                        epilog=None,
                                        formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-s', '--select', choices=['1','2'], default='1', 
                                help='Select number of serial port (1: One port S2E, 2: Two port S2E)')
        parser.add_argument('-t', '--targetip', help='Target IP address')
        parser.add_argument('-r', '--retry', type=int, default=5, help='Test retry number (default: 5)')
        

        args = parser.parse_args()
        return args

    # Config argument
    def config_arg(self):
        parser = argparse.ArgumentParser(description='<WIZnet CLI Configuration Tool>', 
                                        epilog=None,
                                        formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-d', '--device', dest='macaddr', help='Device mac address to configuration')
        parser.add_argument('-a', '--all', action='store_true', help='Configuration about all devices (in mac_list.txt)')
        parser.add_argument('-c', '--clear', action='store_true', help='Mac list clear')

        group = parser.add_argument_group('Configuration')
        group.add_argument('-s', '--search', action='store_true', help='Search devices (in same network)') 
        group.add_argument('-r', '--reset', action='store_true', help='Reboot device')
        group.add_argument('-f', '--factory', action='store_true', help='Factory reset')
        # multi ip set
        group.add_argument('-m', '--multiset', metavar='ipaddr', help='Set IP address for all devices in \'mac_list.txt\'. Parameter is first address.')
        # F/W upload
        group.add_argument('-u', '--upload', dest='fwfile', help='Firmware upload from file')
        
        ## Network config
        group = parser.add_argument_group('General Options')
        group.add_argument('--alloc', choices=['0', '1'], help='IP address allocation method (0: Static, 1: DHCP)')
        group.add_argument('--ip', help='Local ip address')
        group.add_argument('--subnet', help='Subnet mask')
        group.add_argument('--gw', help='Gateway address')
        group.add_argument('--dns', help='DNS server address')
        
        ### Channel 0 options
        group = parser.add_argument_group('Channel #0 Options')
        group.add_argument('--port0', help='Local port number')
        group.add_argument('--nmode0', choices=['0', '1', '2', '3'],
                help='Network operation mode (0: tcpclient, 1: tcpserver, 2: mixed, 3: udp)')
        group.add_argument('--rip0', metavar='IP', help='Remote host IP address / Domain')
        group.add_argument('--rport0', metavar='PORT', help='Remote host port number')

        group.add_argument('--baud0', type=int, help='baud rate (300|600|1200|1800|2400|4800|9600|14400|19200|28800|38400|57600|115200|230400)')
        group.add_argument('--data0', choices=['0','1'], help='data bit (0: 7-bit, 1: 8-bit)')
        group.add_argument('--parity0', choices=['0','1','2'], help='parity bit (0: NONE, 1: ODD, 2: EVEN)')
        group.add_argument('--stop0', choices=['0','1'], help='stop bit (0: 1-bit, 1: 2-bit)')
        group.add_argument('--flow0', choices=['0','1','2'], help='flow control (0: NONE, 1: XON/XOFF, 2: RTS/CTS)')
        group.add_argument('--time0', help='Time delimiter (0: Not use / 1~65535: Data packing time (Unit: millisecond))')
        group.add_argument('--size0', help='Data size delimiter (0: Not use / 1~255: Data packing size (Unit: byte))')
        group.add_argument('--char0', help='Designated character delimiter (00: Not use / Other: Designated character)')
        
        group.add_argument('--it', metavar='timer', 
                help='''Inactivity timer value for TCP connection close\nwhen there is no data exchange (0: Not use / 1~65535: timer value)''')

        group.add_argument('--ka', choices=['0','1'], help='Keep-alive packet transmit enable for checking TCP connection established')
        group.add_argument('--ki', metavar='number', 
                help='''Initial TCP keep-alive packet transmission interval value\n(0: Not use / 1~65535: Initial Keep-alive packet transmission interval (Unit: millisecond))''')
        group.add_argument('--ke', metavar='number', 
                help='''TCP Keep-alive packet transmission retry interval value\n(0: Not use / 1~65535: Keep-alive packet transmission retry interval (Unit: millisecond))''')
        group.add_argument('--ri', metavar='number', 
                help='''TCP client reconnection interval value [TCP client only]\n(0: Not use / 1~65535: TCP client reconnection interval (Unit: millisecond))''')
        # group.add_argument('--ec',  choices=['0','1'], help='UART Echoback function enable (Data UART port)')

        ## Channel 1 options
        group = parser.add_argument_group('Channel #1 Options')
        group.add_argument('--port1', help='Local port number')
        group.add_argument('--nmode1', choices=['0', '1', '2', '3'],
                help='Network operation mode (0: tcpclient, 1: tcpserver, 2: mixed, 3: udp)')
        group.add_argument('--rip1', metavar='IP', help='Remote host IP address / Domain')
        group.add_argument('--rport1', metavar='PORT', help='Remote host port number')
        
        group.add_argument('--baud1', type=int, help='baud rate (300|600|1200|1800|2400|4800|9600|14400|19200|28800|38400|57600|115200|230400)')
        group.add_argument('--data1', choices=['0','1'], help='data bit (0: 7-bit, 1: 8-bit)')
        group.add_argument('--parity1', choices=['0','1','2'], help='parity bit (0: NONE, 1: ODD, 2: EVEN)')
        group.add_argument('--stop1', choices=['0','1'], help='stop bit (0: 1-bit, 1: 2-bit)')
        group.add_argument('--flow1', choices=['0','1','2'], help='flow control (0: NONE, 1: XON/XOFF, 2: RTS/CTS)')
        group.add_argument('--time1', help='Time delimiter (0: Not use / 1~65535: Data packing time (Unit: millisecond))')
        group.add_argument('--size1', help='Data size delimiter (0: Not use / 1~255: Data packing size (Unit: byte))')
        group.add_argument('--char1', help='Designated character delimiter (00: Not use / Other: Designated character)')
        
        group.add_argument('--rv', metavar='timer', 
                help='''Inactivity timer value for TCP connection close\nwhen there is no data exchange (0: Not use / 1~65535: timer value)''')
        group.add_argument('--ra', choices=['0','1'], help='Keep-alive packet transmit enable for checking TCP connection established')
        group.add_argument('--rs', metavar='number', 
                help='''Initial TCP keep-alive packet transmission interval value\n(0: Not use / 1~65535: Initial Keep-alive packet transmission interval (Unit: millisecond))''')
        group.add_argument('--re', metavar='number', 
                help='''TCP Keep-alive packet transmission retry interval value\n(0: Not use / 1~65535: Keep-alive packet transmission retry interval (Unit: millisecond))''')
        group.add_argument('--rr', metavar='number', 
                help='''TCP client reconnection interval value [TCP client only]\n(0: Not use / 1~65535: TCP client reconnection interval (Unit: millisecond))''')
        
        ## Command mode switch settings
        group = parser.add_argument_group('UART Command mode switch settings')
        group.add_argument('--te', choices=['0','1'], help='Serial command mode switch code enable')
        group.add_argument('--ss', metavar='3-byte hex', help='Serial command mode switch code (default: 2B2B2B)')

        ## etc options
        group = parser.add_argument_group('ETC options')
        group.add_argument('--cp', choices=['0','1'], help='TCP connection password enable [TCP server mode only]')
        group.add_argument('--np', metavar='pw', help='TCP connection password (string, up to 8 bytes / default: None) [TCP server mode only]')
        group.add_argument('--sp', metavar='value', help='Search identification code (string, up to 8 bytes / default: None)')
        group.add_argument('--dg', choices=['0','1'], help='Serial debug message enable (Debug UART port)')

        ## Config from file
        group = parser.add_argument_group('\nConfiguration from File')

        group.add_argument('--setfile', help='File name to Set')
        group.add_argument('--getfile', help='File name to Get info. Refer default command(cmd_oneport.txt or cmd_twoport.txt).')

        args = parser.parse_args()
        return args