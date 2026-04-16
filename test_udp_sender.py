"""
test_udp_sender.py — UDP 멀티패킷 송신 시뮬레이터

시나리오:
  1. 정상 단일 패킷 응답 (소형 장치)
  2. 멀티 패킷 응답 (인증서/MQTT 포함 대형 장치)
  3. 동일 데이터 반복 전송 (중복 패킷 테스트)
  4. 비정상 패킷 (구분자 폭탄 — HIGH-03 DoS 테스트)

사용법:
  python test_udp_sender.py [시나리오번호]   # 기본: 2 (멀티패킷)
  python test_udp_sender.py 1   # 단일 패킷
  python test_udp_sender.py 2   # 멀티 패킷 (인증서+MQTT)
  python test_udp_sender.py 3   # 중복 패킷
  python test_udp_sender.py 4   # DoS 패킷
  python test_udp_sender.py all # 전체 순서대로
"""
import socket
import time
import sys
import hashlib

DEST = ("127.0.0.1", 50002)
PACKET_LIMIT = 1460
INTER_PACKET_DELAY = 0.02  # 20ms

# ── 패킷 데이터 정의 ────────────────────────────────────────────

BASE_CMDS = (
    b"MA\x00\x08\xdc\x11\x22\x33\r\n"
    b"MC00:08:DC:11:22:33\r\n"
    b"MN WIZ510SSL\r\n"
    b"VR 1.2.0\r\n"
    b"ST 0\r\n"
    b"OP 0\r\n"
    b"IM 0\r\n"
    b"LI 192.168.1.150\r\n"
    b"SM 255.255.255.0\r\n"
    b"GW 192.168.1.1\r\n"
    b"LP 8883\r\n"
    b"BR 9\r\n"
    b"DB 0\r\n"
    b"PR 0\r\n"
    b"SB 0\r\n"
    b"FL 0\r\n"
)

MQTT_CMDS = (
    b"QH mqtt.example.com\r\n"
    b"QP 8883\r\n"
    b"QI wiznet-device-001\r\n"
    b"QU mqttuser\r\n"
    b"QW mqtt_s3cr3t_p@ssw0rd\r\n"
    b"QT wiznet/device/001/data\r\n"
    b"QS wiznet/device/001/cmd\r\n"
    b"QK 60\r\n"
    b"QQ 1\r\n"
    b"QL 1\r\n"
)

# ~1200B PEM 더미 인증서 (실제 크기 수준)
_CERT_BODY = b"A" * 900
FAKE_CA_CERT = (
    b"-----BEGIN CERTIFICATE-----\r\n"
    + _CERT_BODY + b"\r\n"
    + b"-----END CERTIFICATE-----"
)
FAKE_CLIENT_CERT = (
    b"-----BEGIN CERTIFICATE-----\r\n"
    + b"B" * 800 + b"\r\n"
    + b"-----END CERTIFICATE-----"
)
FAKE_CLIENT_KEY = (
    b"-----BEGIN RSA PRIVATE KEY-----\r\n"
    + b"C" * 700 + b"\r\n"
    + b"-----END RSA PRIVATE KEY-----"
)

CERT_CMDS = (
    b"CA" + FAKE_CA_CERT + b"\r\n"
    + b"CC" + FAKE_CLIENT_CERT + b"\r\n"
    + b"CK" + FAKE_CLIENT_KEY + b"\r\n"
)

FULL_RESPONSE = BASE_CMDS + MQTT_CMDS + CERT_CMDS

# 시나리오 5용: Device B (WIZ750SR, 소형, 단일 패킷, 다른 MAC)
BASE_CMDS_B = (
    b"MA\x00\x08\xdc\xaa\xbb\xcc\r\n"
    b"MC00:08:DC:AA:BB:CC\r\n"
    b"MN WIZ750SR\r\n"
    b"VR 1.5.0\r\n"
    b"ST 0\r\n"
    b"OP 0\r\n"
    b"IM 0\r\n"
    b"LI 192.168.1.200\r\n"
    b"SM 255.255.255.0\r\n"
    b"GW 192.168.1.1\r\n"
    b"LP 5000\r\n"
    b"BR 9\r\n"
    b"DB 0\r\n"
    b"PR 0\r\n"
    b"SB 0\r\n"
    b"FL 0\r\n"
)


def send_chunks(sock, data, label=""):
    """데이터를 PACKET_LIMIT 크기로 분할 전송. 각 청크의 SHA256 출력."""
    chunks = [data[i:i+PACKET_LIMIT] for i in range(0, len(data), PACKET_LIMIT)]
    total = len(data)
    print(f"  [{label}] 전체 크기: {total}B → {len(chunks)}개 패킷 (LIMIT={PACKET_LIMIT}B)")
    for idx, chunk in enumerate(chunks):
        h = hashlib.md5(chunk).hexdigest()[:8]
        print(f"  [패킷 {idx+1}/{len(chunks)}] {len(chunk)}B  md5={h}")
        sock.sendto(chunk, DEST)
        if idx < len(chunks) - 1:
            time.sleep(INTER_PACKET_DELAY)
    return chunks


