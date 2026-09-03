#!/usr/bin/python
# -*- coding: utf-8 -*-

import select
import codecs
import time
from utils import logger

from PyQt5.QtCore import QThread, pyqtSignal
from constants import Opcode
from wizcmdset import Wizcmdset

exitflag = 0

# PACKET_SIZE = 1024
# PACKET_SIZE = 2048
PACKET_SIZE = 4096
MAX_REPLY_CHUNKS = 200      # HIGH-03: 비정상 응답 truncation 상한

# 장치 펌웨어의 설정 요청 버퍼 크기.
# WIZ750SR / WIZ752SR-12x: common.h CONFIG_BUF_SIZE = 512
# WIZ5XXSR-RP(1.0.6): 2048 로 확장됨
# 이를 넘는 요청은 펌웨어에서 recvfrom() 이 버퍼를 오버플로시켜 파싱이 깨진다
# (엉뚱한 커맨드명으로 INVALIDPARAM/NOTAVAIL 반환). 2026-08-18 실기기 확인.
DEVICE_CONFIG_BUF_SIZE = 512
EACH_DEV_LOOP_TIMEOUT = 0.15  # Strategy B: 개별 장치 멀티패킷 수집 루프 타임아웃


def _sanitize_device_name(raw: bytes) -> str:
    """WIZnet 장비 MN 필드 바이트 → str 변환.

    - null 패딩(\\x00) 제거 후 UTF-8 디코딩 시도
    - 실패 시 인쇄 가능 ASCII(0x20~0x7E)와 비정상 바이트를 구분하여,
      연속된 비정상 바이트는 (xxyyzz) 형태로 묶어 표현
      예) b'WIZ\\xff\\xffSR' → 'WIZ(ffff)SR'
    - 빈 bytes / 전체 null → ''
    """
    if not raw:
        return ''
    raw = raw.rstrip(b'\x00')
    if not raw:
        return ''
    try:
        return raw.decode('utf-8')
    except (UnicodeDecodeError, ValueError):
        result = []
        bad_run = []
        for b in raw:
            if 0x20 <= b <= 0x7E:
                if bad_run:
                    result.append('(' + ''.join(f'{x:02x}' for x in bad_run) + ')')
                    bad_run = []
                result.append(chr(b))
            else:
                bad_run.append(b)
        if bad_run:
            result.append('(' + ''.join(f'{x:02x}' for x in bad_run) + ')')
        return ''.join(result)


def parse_reply_lines(data: bytes) -> dict:
    """장치 응답(데이터그램 여러 개를 이어 붙인 것도 됨)을 {커맨드: 값} 으로 푼다.

    MA 줄은 MAC 원시 바이트라 건너뛴다. 같은 커맨드가 두 번 오면 뒤가 이긴다
    (청크 응답마다 MC 가 들어오는데 값은 같다).
    """
    profile = {}
    for line in data.split(b"\r\n"):
        if len(line) < 2 or line[:2] == b"MA":
            continue
        cmd = line[:2].decode('utf-8', errors='replace')
        profile[cmd] = line[2:].decode('utf-8', errors='replace')
    return profile


def timeout_func():
    # print('timeout')
    global exitflag
    exitflag = 1


