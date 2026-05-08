"""
test_udp_receiver.py — UDP 수신 패턴 종합 테스트

검증 항목:
  ① 수신 패킷 수 / 크기 / MD5
  ② 현재 코드(패킷별 개별 처리, A) vs. 누적 처리(B) 커맨드 비교
  ③ 중복 패킷 필터링 동작
  ④ DoS 패킷 시 MAX_REPLY_CHUNKS 작동 여부

사용법:
  python test_udp_receiver.py                     # 기본
  python test_udp_receiver.py --timeout 1         # 루프 타임아웃 1초
  python test_udp_receiver.py --log recv.log      # 콘솔 + 파일 동시 저장
  python test_udp_receiver.py --ready-file /tmp/recv_ready  # 바인드 완료 신호 파일
"""
import socket
import select
import sys
import hashlib
import argparse
import logging
import os
import time

LISTEN_PORT = 50002
MAX_REPLY_CHUNKS = 200   # HIGH-03 수정 값과 동일

# ── 로거 설정 ─────────────────────────────────────────────────────

logger = logging.getLogger("udp_recv")


def setup_logging(log_path: str | None):
    """콘솔 + 파일(옵션) 동시 출력 로거 설정."""
    fmt = logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S.%f"[:-3])
    logger.setLevel(logging.DEBUG)

    # 콘솔 핸들러 (항상)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # 파일 핸들러 (--log 지정 시)
    if log_path:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.info(f"로그 파일: {os.path.abspath(log_path)}")


def log(msg: str):
    """타임스탬프 없이 구조 출력이 필요한 섹션용 단순 래퍼."""
    logger.info(msg)


# ── 파싱 헬퍼 ────────────────────────────────────────────────────

def parse_commands(data: bytes) -> dict:
    """b'XXVALUE\\r\\n...' → {b'XX': b'VALUE', ...}"""
    cmds = {}
    for line in data.split(b"\r\n"):
        if len(line) < 2:
            continue
        key = line[:2]
        if key == b"MA":
            continue  # 바이너리 MAC — 스킵
        cmds[key] = line[2:]
    return cmds


# ── 수신 루프 ────────────────────────────────────────────────────

def receive_all(sock, initial_timeout, loop_timeout, ready_file: str | None) -> list[tuple]:
    """select 루프로 모든 패킷 수신. [(data, addr), ...] 반환."""
    packets = []

    # 바인드 완료 신호 파일 (송신기 동기화용)
    # select() 진입 전에 신호를 써야 하지만, Windows 소켓 warm-up을 위해
    # 신호 쓰기 → 0.3s 대기 → select() 순서로 진행.
    # 패킷이 대기 중에 도착해도 커널 버퍼에 보존되므로 select()가 즉시 반환.
    if ready_file:
        with open(ready_file, "w") as f:
            f.write("READY\n")
        log(f"[수신] 준비 완료 신호: {ready_file}")
        time.sleep(0.05)  # Windows 소켓 초기화 안정화 — select() 진입을 패킷 도착보다 먼저

    readready, _, _ = select.select([sock], [], [], initial_timeout)
    if not readready:
        log(f"  ⚠️  타임아웃({initial_timeout}s): 패킷 없음 (송신기가 실행됐나요?)")
        return packets

    while readready:
        data, addr = sock.recvfrom(65535)   # 최대 UDP 페이로드
        h = hashlib.md5(data).hexdigest()[:8]
        is_dup = any(d == data for d, _ in packets)
        dup_mark = "  ⚠️ 중복!" if is_dup else ""
        log(f"  📦 패킷 #{len(packets) + 1}: {len(data)}B  from={addr}  md5={h}{dup_mark}")
        packets.append((data, addr))
        readready, _, _ = select.select([sock], [], [], loop_timeout)

    return packets


# ── 분석: [A] 현재 코드 vs [B] 누적 처리 ────────────────────────

