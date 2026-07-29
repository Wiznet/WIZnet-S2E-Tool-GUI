#!/usr/bin/env python
"""find_build_env.py

Locate the MSVC + Windows SDK build toolchain via the Everything SDK and emit
INCLUDE / LIB / PATH (and the signtool path) as a single line of JSON on stdout.

Purpose: remove hard-coded toolchain paths from setup_bootloader.ps1 / build.ps1.
Whatever machine this runs on, as long as Everything has the files indexed, the
correct cl.exe / headers / libs / signtool are discovered automatically.

Prereq: the Everything app must be running (results come from its live index).
Output: one JSON object. On success {"ok": true, ...}; on failure {"ok": false,
        "reason": ...} with exit code 1.
"""
import ctypes
import glob
import json
import os
import re
import sys

EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME = 0x00000004


def load_everything():
    """Find and load the FlowLauncher-bundled Everything SDK (x64) DLL."""
    pats = [
        os.path.expandvars(
            r"%LOCALAPPDATA%\FlowLauncher\app-*\EverythingSDK\x64\Everything.dll"
        ),
        os.path.expandvars(r"%LOCALAPPDATA%\Everything*\Everything64.dll"),
    ]
    cands = []
    for p in pats:
        cands += glob.glob(p)
    if not cands:
        return None, "Everything SDK x64 DLL not found"
    dll_path = sorted(cands)[-1]  # newest app-* version
    try:
        dll = ctypes.WinDLL(dll_path)
    except OSError as e:
        return None, f"failed to load {dll_path}: {e}"
    dll.Everything_SetSearchW.argtypes = [ctypes.c_wchar_p]
    dll.Everything_SetRequestFlags.argtypes = [ctypes.c_uint]
    dll.Everything_SetMatchPath.argtypes = [ctypes.c_bool]
    dll.Everything_QueryW.argtypes = [ctypes.c_bool]
    dll.Everything_QueryW.restype = ctypes.c_bool
    dll.Everything_GetNumResults.restype = ctypes.c_uint
    dll.Everything_GetResultFullPathNameW.argtypes = [
        ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint
    ]
    return dll, dll_path


def search(dll, query):
    dll.Everything_SetSearchW(query)
    dll.Everything_SetMatchPath(True)
    dll.Everything_SetRequestFlags(EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME)
    if not dll.Everything_QueryW(True):
        return []
    n = dll.Everything_GetNumResults()
    out = []
    buf = ctypes.create_unicode_buffer(32767)
    for i in range(n):
        dll.Everything_GetResultFullPathNameW(i, buf, 32767)
        out.append(buf.value)
    return out


def ver_key(s):
    return tuple(int(x) for x in re.findall(r"\d+", s))


def pick_latest(paths, pattern):
    """Among paths matching `pattern` (group 1 = version), return newest."""
    rx = re.compile(pattern, re.IGNORECASE)
    matched = [(ver_key(m.group(1)), p) for p in paths for m in [rx.search(p)] if m]
    if not matched:
        return None
    matched.sort()
    return matched[-1][1]


def fail(reason, **extra):
    print(json.dumps({"ok": False, "reason": reason, **extra}))
    return 1


def main():
    dll, info = load_everything()
    if dll is None:
        return fail(info)

    # 1) cl.exe : ...\VC\Tools\MSVC\<ver>\bin\Hostx64\x64\cl.exe
    cls = search(dll, "cl.exe")
    cl = pick_latest(cls, r"VC\\Tools\\MSVC\\([0-9.]+)\\bin\\Hostx64\\x64\\cl\.exe$")
    if not cl:
        return fail("cl.exe (MSVC Hostx64/x64) not found", candidates=cls[:10])
    vc_bin = os.path.dirname(cl)
    vc_root = cl[: cl.lower().index(r"\bin\hostx64")]   # ...\VC\Tools\MSVC\<ver>
    vc_inc = os.path.join(vc_root, "include")
    vc_lib = os.path.join(vc_root, "lib", "x64")

    # 2) SDK Include root : winapifamily.h -> ...\Include\<ver>\shared\winapifamily.h
    fams = search(dll, "winapifamily.h")
    fam = pick_latest(
        fams, r"Windows Kits\\10\\Include\\([0-9.]+)\\shared\\winapifamily\.h$"
    )
    if not fam:
        return fail("winapifamily.h (SDK Include\\shared) not found", candidates=fams[:10])
    sdk_inc_root = os.path.dirname(os.path.dirname(fam))   # ...\Include\<ver>

    # 3) SDK Lib root : kernel32.lib -> ...\Lib\<ver>\um\x64\kernel32.lib
    k32s = search(dll, "kernel32.lib")
    k32 = pick_latest(k32s, r"Windows Kits\\10\\Lib\\([0-9.]+)\\um\\x64\\kernel32\.lib$")
    if not k32:
        return fail("kernel32.lib (SDK Lib\\um\\x64) not found", candidates=k32s[:10])
    sdk_lib_root = os.path.dirname(os.path.dirname(os.path.dirname(k32)))  # ...\Lib\<ver>

    # 4) SDK bin tools : signtool/mt/rc -> ...\bin\<ver>\x64\<tool>
    def sdk_tool(name):
        hits = search(dll, name)
        # Match both standard ("Windows Kits\10\bin\<ver>\x64") and NuGet
        # BuildTools ("Windows Kits\bin\<ver>\x64") layouts.
        return pick_latest(
            hits, r"[\\/]bin[\\/]([0-9][0-9.]+)[\\/]x64[\\/]" + re.escape(name) + r"$"
        )

    signtool = sdk_tool("signtool.exe")
    sdk_bin = os.path.dirname(signtool) if signtool else None

    include = ";".join([
        vc_inc,
        os.path.join(sdk_inc_root, "ucrt"),
        os.path.join(sdk_inc_root, "um"),
        os.path.join(sdk_inc_root, "shared"),
        os.path.join(sdk_inc_root, "winrt"),
    ])
    lib = ";".join([
        vc_lib,
        os.path.join(sdk_lib_root, "ucrt", "x64"),
        os.path.join(sdk_lib_root, "um", "x64"),
    ])
    path_add = ";".join([p for p in (vc_bin, sdk_bin) if p])

    print(json.dumps({
        "ok": True,
        "CL": cl,
        "SIGNTOOL": signtool or "",
        "PATH_ADD": path_add,
        "INCLUDE": include,
        "LIB": lib,
        "diag": {
            "everything_dll": info,
            "vc_root": vc_root,
            "sdk_inc_root": sdk_inc_root,
            "sdk_lib_root": sdk_lib_root,
            "sdk_bin": sdk_bin,
        },
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
