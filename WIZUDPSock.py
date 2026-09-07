#!/usr/bin/python

import socket


class WIZUDPSock:
    # def __init__(self, port, peerport):
    def __init__(self, port, peerport, ipaddr=None, localport=52000, peer_ip="255.255.255.255"):
        self.sock = None
        # self.localport = randint(52000, 53000)
        self.localport = localport  # 0 = OS가 사용 가능한 포트 자동 할당
        self.peerport = peerport
        self.ipaddr = ipaddr
        # 전송 대상. 장치 검색은 브로드캐스트, 테스트(가짜 장치)는 루프백을 준다
        self.peer_ip = peer_ip

    def open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # socket rcv buffer size
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)  # 512 KB
        # print('getsockopt SO_RCVBUF:', self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))

        # self.sock.bind(("", self.localport))
        self.sock.bind((self.ipaddr, self.localport))
        self.sock.setblocking(False)

    def sendto(self, msg):
        assert self.sock is not None, "sendto() called before open()"
        self.sock.sendto(msg, (self.peer_ip, self.peerport))
        # self.sock.sendto(msg, ("192.168.50.255", self.peerport))

    def recvfrom(self):
        assert self.sock is not None, "recvfrom() called before open()"
        data, addr = self.sock.recvfrom(4096)
        return data, addr

    def close(self):
        """이미 닫혔거나 열린 적 없으면 아무것도 하지 않는다.

        정리 경로가 여러 곳(설정 완료·FW 업로드·리셋·재설정)에 있어 두 번 닫히는 일이
        생긴다. 그때 예외로 번지면 뒤따르는 정리가 통째로 건너뛰어져 소켓이 남는다.
        """
        if self.sock is None:
            return
        try:
            self.sock.close()
        finally:
            self.sock = None