def analyze(packets: list[tuple]):
    """수신된 패킷들을 A(현재)/B(누적) 두 방식으로 분석하고 비교 요약 출력."""

    # ── [A] 현재 WIZMSGHandler 동작 (패킷별 덮어쓰기) ──────────
    log("")
    log("─" * 60)
    log("[A] 현재 WIZMSGHandler 동작: 패킷별 개별 파싱")
    log("    self.getreply = replylists 로 매 패킷 덮어씀 → 마지막 패킷만 남음")

    all_per_pkt_cmds = []
    for i, (data, addr) in enumerate(packets):
        cmds = parse_commands(data)
        all_per_pkt_cmds.append(cmds)
        keys_str = str([k.decode(errors='replace') for k in cmds])
        log(f"  패킷 {i + 1}: {len(data)}B  커맨드 {len(cmds)}개: {keys_str}")

    a_final_cmds = {}
    a_lost = 0
    if packets:
        a_final_cmds = all_per_pkt_cmds[-1]
        total_unique = len({k for cmds in all_per_pkt_cmds for k in cmds})
        a_lost = total_unique - len(a_final_cmds)
        log(f"\n  → self.getreply 최종 보유: 패킷 {len(packets)}번 커맨드 {len(a_final_cmds)}개")
        if a_lost > 0:
            log(f"  ❌ [A] 손실 커맨드 수: {a_lost}개  (패킷 1~{len(packets) - 1} 데이터 누락)")
        else:
            log("  ✅ [A] 단일 패킷 — 손실 없음")

    # ── [B] 누적 처리 (수정안) ──────────────────────────────────
    log("")
    log("─" * 60)
    log("[B] 수정 후 동작: 패킷 전부 수집 후 누적 → 한 번에 파싱")

    seen = set()
    unique_chunks = []
    for data, _ in packets:
        h = hashlib.md5(data).hexdigest()
        if h not in seen:
            seen.add(h)
            unique_chunks.append(data)

    accumulated = b"".join(unique_chunks)
    all_lines = accumulated.split(b"\r\n")
    log(f"  누적 데이터: {len(accumulated)}B  → split: {len(all_lines)}개 항목")

    # DoS truncation 시뮬레이션
    truncated = False
    if len(all_lines) > MAX_REPLY_CHUNKS:
        log(f"  ⚠️  MAX_REPLY_CHUNKS({MAX_REPLY_CHUNKS}) 초과 → truncation 적용")
        all_lines = all_lines[:MAX_REPLY_CHUNKS]
        truncated = True

    all_cmds = parse_commands(accumulated)
    keys_str = str([k.decode(errors='replace') for k in all_cmds])
    log(f"  전체 커맨드 ({len(all_cmds)}개): {keys_str}")

    cert_keys = [k.decode() for k in all_cmds if k in (b"CA", b"CC", b"CK")]
    mqtt_keys = [k.decode() for k in all_cmds if k.startswith(b"Q")]
    base_keys = [k.decode() for k in all_cmds
                 if k not in (b"CA", b"CC", b"CK") and not k.startswith(b"Q")]
    log(f"  기본 커맨드 : {base_keys}")
    log(f"  MQTT 커맨드 : {mqtt_keys}")
    log(f"  인증서 커맨드: {cert_keys}")

    # ── 비교 요약 ────────────────────────────────────────────────
    log("")
    log("─" * 60)
    log("[A vs B 비교 요약]")
    log(f"  [A] 현재 코드 — 보유 커맨드: {len(a_final_cmds)}개"
        + (f"  ❌ ({a_lost}개 손실)" if a_lost > 0 else "  ✅ 손실 없음"))
    log(f"  [B] 누적 처리 — 보유 커맨드: {len(all_cmds)}개"
        + ("  (truncation 적용)" if truncated else "  ✅"))

    if a_lost > 0:
        log(f"  → 누적 처리로 {a_lost}개 커맨드 추가 복구됨")
    else:
        log("  → 단일 패킷이므로 두 방식 결과 동일")

    return accumulated, all_cmds


# ── [C] 전략 A+B 시뮬레이션 ──────────────────────────────────────
#
# WIZMSGHandler.py 경로1 (OP_SEARCHALL + presearch=False) 의
# 현재 동작 vs 수정안 동작을 모의 실행하여 dev_profile 결과 비교.
#
# getsearch_each_dev()가 searched_data 시그널로 받은 bytes를 파싱해
# dev_profile[mc] 에 저장하는 구조를 그대로 재현.

EACH_DEV_LOOP_TIMEOUT = 0.15  # 전략 B 상수


def _build_dev_profile(raw: bytes) -> dict:
    """getsearch_each_dev() 내 파싱 로직을 그대로 재현.
    raw bytes → profile dict (key: str, val: str).
    MC 없으면 빈 dict 반환 (에러 상황).
    """
    profile = {}
    for line in raw.split(b"\r\n"):
        if len(line) < 2 or line[:2] == b"MA":
            continue
        cmd = line[:2].decode("utf-8", errors="replace")
        val = line[2:].decode("utf-8", errors="replace")
        profile[cmd] = val
    return profile