class WIZMSGHandler(QThread):
    search_result = pyqtSignal(int)
    set_result = pyqtSignal(int)

    searched_data = pyqtSignal(bytes)

    # Configuration class variables (loaded from device_search_config.py)
    loop_select_timeout = 0.5  # Default: Phase 1 loop select timeout (sec)
    emit_stabilization_ms = 50  # Default: emit stabilization delay (ms)
    skip_phase1_emit_delay = False  # Default: do NOT skip (experimental)
    # SET 응답 수신 후 대기(ms). 장치는 SET 직후 리부트하고, 완료 직후 dev_clicked()가
    # 재조회를 보내므로 이 여유가 없으면 리부트 중인 장치가 응답하지 못한다.
    # 기본값 500ms 유지 권장 — 줄이면 구형/느린 장치에서 SET 후 재조회 실패 가능.
    set_command_delay_ms = 500

    # logging.verbose_debug 로 제어 (main_gui 가 설정/갱신)
    verbose_wire_log = False

    def __init__(self, udpsock, cmd_list, what_sock, op_code, timeout, presearch=False):
        QThread.__init__(self)

        self.logger = logger

        self.sock = udpsock
        self.msg = bytearray(PACKET_SIZE)
        self.size = 0

        try:
            self.inputs = [self.sock.sock]
        except Exception as e:
            self.logger.error("socket error:", e)
            self.terminate()

        self.outputs = []
        self.errors = []
        self.opcode = None
        self.presearch = presearch
        self.iter = 0
        self.dest_mac = None
        self.isvalid = False
        # self.timer1 = None
        self.istimeout = False
        self.reply = ""
        self.setting_pw_wrong = False

        self.mac_list = []
        self.mode_list = []
        self.mn_list = []
        self.vr_list = []
        self.getreply = []
        self.rcv_list = []
        self.st_list = []

        self.what_sock = what_sock
        self.cmd_list = cmd_list
        self.opcode = op_code
        # 개별 장치 조회를 여러 요청으로 나눌 때의 목록. for_device_query() 가 채운다.
        self.cmd_chunks = None
        # 그 장치의 응답 버퍼 크기(B). 응답이 여기 닿으면 경고한다. None 이면 검사 안 함.
        self.reply_limit = None

        self.timeout = timeout

        self.cmdset = Wizcmdset("WIZ750SR")

    @classmethod
    def for_device_query(cls, sock, cmd_chunks, what_sock, timeout, reply_limit=None):
        """개별 장치 조회(Phase 3) 전용 생성자. 요청을 청크 목록으로 받는다.

        cmd_chunks 는 WIZMakeCMD.search_chunks() 결과. reply_limit 은 그 장치의 응답
        버퍼 크기(B)로, 모르면 None 으로 두어 크기 경고를 내지 않는다 — 틀린 경고는
        없는 것보다 나쁘다.
        """
        th = cls(sock, cmd_chunks[0], what_sock, Opcode.OP_SEARCHALL, timeout)
        th.cmd_chunks = list(cmd_chunks)
        th.reply_limit = reply_limit
        return th

    def timeout_func(self):
        self.istimeout = True

    def makecommands(self):
        self.size = 0

        try:
            for cmd in self.cmd_list:
                # print('cmd[0]: %s, cmd[1]: %s' % (cmd[0], cmd[1]))
                try:
                    self.msg[self.size :] = str.encode(cmd[0])
                except Exception as e:
                    self.logger.error("[ERROR] makecommands() encode:", cmd[0], e)
                self.size += len(cmd[0])
                if cmd[0] == "MA":
                    # sys.stdout.write('cmd[1]: %r\r\n' % cmd[1])
                    cmd[1] = cmd[1].replace(":", "")
                    # print(cmd[1])
                    # hex_string = cmd[1].decode('hex')
                    try:
                        hex_string = codecs.decode(cmd[1], "hex")
                        self.msg[self.size :] = hex_string
                        self.dest_mac = hex_string
                        # self.dest_mac = (int(cmd[1], 16)).to_bytes(6, byteorder='big') # Hexadecimal string to hexadecimal binary
                        # self.msg[self.size:] = self.dest_mac
                        self.size += 6
                    except Exception as e:
                        self.logger.error(
                            "[ERROR] makecommands() decode:", cmd[0], cmd[1], e
                        )
                else:
                    try:
                        self.msg[self.size :] = str.encode(cmd[1])
                    except Exception as e:
                        self.logger.error(
                            "[ERROR] makecommands() encode param:", cmd[0], cmd[1], e
                        )
                    self.size += len(cmd[1])
                if "\r\n" not in cmd[1]:
                    self.msg[self.size :] = str.encode("\r\n")
                    self.size += 2

                    # print(self.size, self.msg)
        except Exception as e:
            self.logger.error("[ERROR] WIZMSGHandler makecommands(): %r" % e)

        if self.size > DEVICE_CONFIG_BUF_SIZE:
            self.logger.warning(
                f"[SIZE] 요청 {self.size}B 가 장치 설정 버퍼 한계"
                f"({DEVICE_CONFIG_BUF_SIZE}B)를 초과함 — 펌웨어에서 잘리거나 "
                f"파싱이 깨질 수 있음. cmd 수={len(self.cmd_list)}"
            )

        # 와이어 바이트 덤프 (logging.verbose_debug 활성 시에만)
        if WIZMSGHandler.verbose_wire_log:
            try:
                self.logger.debug(
                    f"[WIRE] request opcode={self.opcode} size={self.size}B "
                    f"bytes={bytes(self.msg[:self.size])!r}"
                )
            except Exception as e:
                self.logger.debug(f"[WIRE] request dump failed: {e}")

    def sendcommands(self):
        self.sock.sendto(self.msg)

    def sendcommandsTCP(self):
        self.sock.write(self.msg)

    def check_parameter(self, cmdset):
        # print('check_parameter()', cmdset, cmdset[:2], cmdset[2:])
        try:
            if b"MA" not in cmdset:
                # print('check_parameter() OK', cmdset, cmdset[:2], cmdset[2:])
                if self.cmdset.isvalidparameter(
                    cmdset[:2].decode(), cmdset[2:].decode()
                ):
                    return True
                else:
                    return False
            else:
                return False
        except Exception as e:
            self.logger.error("[ERROR] WIZMSGHandler check_parameter(): %r" % e)

    def _run_each_dev(self):
        """개별 장치 조회(Phase 3). 요청 청크를 순서대로 보내고 응답을 모아 한 번 emit 한다.

        청크에 응답이 없으면 한 번 더 보낸다 — GET 뿐이라 재송신에 부작용이 없다.
        그래도 없으면 이 장치는 emit 하지 않는다. 반쪽 프로파일로 화면을 채우면
        이전 장치 값이 남은 칸과 섞이므로, 검색 목록에 미완료로 남는 편이 정직하다.
        """
        chunks = self.cmd_chunks if self.cmd_chunks else [self.cmd_list]
        total = len(chunks)
        accumulated = b""
        seen = set()
        for idx, chunk in enumerate(chunks, 1):
            self.cmd_list = chunk
            got = b""
            for attempt in (1, 2):
                try:
                    self.makecommands()
                    if self.what_sock == "tcp":
                        self.sendcommandsTCP()
                    else:
                        self.sendcommands()
                except Exception as e:
                    self.logger.error(f"[ERROR] WIZMSGHandler sendcommands: {e}")
                    self.search_result.emit(0)
                    return
                got = self._collect_replies(seen)
                if got:
                    break
                self.logger.warning(
                    f"[QUERY] 조회 청크 {idx}/{total} 무응답 (시도 {attempt}/2)"
                    + (" — 재송신" if attempt == 1 else "")
                )
            if not got:
                self.logger.warning(
                    f"[QUERY] 장치 조회 미완료 — 청크 {idx}/{total} 가 재송신에도 무응답. "
                    f"emit 하지 않음(검색 목록에 미완료로 남김)"
                )
                return
            accumulated += self._finish_chunk_reply(got, idx, total)

        if accumulated:
            self.searched_data.emit(accumulated)
            replylists = accumulated.split(b"\r\n")
            if len(replylists) > MAX_REPLY_CHUNKS:
                self.logger.warning(f"[WIZMsg] 비정상 응답 truncate: {len(replylists)} → {MAX_REPLY_CHUNKS}")
                replylists = replylists[:MAX_REPLY_CHUNKS]
            self.getreply = replylists

    def _collect_replies(self, seen):
        """응답이 조용해질 때까지 모은다. 같은 데이터그램이 두 번 오면 한 번만 센다.

        seen 은 조회 전체에서 공유한다 — 재송신 뒤 첫 응답이 늦게 도착해도 중복되지 않는다.
        """
        buf = b""
        readready, _, _ = select.select(self.inputs, self.outputs, self.errors, self.timeout)
        while readready:
            for sock in readready:
                if sock == self.sock.sock:
                    data, _ = self.sock.recvfrom()
                    self.logger.debug(f"Each-search recv: {len(data)}B")
                    if self.what_sock == "udp":
                        self._warn_if_reply_reaches_buffer(len(data))
                    h = hash(data)
                    if h not in seen:
                        seen.add(h)
                        buf += data
            readready, _, _ = select.select(
                self.inputs, self.outputs, self.errors, EACH_DEV_LOOP_TIMEOUT
            )
        return buf

    def _finish_chunk_reply(self, buf, idx, total):
        """청크 응답 마무리. TCP 는 여기서 크기를 보고, 꼬리에 CRLF 없는 조각은 버린다.

        상한이 들어간 펌웨어는 응답을 줄 중간에서 자른다. 그 조각을 값으로 읽으면
        `SC0` 같은 엉뚱한 값이 화면에 들어가므로 버리고 경고한다. TCP 는 세그먼트가
        줄 중간에서 갈릴 수 있어 데이터그램이 아니라 청크 단위로 본다.
        """
        if self.what_sock != "udp":
            self._warn_if_reply_reaches_buffer(len(buf))
        if not buf.endswith(b"\r\n"):
            cut = buf.rfind(b"\r\n")
            frag = buf[cut + 2:] if cut >= 0 else buf
            self.logger.warning(
                f"[SIZE] 청크 {idx}/{total} 응답 꼬리에 CRLF 없는 조각 {len(frag)}B 폐기: "
                f"{frag[:12]!r} — 장치가 응답을 자른 것으로 보임(상한 있는 펌웨어)"
            )
            buf = buf[:cut + 2] if cut >= 0 else b""
        return buf

    def _warn_if_reply_reaches_buffer(self, nbytes):
        """응답 버퍼 크기를 아는 장치에서 응답이 버퍼에 닿으면 경고한다 — 사후 검출.

        펌웨어는 응답 뒤에 NUL 을 더 쓰므로 nbytes + 1 >= 버퍼면 이미 밖에 썼거나(구형)
        거기서 잘렸다(상한 있는 펌웨어). 예방이 아니라 검출이다. 예방은 요청 분할이 한다.
        """
        if self.reply_limit is None or nbytes + 1 < self.reply_limit:
            return
        self.logger.warning(
            f"[SIZE] 응답 {nbytes}B 가 장치 응답 버퍼({self.reply_limit}B)에 닿음 — "
            f"구형 펌웨어면 버퍼 밖 메모리를 밟았고(장치 전원 재인가 권장), "
            f"상한 있는 펌웨어면 잘렸다. 요청 목록 축소 필요"
        )

    def run(self):
        if self.opcode == Opcode.OP_SEARCHALL and not self.presearch:
            self._run_each_dev()
            return

        _fail_emit = {
            Opcode.OP_SEARCHALL:  (self.search_result, 0),
            Opcode.OP_SETCOMMAND: (self.set_result,    -1),
        }
        t_send = None
        try:
            self.makecommands()
            if self.what_sock == "udp":
                self.sendcommands()
                t_send = time.time()
            elif self.what_sock == "tcp":
                self.sendcommandsTCP()
                t_send = time.time()
        except Exception as e:
            self.logger.error(f"[ERROR] WIZMSGHandler sendcommands: {e}")
            sig, val = _fail_emit.get(self.opcode, (None, None))
            if sig:
                sig.emit(val)
            return

        try:
            _t_sel0 = time.time()
            # if t_send is not None:
            #     self.logger.info(f"[TIMING] +{time.time()-t_send:.3f}s initial select(timeout={self.timeout}s) 시작")
            readready, writeready, errorready = select.select(
                self.inputs, self.outputs, self.errors, self.timeout
            )
            if t_send is not None:
                pass  # self.logger.info(f"[TIMING] +{time.time()-t_send:.3f}s initial select 완료 ({(time.time()-_t_sel0)*1000:.0f}ms 소요, ready={len(readready)})")

            replylists = None

            self.getreply = []
            self.mac_list = []
            self.mn_list = []
            self.vr_list = []
            self.st_list = []
            self.rcv_list = []
            # print('readready value: ', len(readready), readready)

            # Pre search
            per_addr_buf = {}   # Strategy C: addr → accumulated bytes
            per_addr_seen = {}  # Strategy C: addr → hash set (per-source dedup)
            while True:
                self.iter += 1
                # sys.stdout.write("iter count: %r " % self.iter)
                for sock in readready:
                    if sock == self.sock.sock:
                        data, addr = self.sock.recvfrom()
                        if t_send is not None:
                            self.logger.debug(f"[TIMING] iter={self.iter} recv #{len(self.rcv_list)+1} at +{time.time()-t_send:.3f}s")
                        self.logger.debug(f"Pre-search recv: {len(data)}B from {addr}")
                        # self.searched_data.emit(data)

                        # check if data reduplication
                        if data in self.rcv_list:
                            replylists = []
                        else:
                            self.rcv_list.append(data)  # received data backup
                            replylists = data.split(b"\r\n")
                            if len(replylists) > MAX_REPLY_CHUNKS:
                                self.logger.warning(f"[WIZMsg] 비정상 응답 truncate: {len(replylists)} → {MAX_REPLY_CHUNKS}")
                                replylists = replylists[:MAX_REPLY_CHUNKS]
                            self.getreply = replylists

                        if self.opcode == Opcode.OP_SEARCHALL:
                            # Strategy C: per-addr 누적 — 파싱은 루프 종료 후 일괄 처리
                            h = hash(data)
                            if addr not in per_addr_buf:
                                per_addr_buf[addr] = b""
                                per_addr_seen[addr] = set()
                            if h not in per_addr_seen[addr]:
                                per_addr_seen[addr].add(h)
                                per_addr_buf[addr] += data
                        elif self.opcode == Opcode.OP_FWUP:
                            for i in range(0, len(replylists)):
                                if b"MA" in replylists[i][:2]:
                                    pass
                                    # self.isvalid = True
                                else:
                                    self.isvalid = False
                                # sys.stdout.write("%r\r\n" % replylists[i][:2])
                                if b"FW" in replylists[i][:2]:
                                    # sys.stdout.write('self.isvalid == True\r\n')
                                    # param = replylists[i][2:].split(b':')
                                    self.reply = replylists[i][2:]
                        elif self.opcode == Opcode.OP_SETCOMMAND:
                            for i in range(0, len(replylists)):
                                if b"AP" in replylists[i][:2]:
                                    if replylists[i][2:] == b" ":
                                        self.setting_pw_wrong = True
                                    else:
                                        self.setting_pw_wrong = False

                if t_send is not None:
                    self.logger.debug(f"[TIMING] +{time.time()-t_send:.3f}s iter={self.iter} 루프 select(1s) 시작")
                _t_loop_sel = time.time()
                readready, writeready, errorready = select.select(
                    self.inputs, self.outputs, self.errors, WIZMSGHandler.loop_select_timeout
                )
                if t_send is not None:
                    self.logger.debug(f"[TIMING] +{time.time()-t_send:.3f}s iter={self.iter} 루프 select 완료 ({(time.time()-_t_loop_sel)*1000:.0f}ms 소요, ready={len(readready)})")

                if not readready or not replylists:
                    break

            if self.opcode == Opcode.OP_SEARCHALL:
                # Strategy C: 루프 종료 후 addr별 누적 데이터 파싱 → mac_list 구성
                for _addr, _accumulated in per_addr_buf.items():
                    try:
                        _replylists = _accumulated.split(b"\r\n")
                        if len(_replylists) > MAX_REPLY_CHUNKS:
                            self.logger.warning(f"[WIZMsg] 비정상 응답 truncate: {len(_replylists)} → {MAX_REPLY_CHUNKS}")
                            _replylists = _replylists[:MAX_REPLY_CHUNKS]
                        pkt = {}
                        for line in _replylists:
                            if len(line) < 2:
                                continue
                            if line[:2] == b"MA":
                                continue
                            try:
                                cmd = line[:2].decode('ascii')
                            except Exception:
                                continue
                            pkt[cmd] = line[2:]
                        if 'MC' in pkt and self.check_parameter(b"MC" + pkt['MC']):
                            self.mac_list.append(pkt['MC'])
                            self.mn_list.append(_sanitize_device_name(pkt.get('MN', b'')))
                            self.vr_list.append(pkt.get('VR', b''))
                            self.mode_list.append(pkt.get('OP', b''))
                            self.st_list.append(pkt.get('ST', b''))
                    except Exception as e:
                        self.logger.error("[ERROR] WIZMSGHandler OP_SEARCHALL: %r" % e)

                if t_send is not None:
                    t_loop_break = time.time()
                    self.logger.debug(f"[TIMING] loop broke at +{t_loop_break-t_send:.3f}s, {len(self.mac_list)} devices found")

                # Phase 1 emit 전 안정화 대기 (실험적 플래그로 제어)
                if not WIZMSGHandler.skip_phase1_emit_delay:
                    self.msleep(WIZMSGHandler.emit_stabilization_ms)
                    if t_send is not None:
                        self.logger.debug(f"[TIMING] after msleep({WIZMSGHandler.emit_stabilization_ms}): +{time.time()-t_send:.3f}s → emitting result")
                else:
                    # 실험적: msleep 생략 (PyQt signal queue 불안정 가능성)
                    if t_send is not None:
                        self.logger.warning(f"[TIMING] EXPERIMENTAL: skipped msleep({WIZMSGHandler.emit_stabilization_ms}) → emitting result immediately")

                self.search_result.emit(len(self.mac_list))
            if self.opcode == Opcode.OP_SETCOMMAND:
                self.msleep(WIZMSGHandler.set_command_delay_ms)
                if len(self.rcv_list) > 0:
                    if self.setting_pw_wrong:
                        self.set_result.emit(-3)
                    else:
                        self.set_result.emit(len(self.rcv_list[0]))
                else:
                    self.set_result.emit(-1)
            elif self.opcode == Opcode.OP_FWUP:
                return self.reply
            # sys.stdout.write("%s\r\n" % self.mac_list)
        except Exception as e:
            self.logger.error(f"[ERROR] WIZMSGHandler error: {e}")
            sig, val = _fail_emit.get(self.opcode, (None, None))
            if sig:
                sig.emit(val)


