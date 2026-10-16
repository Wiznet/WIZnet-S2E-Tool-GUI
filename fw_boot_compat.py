"""
FW from Git 용 Boot↔App 호환 판정. GUI 의존 없는 순수 로직 모듈.

W7500 계열 Boot 는 메모리가 부족해 버전 정보를 갖고 있지 않다. "Boot V1.2/V1.3" 은
Boot 가 마지막으로 써진 시점의 App 버전으로 붙인 이름일 뿐이라 장치에서 읽을 수 없고,
실행 중인 App 버전으로 추측할 수밖에 없다. 그래서 판정은 세 단계다.
  ok     Boot 가 무엇이든 동작하는 이동
  block  Boot 가 무엇이든 동작하지 않는 이동
  warn   Boot 에 따라 갈리는 이동, 또는 판단할 근거가 없는 경우

규칙은 family 의 boot_compat 에 둔다.
  epochs       구간 이름 → 시작 버전(오름차순). Boot/App 이 같은 규약으로 묶이는 구간으로,
               경계는 인터럽트 재매핑(ISR) 주소가 바뀌는 버전이다(1.3.0, 1.3.3).
  transitions  "현재구간>대상구간": ok/warn/block. 없으면 같은 구간은 ok, 그 외는 warn.
  known_max    호환표가 보증하는 최신 App 버전. 현재/대상이 이걸 넘으면 항상 warn
               (Boot 가 더 올라가면 표가 낡으므로 새 Boot/App 이 나올 때까지 근거가 없다).
  isp_recommend_from  단종된 구간. 여기서 출발하면 App 만 올리지 말고 ISP tool 로 Boot 까지
               다시 쓰라고 권한다 — App 만 올리면 Boot 가 옛것으로 남아 이후 판단이 불가능해진다.

장치가 BOOT 상태(복구 중)일 때는 화면의 현재 버전이 저장된 값이지 실제로 돌던 App 이
아니므로 block 을 warn 으로 낮춘다. 막으면 복구용 업로드까지 막게 된다.
"""
from fw_version import parse_triple

OK = "ok"
WARN = "warn"
BLOCK = "block"


def _parse(version):
    """(major, minor, patch) 또는 None. 숫자부 추출은 `fw_version` 이 한다."""
    return parse_triple(version)


def generation(version, rule=None):
    """
    '1.4.5' / 'v1.3.3_DIK' / '1.2.4A' → 구간 이름. 읽을 수 없거나 첫 구간보다 낮으면 None.
    rule 에 epochs 가 없으면 major.minor('1.4')를 구간으로 본다.
    """
    v = _parse(version)
    if v is None:
        return None
    epochs = (rule or {}).get("epochs")
    if not epochs:
        return f"{v[0]}.{v[1]}"
    name = None
    for epoch_name, start in epochs.items():
        lower = _parse(start)
        if lower is not None and v >= lower:
            name = epoch_name
    return name


def _beyond_known(rule, *versions):
    known_max = _parse(rule.get("known_max"))
    if known_max is None:
        return False
    return any(v is not None and v > known_max for v in map(_parse, versions))


def judge(rule, current_version, target_version, in_boot_mode=False):
    """
    rule 은 family["boot_compat"] (없으면 None → 제약 없음).
    반환: {"result": ok|warn|block, "from": 현재 구간, "to": 대상 구간,
           "current": 현재 버전, "target": 대상 버전, "docs_url": 호환표 링크,
           "isp_recommended": 단종 구간에서 출발하는가,
           "boot_mode_relaxed": BOOT 상태라 block 을 warn 으로 낮췄는가}
    """
    current = (current_version or "").strip()
    target = (target_version or "").strip()
    if not rule:
        return {"result": OK, "from": None, "to": None, "current": current,
                "target": target, "docs_url": "", "isp_recommended": False,
                "boot_mode_relaxed": False}
    src = generation(current, rule)
    dst = generation(target, rule)
    if src is None or dst is None or _beyond_known(rule, current, target):
        result = WARN
    else:
        default = OK if src == dst else WARN
        result = rule.get("transitions", {}).get(f"{src}>{dst}", default)
    relaxed = in_boot_mode and result == BLOCK
    if relaxed:
        result = WARN
    return {"result": result, "from": src, "to": dst, "current": current,
            "target": target, "docs_url": rule.get("docs_url", ""),
            "isp_recommended": src in rule.get("isp_recommend_from", []),
            "boot_mode_relaxed": relaxed}