def simulate_path1(packets: list[tuple]):
    """[C] 경로1 시뮬레이션: 현재 vs 전략 A+B."""
    log("")
    log("=" * 60)
    log("[C] 경로1 시뮬레이션 (getsearch_each_dev 관점)")
    log("    presearch=False 경로: 사용자가 장치 클릭 → 개별 조회 응답 처리")

    if not packets:
        log("  수신 패킷 없음 — 시뮬레이션 불가")
        return

    # ── [C-현재] 단일 recvfrom (현재 코드) ──────────────────────
    log("")
    log("─" * 60)
    log("[C-현재] 단일 recvfrom — 첫 패킷만 처리")
    log("  WIZMSGHandler.py L218: data = self.sock.recvfrom()  # 1회만")
    log("  searched_data.emit(data) → getsearch_each_dev(data)")

    first_data = packets[0][0]
    profile_old = _build_dev_profile(first_data)
    mc = profile_old.get("MC", "")

    log(f"  수신 바이트: {len(first_data)}B")
    if mc:
        log(f"  dev_profile['{mc}'] 키: {list(profile_old.keys())}")
        cert_keys = [k for k in profile_old if k in ("CA", "CC", "CK")]
        mqtt_keys = [k for k in profile_old if k.startswith("Q")]
        log(f"    기본 커맨드 : {[k for k in profile_old if k not in ('CA', 'CC', 'CK') and not k.startswith('Q')]}")
        log(f"    MQTT 커맨드 : {mqtt_keys}  {'❌ 없음' if not mqtt_keys else '✅'}")
        log(f"    인증서 커맨드: {cert_keys}  {'❌ 없음' if not cert_keys else '✅'}")
    else:
        log("  ❌ MC 필드 없음 → dev_profile 저장 실패 (에러 로그 출력됨)")

    if len(packets) > 1:
        lost_keys = set()
        for data, _ in packets[1:]:
            p = _build_dev_profile(data)
            lost_keys.update(p.keys())
        lost_keys -= set(profile_old.keys())
        log(f"  ❌ 누락된 패킷 수: {len(packets) - 1}개")
        log(f"  ❌ fill_devinfo에서 표시 불가한 필드: {sorted(lost_keys)}")

    # ── [C-수정] 전략 A+B — 루프 누적 후 단일 emit ──────────────
    log("")
    log("─" * 60)
    log(f"[C-수정] 전략 A+B — EACH_DEV_LOOP_TIMEOUT={EACH_DEV_LOOP_TIMEOUT}s 루프 누적")
    log("  while readready: recvfrom() → accumulated += data")
    log("  searched_data.emit(accumulated)  # 1회만, 전체 데이터")
    log("  getsearch_each_dev(accumulated) → dev_profile[mc] 완전 구성")

    # 중복 제거 + 누적 (전략 A+B 동작 재현)
    seen = set()
    accumulated = b""
    pkt_count = 0
    for data, _ in packets:
        h = hashlib.md5(data).hexdigest()
        if h not in seen:
            seen.add(h)
            accumulated += data
            pkt_count += 1

    profile_new = _build_dev_profile(accumulated)
    mc_new = profile_new.get("MC", "")

    log(f"  누적 바이트: {len(accumulated)}B  (고유 패킷 {pkt_count}개)")
    if mc_new:
        cert_keys = [k for k in profile_new if k in ("CA", "CC", "CK")]
        mqtt_keys = [k for k in profile_new if k.startswith("Q")]
        log(f"  dev_profile['{mc_new}'] 키: {list(profile_new.keys())}")
        log(f"    기본 커맨드 : {[k for k in profile_new if k not in ('CA', 'CC', 'CK') and not k.startswith('Q')]}")
        log(f"    MQTT 커맨드 : {mqtt_keys}  {'✅' if mqtt_keys else '❌ 없음'}")
        log(f"    인증서 커맨드: {cert_keys}  {'✅' if cert_keys else '❌ 없음'}")
    else:
        log("  ❌ MC 필드 없음 (비정상 패킷)")

    # ── [C] 결론 ────────────────────────────────────────────────
    log("")
    log("─" * 60)
    log("[C] 결론")
    gained = sorted(set(profile_new.keys()) - set(profile_old.keys()))
    if gained:
        log(f"  ✅ 전략 A+B로 추가 복구되는 필드: {gained}")
        log("  → fill_devinfo()에서 MQTT/인증서 탭이 정상 표시됨")
    else:
        log("  → 단일 패킷 응답 — 전략 A+B 적용 전후 차이 없음")

    log("")
    log("  [적용 위치] WIZMSGHandler.py L214~227 (OP_SEARCHALL + presearch=False)")
    log(f"  [변경 내용] 단일 recvfrom() → while 루프 누적 (timeout={EACH_DEV_LOOP_TIMEOUT}s)")
    log("  [emit 방식] searched_data.emit(accumulated)  # 패킷별 아님, 누적 전체 1회")


