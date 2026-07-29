---
phase: 06-gui-integration
reviewed: 2026-05-18T21:42:00Z
depth: quick
files_reviewed: 3
files_reviewed_list:
  - main_gui.py
  - tests/conftest.py
  - tests/test_wiz550_gui.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-05-18T21:42:00Z
**Depth:** quick (pattern scan + targeted reads of Phase 6 additions)
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 6 adds WIZ550 search integration (`_merge_wiz550_results`), a dynamic panel builder (`_build_wiz550_panel` / `_make_wiz550_field_widget`), GET_INFO fill (`fill_devinfo_wiz550`, `_on_wiz550_get_done`), Apply (`fill_setinfo_wiz550`, `apply_wiz550`, `_on_wiz550_set_done`), and Reset flows (`reset_wiz550`, `_on_wiz550_reset_done`), plus routing in `event_setting_clicked`, `event_reset_clicked`, and `event_factory_option_clicked`.

Two critical bugs were found: QThread local-variable lifetime (all three thread objects are stack-local and may be garbage-collected mid-run) and a stale `_wiz550_field_widgets` dict surviving panel teardown. Three warnings cover the WIZ550S2E panel not rebuilding when fw_version changes between MQTT/Modbus, the conftest `import sys` placement, and a `fill_setinfo_wiz550` type-detection comment mismatch. Two info items note minor code style issues.

The `_binary_proto` filter placement (line 2504) is correct — it runs after the list is passed into `search_each_dev`, not inside the existing WIZ5xx loop, and does not regress standard devices.

---

## Critical Issues

### CR-01: QThread Objects Are Stack-Local — May Be GC'd Before run() Completes

**File:** `main_gui.py:3307`, `main_gui.py:3680`, `main_gui.py:3743`

**Issue:** `getter`, `setter`, and `resetter` are assigned to local variables only. Python's garbage collector may destroy these QThread objects immediately after `start()` returns, before `run()` finishes. In CPython this is often masked by reference counting, but when Qt's event loop re-enters (e.g., user clicks something), the reference count can drop to zero. This is the standard Qt-Python QThread lifetime bug — the signal connection does not prevent GC.

```python
# CURRENT (line 3307) — local variable, no self reference
getter = WIZ550Getter(...)
getter.get_done.connect(lambda ...)
getter.start()
# getter goes out of scope here; CPython may GC it
```

**Fix:** Store each thread on `self` before calling `start()`. Add a `finished` connection to clear the reference for cleanup:

```python
# In apply_wiz550() / reset_wiz550() / get_clicked_devinfo()
self._wiz550_getter = WIZ550Getter(...)
self._wiz550_getter.get_done.connect(
    lambda cfg, mac=macaddr, dtype=device_type:
        self._on_wiz550_get_done(cfg, mac, dtype)
)
self._wiz550_getter.finished.connect(
    lambda: setattr(self, '_wiz550_getter', None)
)
self._wiz550_getter.start()

# Same pattern for setter → self._wiz550_setter
# Same pattern for resetter → self._wiz550_resetter
```

---

### CR-02: Old `_wiz550_field_widgets` Survives Panel Teardown — Stale Widget References

**File:** `main_gui.py:3288-3289`

**Issue:** When the device type changes and the old container is detached via `setParent(None)` (line 3289), `_wiz550_field_widgets` is NOT cleared before `_build_wiz550_panel` reassigns it at line 3477. Between lines 3289 and 3286 (new panel build), `_wiz550_field_widgets` still holds references to widgets owned by the detached (orphaned) container. If `_on_wiz550_get_done` fires from a previous in-flight `WIZ550Getter` during this window — possible because CR-01 means the getter is not tracked — `fill_devinfo_wiz550` will write into dead widgets, causing a silent data loss or (on Windows) a crash when Qt finalizes the orphaned container.

```python
# CURRENT (line 3288-3289): container detached but dict not cleared
if self._wiz550_container is not None:
    self._wiz550_container.setParent(None)
# _wiz550_field_widgets still references old container's widgets here
```

**Fix:** Clear `_wiz550_field_widgets` immediately after `setParent(None)`:

```python
if self._wiz550_container is not None:
    self._wiz550_container.setParent(None)
    self._wiz550_field_widgets = {}   # <-- add this line
```

---

## Warnings

### WR-01: WIZ550S2E Panel Not Rebuilt When fw_version Changes (MQTT/Modbus Mode Switch)

**File:** `main_gui.py:3284-3285`

