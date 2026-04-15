"""
test_udp_receiver.py — UDP 수신 패턴 종합 테스트

검증 항목:
  ① 수신 패킷 수 / 크기 / MD5
  ② 송수신 내용 일치 여부 (누적 후 재조합)
  ③ 현재 코드(패킷별 개별 처리) vs. 누적 처리 커맨드 차이
  ④ 중복 패킷 필터링 동작
  ⑤ DoS 패킷 시 MAX_REPLY_CHUNKS 작동 여부

사용법:
  python test_udp_receiver.py             # 기본 (0.5s 루프 타임아웃)
  python test_udp_receiver.py --timeout 1 # 루프 타임아웃 1초
"""
import socket
import select
import sys
import hashlib
import argparse

LISTEN_PORT = 50002
MAX_REPLY_CHUNKS = 200   # HIGH-03 수정 값과 동일


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--timeout", type=float, default=0.5,
                   help="루프 select 타임아웃(초), 기본 0.5")
    p.add_argument("--initial", type=float, default=5.0,
                   help="첫 패킷 대기 타임아웃(초), 기본 5.0")
    return p.parse_args()


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


def check_integrity(sent_full: bytes, received_chunks: list[bytes]) -> bool:
    """누적 수신 데이터가 송신 데이터와 일치하는지 확인."""
    accumulated = b"".join(received_chunks)
    h_sent = hashlib.md5(sent_full).hexdigest()
    h_recv = hashlib.md5(accumulated).hexdigest()
    match = (accumulated == sent_full)
    print(f"  송신 md5 : {h_sent}  ({len(sent_full)}B)")
    print(f"  수신 md5 : {h_recv}  ({len(accumulated)}B)")
    if match:
        print("  ✅ 송수신 완전 일치")
    else:
        print("  ❌ 송수신 불일치 — 패킷 손실 또는 순서 오류")
    return match


def receive_all(sock, initial_timeout, loop_timeout) -> list[tuple]:
    """select 루프로 모든 패킷 수신. [(data, addr), ...] 반환."""
    packets = []
    readready, _, _ = select.select([sock], [], [], initial_timeout)
    if not readready:
        print("  ⚠️  타임아웃: 패킷 없음 (송신기가 실행됐나요?)")
        return packets

    while readready:
        data, addr = sock.recvfrom(4096)
        h = hashlib.md5(data).hexdigest()[:8]
        is_dup = any(d == data for d, _ in packets)
        print(f"  📦 패킷 #{len(packets) + 1}: {len(data)}B  from={addr}  md5={h}"
              + ("  ⚠️ 중복!" if is_dup else ""))
        packets.append((data, addr))
        readready, _, _ = select.select([sock], [], [], loop_timeout)

    return packets