# ── [D] Strategy C: per-addr 그룹핑 시뮬레이션 ───────────────────
#
# presearch=True 브로드캐스트 경로에서 여러 장치가 동시에 응답할 때,
# addr(IP:port) 기준으로 패킷을 장치별 분리 누적 → 독립 파싱.
#
# 전제 조건 (production 적용 시):
#   WIZUDPSock.recvfrom(): return data → return data, addr
#   WIZMSGHandler presearch=True 루프: per-addr accumulated dict 유지

def simulate_per_addr_grouping(packets: list[tuple]):
    """[D] Strategy C 시뮬레이션: addr별 그룹핑."""
    if not packets:
        return

    log("")
    log("=" * 60)
    log("[D] Strategy C: per-addr 그룹핑 시뮬레이션")
    log("    대상: presearch=True 브로드캐스트 경로 (여러 장치 동시 응답)")

    unique_addrs = list(dict.fromkeys(addr for _, addr in packets))
    log(f"  수신 패킷: {len(packets)}개  고유 출처(addr): {len(unique_addrs)}개")
    for addr in unique_addrs:
        cnt = sum(1 for _, a in packets if a == addr)
        sizes = [len(d) for d, a in packets if a == addr]
        log(f"    {addr}  →  {cnt}패킷  {sizes}B")

    # ── [D-현재] addr 무시 단순 누적 ────────────────────────────
    log("")
    log("─" * 60)
    log("[D-현재] addr 무시 단순 누적 — 장치 구별 없이 전체 합산")

    seen_naive = set()
    accumulated_naive = b""
    for data, _ in packets:
        h = hashlib.md5(data).hexdigest()
        if h not in seen_naive:
            seen_naive.add(h)
            accumulated_naive += data

    profile_naive = _build_dev_profile(accumulated_naive)
    mc_naive = profile_naive.get("MC", "")
    log(f"  누적 바이트: {len(accumulated_naive)}B  커맨드: {len(profile_naive)}개")
    log(f"  최종 MC: {mc_naive!r}")

    if len(unique_addrs) > 1:
        log(f"  ❌ {len(unique_addrs)}개 장치 데이터 혼합 → MC는 마지막 파싱값 1개만 남음")
        log("  ❌ 일부 장치 정보 유실 — addr 구별 없이는 정확한 분리 불가")
    else:
        log("  → 단일 출처 — 혼합 없음")

    # ── [D-전략C] per-addr 그룹핑 ────────────────────────────────
    log("")
    log("─" * 60)
    log("[D-전략C] per-addr 그룹핑 — 장치별 독립 누적·파싱")

    groups: dict[tuple, bytes] = {}
    seen_per: dict[tuple, set] = {}
    for data, addr in packets:
        h = hashlib.md5(data).hexdigest()
        if addr not in groups:
            groups[addr] = b""
            seen_per[addr] = set()
        if h not in seen_per[addr]:
            seen_per[addr].add(h)
            groups[addr] += data

    dev_profiles = {}
    for addr, accumulated in groups.items():
        profile = _build_dev_profile(accumulated)
        mc = profile.get("MC", "")
        pkt_cnt = sum(1 for _, a in packets if a == addr)
        log(f"  [{addr}]  {len(accumulated)}B  ({pkt_cnt}패킷 누적)")
        if mc:
            dev_profiles[mc] = profile
            cert_keys = [k for k in profile if k in ("CA", "CC", "CK")]
            mqtt_keys = [k for k in profile if k.startswith("Q")]
            base_keys = [k for k in profile
                         if k not in ("CA", "CC", "CK") and not k.startswith("Q")]
            log(f"    MC={mc}  커맨드 {len(profile)}개")
            log(f"    기본: {base_keys}")
            log(f"    MQTT: {mqtt_keys}  {'✅' if mqtt_keys else '(없음)'}")
            log(f"    인증서: {cert_keys}  {'✅' if cert_keys else '(없음)'}")
        else:
            log("    ❌ MC 없음")

    # ── [D] 결론 ─────────────────────────────────────────────────
    log("")
    log("─" * 60)
    log("[D] 결론")
    if len(unique_addrs) > 1:
        log(f"  ✅ per-addr 그룹핑으로 {len(unique_addrs)}개 장치 완전 분리")
        log("  ✅ 각 장치 dev_profile 독립 구성 — 데이터 뒤섞임 없음")
        log(f"  ✅ 등록된 장치: {list(dev_profiles.keys())}")
        naive_mc_count = len({profile_naive.get('MC', '')} - {''})
        log(f"  비교: [D-현재] 장치 {naive_mc_count}개만 인식 vs "
            f"[D-전략C] {len(dev_profiles)}개 완전 인식")
    else:
        log("  → 단일 출처 응답 — per-addr 그룹핑 필요 없음 (전략 A+B와 동일)")

    log("")
    log("  [production 적용 위치]")
    log("    1. WIZUDPSock.recvfrom(): return data  →  return data, addr")
    log("    2. WIZMSGHandler presearch=True 루프: per-addr accumulated dict 유지")
    log("    3. 루프 종료 후 각 addr의 accumulated 를 독립 파싱 → mac_list 등 구성")


