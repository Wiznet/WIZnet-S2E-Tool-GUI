from enum import Enum

class Opcode(Enum):
    OP_SEARCHALL = 1
    OP_GETCOMMAND = 2
    OP_SETCOMMAND = 3
    OP_SETFILE = 4
    OP_GETFILE = 5
    OP_FWUP = 6

class SockState(Enum):
    SOCK_CLOSE = 10
    SOCK_OPENTRY = 11
    SOCK_OPEN = 12
    SOCK_CONNECTTRY = 13
    SOCK_CONNECT = 14
