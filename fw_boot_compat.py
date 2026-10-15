"""
FW from Git 용 Boot↔App 호환 판정. GUI 의존 없는 순수 로직 모듈.

W7500 계열 Boot 는 메모리가 부족해 버전 정보를 갖고 있지 않다. "Boot V1.2/V1.3" 은
Boot 가 마지막으로 써진 시점의 App 버전으로 붙인 이름일 뿐이라 장치에서 읽을 수 없고,
실행 중인 App 버전으로 추측할 수밖에 없다. 그래서 판정은 세 단계다.
  ok     Boot 가 무엇이든 동작하는 이동
  block  Boot 가 무엇이든 동작하지 않는 이동
  warn   Boot 에 따라 갈리는 이동, 또는 판단할 근거가 없는 경우
규칙은 family 의 boot_compat 에 "현재세대>대상세대": 결과 로 둔다. 세대는 major.minor.
호환표는 앞으로 바뀐다(Boot 가 1.4 이상으로 올라가면 지금의 추측이 틀어진다). 표가
보증하는 최신 App 버전(known_max)을 넘는 쪽은 근거가 없으므로 항상 warn 이다.
단종된 세대(isp_recommend_from)에서 출발하면 App 만 올리지 말고 ISP tool 로 Boot 까지
다시 쓰라고 권한다 — App 만 올리면 Boot 가 옛것으로 남아 이후 판단이 불가능해지기 때문.
"""
import re

OK = "ok"
WARN = "warn"
BLOCK = "block"

_VERSION_RE = re.compile(r"^\s*[vV]?(\d+)\.(\d+)(?:\.(\d+))?")


def _parse(version):
    m = _VERSION_RE.match(version or "")
    return tuple(int(g or 0) for g in m.groups()) if m else None


def generation(version):
    """'1.4.5' / 'v1.3.3_DIK' / '1.2.4A' → '1.4' / '1.3' / '1.2'. 읽을 수 없으면 None."""
    v = _parse(version)
    return f"{v[0]}.{v[1]}" if v else None


def _beyond_known(rule, *versions):
    known_max = _parse(rule.get("known_max"))
    if known_max is None:
        return False
    return any(v is not None and v > known_max for v in map(_parse, versions))


def judge(rule, current_version, target_version):
    """
    rule 은 family["boot_compat"] (없으면 None → 제약 없음).
    반환: {"result": ok|warn|block, "from": 현재 세대, "to": 대상 세대,
           "docs_url": 호환표 링크, "isp_recommended": 단종 세대에서 출발하는가}
    transitions 에 없는 이동은 같은 세대면 ok(Boot 와의 관계가 안 바뀜), 아니면 warn.
    """
    if not rule:
        return {"result": OK, "from": None, "to": None, "docs_url": "",
                "isp_recommended": False}
    src = generation(current_version)
    dst = generation(target_version)
    if src is None or dst is None or _beyond_known(rule, current_version, target_version):
        result = WARN
    else:
        default = OK if src == dst else WARN
        result = rule.get("transitions", {}).get(f"{src}>{dst}", default)
    return {"result": result, "from": src, "to": dst,
            "docs_url": rule.get("docs_url", ""),
            "isp_recommended": src in rule.get("isp_recommend_from", [])}