# ── 검증 요약 ────────────────────────────────────────────────────

def print_summary(packets, accumulated, cmds):
    log("")
    log("─" * 60)
    log("[검증 요약]")
    total_recv = sum(len(d) for d, _ in packets)
    dup_count = sum(
        1 for i, (d, _) in enumerate(packets)
        if any(d == packets[j][0] for j in range(i))
    )
    log(f"  수신 패킷 수      : {len(packets)}")
    log(f"  중복 패킷 수      : {dup_count}")
    log(f"  총 수신 바이트    : {total_recv}B")
    log(f"  누적 바이트       : {len(accumulated)}B")
    log(f"  파싱된 커맨드 수  : {len(cmds)}")

    lines_all = accumulated.split(b"\r\n")
    if len(lines_all) > MAX_REPLY_CHUNKS:
        log(f"  ⚠️  DoS 패킷 감지: split {len(lines_all)}개 > MAX_REPLY_CHUNKS({MAX_REPLY_CHUNKS})")
    else:
        log(f"  ✅ split {len(lines_all)}개 ≤ MAX_REPLY_CHUNKS({MAX_REPLY_CHUNKS})")


# ── 메인 ─────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--timeout", type=float, default=0.5,
                   help="루프 select 타임아웃(초), 기본 0.5")
    p.add_argument("--initial", type=float, default=5.0,
                   help="첫 패킷 대기 타임아웃(초), 기본 5.0")
    p.add_argument("--log", metavar="FILE",
                   help="콘솔 + 파일 동시 로그 저장 경로")
    p.add_argument("--ready-file", metavar="FILE",
                   help="바인드 완료 후 생성할 신호 파일 (송신기 동기화용)")
    return p.parse_args()


def main():
    args = parse_args()
    setup_logging(args.log)

    # 이전 ready-file 정리
    if args.ready_file and os.path.exists(args.ready_file):
        os.remove(args.ready_file)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)
    sock.bind(("0.0.0.0", LISTEN_PORT))  # INADDR_ANY — 127.0.0.1·로컬 모두 수신
    sock.setblocking(False)

    log(f"[수신] 포트 {LISTEN_PORT}  루프타임아웃={args.timeout}s  첫패킷대기={args.initial}s")
    log("[수신] 송신기를 실행하세요: python test_udp_sender.py [시나리오]")
    log("=" * 60)

    packets = receive_all(sock, args.initial, args.timeout, args.ready_file)
    sock.close()

    log(f"\n[수신 완료] 총 {len(packets)}개 패킷")

    if not packets:
        log("수신된 패킷 없음.")
        return

    accumulated, cmds = analyze(packets)
    simulate_path1(packets)
    simulate_per_addr_grouping(packets)
    print_summary(packets, accumulated, cmds)

    # 로그 파일 경로 재출력 (확인 용이)
    if args.log:
        log(f"\n[로그 저장됨] {os.path.abspath(args.log)}")


if __name__ == "__main__":
    main()