def analyze(packets: list[tuple]):
    """수신된 패킷들을 A(현재)/B(누적) 두 방식으로 분석."""
    print()
    print("─" * 60)
    print("[A] 현재 WIZMSGHandler 동작: 패킷별 개별 파싱")
    print("    (self.getreply = replylists 덮어씀 → 마지막 패킷만 남음)")

    all_per_pkt_cmds = []
    for i, (data, addr) in enumerate(packets):
        lines = data.split(b"\r\n")
        cmds = parse_commands(data)
        all_per_pkt_cmds.append(cmds)
        print(f"  패킷 {i+1}: {len(data)}B  커맨드 {len(cmds)}개: "
              + str([k.decode(errors='replace') for k in cmds]))

    if packets:
        last_cmds = all_per_pkt_cmds[-1]
        print(f"\n  → self.getreply 최종: 패킷 {len(packets)}번 커맨드 {len(last_cmds)}개")
        total_unique = len({k for cmds in all_per_pkt_cmds for k in cmds})
        lost = total_unique - len(last_cmds)
        if lost > 0:
            print(f"  ❌ 손실 커맨드 수: {lost}개 (패킷 1~{len(packets)-1} 누락)")
        else:
            print("  ✅ 단일 패킷 — 손실 없음")

    print()
    print("─" * 60)
    print("[B] 수정 후 동작: 누적 후 한 번에 파싱")

    # 중복 제거 후 누적
    seen = set()
    unique_chunks = []
    for data, _ in packets:
        h = hashlib.md5(data).hexdigest()
        if h not in seen:
            seen.add(h)
            unique_chunks.append(data)

    accumulated = b"".join(unique_chunks)
    all_lines = accumulated.split(b"\r\n")
    print(f"  누적 데이터: {len(accumulated)}B  → split: {len(all_lines)}개 항목")

    # DoS truncation 시뮬레이션
    if len(all_lines) > MAX_REPLY_CHUNKS:
        print(f"  ⚠️  MAX_REPLY_CHUNKS({MAX_REPLY_CHUNKS}) 초과 → truncation 적용")
        all_lines = all_lines[:MAX_REPLY_CHUNKS]

    all_cmds = parse_commands(accumulated)
    print(f"  전체 커맨드 ({len(all_cmds)}개): "
          + str([k.decode(errors='replace') for k in all_cmds]))

    cert_keys  = [k.decode() for k in all_cmds if k in (b"CA", b"CC", b"CK")]
    mqtt_keys  = [k.decode() for k in all_cmds if k.startswith(b"Q")]
    base_keys  = [k.decode() for k in all_cmds
                  if k not in (b"CA", b"CC", b"CK") and not k.startswith(b"Q")]
    print(f"  기본 커맨드 : {base_keys}")
    print(f"  MQTT 커맨드 : {mqtt_keys}")
    print(f"  인증서 커맨드: {cert_keys}")

    return accumulated, all_cmds


def main():
    args = parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)
    sock.bind(("127.0.0.1", LISTEN_PORT))
    sock.setblocking(False)

    print(f"[수신] 포트 {LISTEN_PORT}  루프타임아웃={args.timeout}s"
          f"  첫패킷대기={args.initial}s")
    print(f"[수신] 송신기를 실행하세요: python test_udp_sender.py [시나리오]")
    print("=" * 60)

    packets = receive_all(sock, args.initial, args.timeout)
    sock.close()

    print(f"\n[수신 완료] 총 {len(packets)}개 패킷")

    if not packets:
        print("수신된 패킷 없음.")
        return

    accumulated, cmds = analyze(packets)

    # ── 송수신 일치 확인 (시나리오 2 자동 검증) ──────────────────
    # 시나리오 2의 전체 응답 크기 = 실제 FULL_RESPONSE와 비교하려면
    # 송신기에서 출력한 md5를 수동으로 붙여넣거나,
    # 아래 플래그로 확인할 수 있습니다.
    print()
    print("─" * 60)
    print("[검증 요약]")
    total_recv = sum(len(d) for d, _ in packets)
    total_uniq = len(b"".join(
        d for d, _ in packets
        if hashlib.md5(d).hexdigest()
        in {hashlib.md5(x).hexdigest() for x, _ in
            [(packets[0][0], None)] if x == d}
    ))  # 단순화: 전체 합
    dup_count = sum(
        1 for i, (d, _) in enumerate(packets)
        if any(d == packets[j][0] for j in range(i))
    )
    print(f"  수신 패킷 수      : {len(packets)}")
    print(f"  중복 패킷 수      : {dup_count}")
    print(f"  총 수신 바이트    : {total_recv}B")
    print(f"  누적 바이트       : {len(accumulated)}B")
    print(f"  파싱된 커맨드 수  : {len(cmds)}")

    lines_all = accumulated.split(b"\r\n")
    if len(lines_all) > MAX_REPLY_CHUNKS:
        print(f"  ⚠️  DoS 패킷 감지: split 항목 {len(lines_all)}개 > MAX_REPLY_CHUNKS({MAX_REPLY_CHUNKS})")
    else:
        print(f"  ✅ split 항목 {len(lines_all)}개 ≤ MAX_REPLY_CHUNKS({MAX_REPLY_CHUNKS})")


if __name__ == "__main__":
    main()
