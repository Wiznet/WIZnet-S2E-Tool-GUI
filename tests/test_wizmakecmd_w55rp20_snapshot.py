# -*- coding: utf-8 -*-
"""W55RP20 계열 search()/setcommand() 출력 고정 — 7단계(R2 WIZMakeCMD 테이블화) 전 안전망.

devname x version(신FW/구FW) x BOOT 조합별 cmd_list 코드 순서를 실제 실행 결과 그대로
동결한다(2026-09-28, 리팩토링 전 캡처). R2 이후에도 이 값이 그대로면 "동작 무변경" 증명.
"""
import pytest

from WIZMakeCMD import WIZMakeCMD

MAC = "00:08:dc:11:22:33"
PW = "0000"

DEVNAMES = [
    "W55RP20-S2E",
    "W55RP20-S2E-2CH",
    "W55RP20-S2E-3CH",
    "W55RP20-S2E-4CH",
]

NEW_FW = "1.2.2"
OLD_FW = "1.1.0"

SEARCH_SNAPSHOT = {
    (NEW_FW, "W55RP20-S2E"): [
        'MA', 'PW', 'MC', 'VR', 'MN', 'IM', 'OP', 'CP', 'DG', 'KA', 'KI', 'KE', 'RI', 'LI',
        'SM', 'GW', 'DS', 'DH', 'LP', 'RP', 'RH', 'BR', 'DB', 'PR', 'SB', 'FL', 'IT', 'PT',
        'PS', 'PD', 'TE', 'SS', 'NP', 'SP', 'UN', 'ST', 'EC', 'SC', 'TR', 'QU', 'QP', 'QC',
        'QK', 'PU', 'U0', 'U1', 'U2', 'QO', 'RC', 'CE', 'SO', 'UF', 'SD', 'DD', 'SE', 'PO',
    ],
    (NEW_FW, "W55RP20-S2E-2CH"): [
        'MA', 'PW', 'MC', 'VR', 'MN', 'IM', 'OP', 'CP', 'DG', 'KA', 'KI', 'KE', 'RI', 'LI',
        'SM', 'GW', 'DS', 'DH', 'LP', 'RP', 'RH', 'BR', 'DB', 'PR', 'SB', 'FL', 'IT', 'PT',
        'PS', 'PD', 'TE', 'SS', 'NP', 'SP', 'UN', 'ST', 'EC', 'SC', 'TR', 'QU', 'QP', 'QC',
        'QK', 'PU', 'U0', 'U1', 'U2', 'QO', 'RC', 'CE', 'SO', 'UF', 'SD', 'DD', 'SE', 'QS',
        'EN', 'AO', 'QL', 'QH', 'AP', 'EB', 'ED', 'EP', 'ES', 'EF', 'ND', 'NS', 'AT', 'RV',
        'RA', 'RS', 'RE', 'RR', 'RO', 'EO', 'RD', 'RF', 'EE', 'PO',
    ],
    (NEW_FW, "W55RP20-S2E-3CH"): [
        'MA', 'PW', 'MC', 'VR', 'MN', 'IM', 'OP', 'CP', 'DG', 'KA', 'KI', 'KE', 'RI', 'LI',
        'SM', 'GW', 'DS', 'DH', 'LP', 'RP', 'RH', 'BR', 'DB', 'PR', 'SB', 'FL', 'IT', 'PT',
        'PS', 'PD', 'TE', 'SS', 'NP', 'SP', 'UN', 'ST', 'EC', 'SC', 'TR', 'QU', 'QP', 'QC',
        'QK', 'PU', 'U0', 'U1', 'U2', 'QO', 'RC', 'CE', 'SO', 'UF', 'SD', 'DD', 'SE', 'QS',
        'EN', 'AO', 'QL', 'QH', 'AP', 'EB', 'ED', 'EP', 'ES', 'EF', 'ND', 'NS', 'AT', 'RV',
        'RA', 'RS', 'RE', 'RR', 'RO', 'EO', 'RD', 'RF', 'EE', 'UI', 'EI', 'GS', 'WN', 'WI',
        'TO', 'GL', 'GH', 'TP', 'WB', 'WD', 'WP', 'WS', 'WF', 'HD', 'HS', 'TT', 'XV', 'XA',
        'XS', 'XE', 'XR', 'XO', 'WO', 'XD', 'XF', 'WE', 'PO',
    ],
    (NEW_FW, "W55RP20-S2E-4CH"): [
        'MA', 'PW', 'MC', 'VR', 'MN', 'IM', 'OP', 'CP', 'DG', 'KA', 'KI', 'KE', 'RI', 'LI',
        'SM', 'GW', 'DS', 'DH', 'LP', 'RP', 'RH', 'BR', 'DB', 'PR', 'SB', 'FL', 'IT', 'PT',
        'PS', 'PD', 'TE', 'SS', 'NP', 'SP', 'UN', 'ST', 'EC', 'SC', 'TR', 'QU', 'QP', 'QC',
        'QK', 'PU', 'U0', 'U1', 'U2', 'QO', 'RC', 'CE', 'SO', 'UF', 'SD', 'DD', 'SE', 'QS',
        'EN', 'AO', 'QL', 'QH', 'AP', 'EB', 'ED', 'EP', 'ES', 'EF', 'ND', 'NS', 'AT', 'RV',
        'RA', 'RS', 'RE', 'RR', 'RO', 'EO', 'RD', 'RF', 'EE', 'UI', 'EI', 'GS', 'WN', 'WI',
        'TO', 'GL', 'GH', 'TP', 'WB', 'WD', 'WP', 'WS', 'WF', 'HD', 'HS', 'TT', 'XV', 'XA',
        'XS', 'XE', 'XR', 'XO', 'WO', 'XD', 'XF', 'WE', 'CS', 'YN', 'YI', 'JO', 'CL', 'CH',
        'JP', 'YB', 'YD', 'YP', 'YS', 'YF', 'UD', 'US', 'JT', 'ZV', 'ZA', 'ZS', 'ZE', 'ZR',
        'ZO', 'YO', 'ZD', 'ZF', 'YE', 'PO',
    ],
}
# 구FW(<1.1.8): 4개 devname 전부 base 목록(채널 확장 커맨드 없이 강등)으로 동일
_OLD_FW_BASE = [
    'MA', 'PW', 'MC', 'VR', 'MN', 'IM', 'OP', 'CP', 'DG', 'KA', 'KI', 'KE', 'RI', 'LI',
    'SM', 'GW', 'DS', 'DH', 'LP', 'RP', 'RH', 'BR', 'DB', 'PR', 'SB', 'FL', 'IT', 'PT',
    'PS', 'PD', 'TE', 'SS', 'NP', 'SP', 'UN', 'ST', 'EC', 'SC', 'TR', 'QU', 'QP', 'QC',
    'QK', 'PU', 'U0', 'U1', 'U2', 'QO', 'RC', 'CE', 'SO', 'UF', 'PO',
]
for _dn in DEVNAMES:
    SEARCH_SNAPSHOT[(OLD_FW, _dn)] = _OLD_FW_BASE