def scenario_1(sock):
    """시나리오 1: 정상 단일 패킷 (소형 장치, < 1460B)"""
    print("\n━━ 시나리오 1: 단일 패킷 정상 응답 ━━")
    small = BASE_CMDS
    print(f"  크기: {len(small)}B (< {PACKET_LIMIT}B → 1패킷)")
    sock.sendto(small, DEST)
    print("  전송 완료")
    return small


def scenario_2(sock):
    """시나리오 2: 멀티 패킷 (인증서+MQTT, > 1460B)"""
    print("\n━━ 시나리오 2: 멀티 패킷 응답 (인증서+MQTT) ━━")
    send_chunks(sock, FULL_RESPONSE, "FULL")
    h_full = hashlib.md5(FULL_RESPONSE).hexdigest()
    print(f"  전체 데이터 md5={h_full} (수신 측에서 일치 확인용)")
    return FULL_RESPONSE


def scenario_3(sock):
    """시나리오 3: 중복 패킷 (같은 패킷 3회 반복)"""
    print("\n━━ 시나리오 3: 중복 패킷 (동일 데이터 3회) ━━")
    for i in range(3):
        print(f"  전송 #{i+1}: {len(BASE_CMDS)}B")
        sock.sendto(BASE_CMDS, DEST)
        time.sleep(0.05)
    return BASE_CMDS


def scenario_4(sock):
    """시나리오 4: DoS 패킷 — 더미 커맨드 폭탄 (HIGH-03)
    300개 커맨드 라인을 한 패킷에 담아 전송.
    MAX_REPLY_CHUNKS=200 이면 truncation 로그 출력되어야 함.
    """
    print("\n━━ 시나리오 4: DoS 패킷 — 더미 커맨드 폭탄 ━━")
    # 'XX00000\r\n' (9B) × 300 = 2700B, split 결과 301개 항목 → MAX_REPLY_CHUNKS(200) 초과
    line = b"ZZ00000\r\n"
    dos_payload = line * 300
    chunks = dos_payload.split(b"\r\n")
    print(f"  크기: {len(dos_payload)}B  커맨드 라인: 300개  split 항목: {len(chunks)}개")
    print(f"  → MAX_REPLY_CHUNKS=200 이면 truncation 경고 기대")
    sent = sock.sendto(dos_payload, DEST)
    print(f"  전송: {sent}B")
    return dos_payload


def scenario_5(_sock):
    """시나리오 5: 멀티 장치 브로드캐스트 — 인터리빙 응답
    Device A (WIZ510SSL, 대형): FULL_RESPONSE → 2패킷
    Device B (WIZ750SR, 소형): BASE_CMDS_B  → 1패킷
    전송 순서: A1 → B1 → A2  (실제 네트워크 인터리빙 시뮬레이션)
    두 소켓 = 두 개의 출처 포트 → 수신 측에서 addr로 장치 구별 가능
    """
    print("\n━━ 시나리오 5: 멀티 장치 브로드캐스트 응답 (인터리빙) ━━")
    sock_a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        chunks_a = [FULL_RESPONSE[i:i+PACKET_LIMIT]
                    for i in range(0, len(FULL_RESPONSE), PACKET_LIMIT)]
        print(f"  Device A (WIZ510SSL) FULL_RESPONSE={len(FULL_RESPONSE)}B → {len(chunks_a)}패킷")
        print(f"  Device B (WIZ750SR)  BASE_CMDS_B={len(BASE_CMDS_B)}B → 1패킷")
        print(f"  전송 순서: A1 → B1 → A2  (인터리빙)")

        h = hashlib.md5(chunks_a[0]).hexdigest()[:8]
        print(f"  [A 패킷 1/{len(chunks_a)}] {len(chunks_a[0])}B  md5={h}")
        sock_a.sendto(chunks_a[0], DEST)
        time.sleep(INTER_PACKET_DELAY)

        h = hashlib.md5(BASE_CMDS_B).hexdigest()[:8]
        print(f"  [B 패킷 1/1] {len(BASE_CMDS_B)}B  md5={h}")
        sock_b.sendto(BASE_CMDS_B, DEST)
        time.sleep(INTER_PACKET_DELAY)

        h = hashlib.md5(chunks_a[1]).hexdigest()[:8]
        print(f"  [A 패킷 2/{len(chunks_a)}] {len(chunks_a[1])}B  md5={h}")
        sock_a.sendto(chunks_a[1], DEST)

        print("  전송 완료")
    finally:
        time.sleep(0.1)
        sock_a.close()
        sock_b.close()


# ── 메인 ────────────────────────────────────────────────────────

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "2"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[송신] 목적지: {DEST}  모드: {mode}")

    try:
        if mode == "1":
            scenario_1(sock)
        elif mode == "2":
            scenario_2(sock)
        elif mode == "3":
            scenario_3(sock)
        elif mode == "4":
            scenario_4(sock)
        elif mode == "5":
            scenario_5(sock)
        elif mode == "all":
            for fn in [scenario_1, scenario_2, scenario_3, scenario_4, scenario_5]:
                fn(sock)
                print("  (다음 시나리오까지 1.5초 대기)")
                time.sleep(1.5)
        else:
            print(f"알 수 없는 시나리오: {mode}")
    finally:
        time.sleep(0.1)  # Windows UDP 플러시 대기 (단일 패킷 즉시 close 시 유실 방지)
        sock.close()

    print("\n[송신] 완료")


if __name__ == "__main__":
    main()