class DataRefresh(QThread):
    resp_check = pyqtSignal(int)

    _seq = 0    # 인스턴스 식별 순번 (로그 추적용)

    def __init__(self, sock, cmd_list, what_sock, interval):
        QThread.__init__(self)

        self.logger = logger

        self.sock = sock
        self.msg = bytearray(PACKET_SIZE)
        self.size = 0

        self.inputs = [self.sock.sock]
        self.outputs = []
        self.errors = []

        self.iter = 0
        self.dest_mac = None
        self.reply = ""

        self.mac_list = []
        self.rcv_list = []

        self.what_sock = what_sock
        self.cmd_list = cmd_list
        self.interval = interval * 1000

        # 인스턴스 식별 순번.
        # refresh_gpio() 가 새 인스턴스를 만들 때 이전 것을 terminate() 하지만
        # 실제로 죽었는지 보장이 없다. 로그에서 어느 스레드가 보내고 받았는지
        # 구분하려면 식별자가 필요하다.
        DataRefresh._seq += 1
        self.inst_id = DataRefresh._seq

    def makecommands(self):
        self.size = 0

        for cmd in self.cmd_list:
            self.msg[self.size :] = str.encode(cmd[0])
            self.size += len(cmd[0])
            if cmd[0] == "MA":
                cmd[1] = cmd[1].replace(":", "")
                hex_string = codecs.decode(cmd[1], "hex")

                self.msg[self.size :] = hex_string
                self.dest_mac = hex_string
                self.size += 6
            else:
                self.msg[self.size :] = str.encode(cmd[1])
                self.size += len(cmd[1])
            if "\r\n" not in cmd[1]:
                self.msg[self.size :] = str.encode("\r\n")
                self.size += 2

    def _wire_log(self, msg):
        """logging.verbose_debug 가 켜져 있을 때만 남기는 와이어 로그.

        WIZMSGHandler 와 같은 스위치를 쓴다. GPIO 조회는 이 클래스가 담당하는데
        지금까지 요청·응답이 어디에도 기록되지 않아 장치가 무엇을 답했는지
        확인할 수 없었다.
        """
        if WIZMSGHandler.verbose_wire_log:
            self.logger.debug(f"[WIRE][DataRefresh#{self.inst_id}] {msg}")

    def sendcommands(self):
        self._wire_log(
            f"request size={self.size}B bytes={bytes(self.msg[:self.size])!r}"
        )
        self.sock.sendto(self.msg)

    def sendcommandsTCP(self):
        self._wire_log(
            f"request(tcp) size={self.size}B bytes={bytes(self.msg[:self.size])!r}"
        )
        self.sock.write(self.msg)

    def run(self):
        try:
            self.makecommands()
            if self.what_sock == "udp":
                self.sendcommands()
            elif self.what_sock == "tcp":
                self.sendcommandsTCP()
        except Exception as e:
            self.logger.error(str(e))

        # replylists = None
        checknum = 0

        try:
            while True:
                self.rcv_list = []
                readready, writeready, errorready = select.select(
                    self.inputs, self.outputs, self.errors, 2
                )

                self.iter += 1
                # sys.stdout.write("iter count: %r " % self.iter)

                for sock in readready:
                    self.logger.info(f"DataRefresh#{self.inst_id}: {checknum}")

                    if sock == self.sock.sock:
                        data, _ = self.sock.recvfrom()
                        self.rcv_list.append(data)  # 수신 데이터 저장
                        self._wire_log(
                            f"reply iter={checknum} len={len(data)}B bytes={data!r}"
                        )
                        # replylists = data.splitlines()
                        # replylists = data.split(b"\r\n")
                        # print('replylists', replylists)

                checknum += 1
                # emit 하는 쪽을 남긴다. 이전 인스턴스가 terminate() 후에도 살아
                # 남아 함께 emit 하면 gpio_update() 는 출처를 구분하지 못한 채
                # 항상 현재 self.datarefresh 의 rcv_list 를 읽는다.
                self._wire_log(f"emit({checknum}) rcv_list={len(self.rcv_list)}")
                self.resp_check.emit(checknum)
                if self.interval == 0:
                    break
                else:
                    self.msleep(self.interval)
                self.sendcommands()
        except Exception as e:
            self.logger.error(f"[ERROR] DataRefresh error: {e}")