_BOOT_SEARCH = ['MA', 'PW', 'MC', 'VR', 'MN', 'ST', 'IM', 'OP', 'LI', 'SM', 'GW', 'SP', 'DS']


@pytest.fixture
def maker():
    return WIZMakeCMD()


def _codes(cmd_list):
    return [c for c, _ in cmd_list]


@pytest.mark.parametrize("devname", DEVNAMES)
@pytest.mark.parametrize("version", [NEW_FW, OLD_FW])
def test_search_w55rp20_codes(maker, devname, version):
    codes = _codes(maker.search(MAC, PW, devname, version))
    assert codes == SEARCH_SNAPSHOT[(version, devname)]


@pytest.mark.parametrize("devname", DEVNAMES)
def test_search_boot_status(maker, devname):
    codes = _codes(maker.search(MAC, PW, devname, NEW_FW, devstatus="BOOT"))
    assert codes == _BOOT_SEARCH


@pytest.mark.parametrize("devname", DEVNAMES)
@pytest.mark.parametrize("version", [NEW_FW, OLD_FW])
def test_setcommand_get_tail_matches_search(maker, devname, version):
    """setcommand() 의 확인용 GET 목록(SV/RT 앞)은 search() 목록과 같은 코드 순서여야 한다."""
    search_codes = _codes(maker.search(MAC, PW, devname, version))
    set_codes = _codes(maker.setcommand(MAC, PW, PW, [], [], devname, version, status=None))
    assert set_codes[:2] == ["MA", "PW"]
    assert set_codes[-2:] == ["SV", "RT"]
    assert set_codes[2:-2] == search_codes[2:]


@pytest.mark.parametrize("devname", DEVNAMES)
def test_setcommand_boot_status(maker, devname):
    codes = _codes(maker.setcommand(MAC, PW, PW, [], [], devname, NEW_FW, status="BOOT"))
    assert codes[:2] == ["MA", "PW"]
    assert codes[-2:] == ["SV", "RT"]
    assert codes[2:-2] == _BOOT_SEARCH[2:]