**Issue:** The panel rebuild condition at line 3284 only checks `_wiz550_last_type != device_type`. For `WIZ550S2E`, the same device type can render different sections (MQTT vs Modbus) depending on `fw_version[1]`. If a user selects a WIZ550S2E device, the panel is built with `has_mqtt=False` (fw_version not yet loaded), then GET_INFO completes and `dev_profile` is updated with the real `fw_version`. On the *next* click, the cache hit (`_wiz550_last_type == 'WIZ550S2E'`) skips the rebuild — so the MQTT/Modbus section is never shown even though fw_version is now known.

**Fix:** Include a fw_version-derived key in the cache check:

```python
fw_ver = self.dev_profile.get(macaddr, {}).get('fw_version', b'\x00\x00\x00')
fw_variant = fw_ver[1] if len(fw_ver) >= 2 else 0  # 0=base, odd=mqtt, even(!=0)=modbus
cache_key = (device_type, fw_variant)
if (self._wiz550_container is None
        or getattr(self, '_wiz550_last_key', None) != cache_key):
    ...
    self._wiz550_last_key = cache_key
```

---

### WR-02: `import sys` Is Mid-File in conftest.py — PEP 8 Violation That May Confuse Linters

**File:** `tests/conftest.py:286`

**Issue:** `import sys` appears at line 286, after all other module-level code and fixtures. While Python allows this and it functions correctly, pytest linters and `isort` will flag it as an error-level style violation. More importantly, if the module fails to import for any reason, the error message will point to line 286 instead of the top of file, making diagnosis harder.

**Fix:** Move `import sys` to the top of the file with the other stdlib imports (after `import struct`, before `import pytest`):

```python
import struct
import sys
import pytest
```

---

### WR-03: `fill_setinfo_wiz550` Type Detection Relies on `int()` Exception — No Widget-Type Metadata

**File:** `main_gui.py:3621-3628`

**Issue:** The docstring says "uint16 필드는 int 변환, ip/text 필드는 str 유지" but the implementation tries `int()` on ALL QLineEdit fields and falls back to str only on ValueError. This works correctly for the current field set (IP strings fail int conversion naturally) but will silently convert any text field whose content happens to be numeric (e.g., a hostname like `192168001` would become integer `192168001`). There is no widget-level metadata linking back to the YAML `type` key.

**Fix:** Store the field type alongside the widget in `_wiz550_field_widgets` (e.g., as a tuple):

```python
# In _build_wiz550_panel:
self._wiz550_field_widgets[field['id']] = (widget, field.get('type', 'text'))

# In fill_setinfo_wiz550:
for field_id, (widget, ftype) in self._wiz550_field_widgets.items():
    ...
    elif isinstance(widget, QLineEdit):
        text = widget.text().strip()
        if ftype == 'uint16':
            try:
                result[field_id] = int(text)
            except ValueError:
                result[field_id] = 0  # or log warning
        else:
            result[field_id] = text
```

---

## Info

### IN-01: `_wiz550_last_type` Not Initialized in `__init__`

**File:** `main_gui.py:892`, `main_gui.py:3285`

**Issue:** `_wiz550_last_type` is never set in `__init__` (line 892 block). It is accessed via `getattr(self, '_wiz550_last_type', None)` which is safe, but is inconsistent with the initialization of `_wiz550_container`, `_wiz550_search_pending`, and `_wiz550_field_widgets` which are all set in `__init__`. Future developers may not realize the implicit `None` default.

**Fix:** Add to `__init__` alongside the other WIZ550 initialization:

```python
self._wiz550_last_type = None
```

---

### IN-02: `test_wiz550_resetter_opcodes` Inspects `__init__` Signature — Fragile to Refactoring

**File:** `tests/test_wiz550_gui.py:98-102`

**Issue:** The test uses `inspect.signature(WIZ550Resetter.__init__)` to read the default value of `op_code`. This is a valid technique but brittle — if `WIZ550Resetter.__init__` adds `*args/**kwargs` delegation or moves `op_code` to a class-level constant, the inspection will silently return the wrong result. The test also does not call `WIZ550Resetter()` and verify actual behavior.

**Fix (optional):** The test is already marked as an immediate-PASS stub for constants. If robustness is needed, replace the inspect approach with a direct instantiation check:

```python
# Alternative: instantiate and check .op_code attribute
r = WIZ550Resetter.__new__(WIZ550Resetter)
r.__init__.__defaults__  # or check WIZ550Resetter.__init__.__kwdefaults__
```

This is low priority (Info) since the test does correctly verify the constant values at import time.

---

_Reviewed: 2026-05-18T21:42:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick (targeted reads on Phase 6 additions)_
