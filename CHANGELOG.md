# Changelog

All notable changes to WIZnet S2E Tool GUI from v1.5.5 onward.

---

## [1.6.2.8] – 2026-07-02

### Security
- Dependency updates: `requests`, `idna`, `certifi`, `charset-normalizer`.

---

## [1.6.2.7] – 2026-06-16

### Features
- File menu: **Apply Settings (F4)** entry added.
- WIZ550 unicast **"IP Address" search mode** added (equivalent to the Java tool's IP Address
  mode); blocking ping/TCP dialog removed, multi-NIC broadcast applied to `WIZ550Getter`
  (GET_INFO) and `WIZ550Searcher`.
- **Config validation system (P3–P5)**: range/enum validation + baseline restore on load, schema
  migration engine, violation-correction persistence with repeat prevention, GUI notification of
  restored baseline values, `set_command_delay_ms` exposed in the Advanced dialog.
- WIZ550: widget visibility gating driven by YAML `widget_overrides.visible` for unsupported
  features.

### Bug Fixes
- WIZ550 YAML firmware alignment corrections (`baud_rate`, `data_bits`/`stop_bits` encoding,
  `working_mode`/`flow_control` mislabeling) — groundwork for widget-override-based gating.
- WIZ550SR: baud 300 removed (SR only supports 600+) + 3 FW v1.2.2 dead-field comments added.
- `ch0_flow` combo enum restructured to fix index mismatch (BUG-W550-AC).
- WIZ550 MQTT: field wiring, entry-UI (radio enable + tab visibility), and FW-version
  (`fw_ver[1]` odd/even) gating for MQTT-capable builds.
- WIZ550 GET/SET verification logs promoted to INFO (previously hidden at INFO level); received-
  value logging split into summary (INFO) / full (DEBUG).
- Search/unicast label switching fixed (WIZ550 → "IP Address", WIZ5xxSR → "TCP unicast");
  unicast radio default restored to TCP unicast except when WIZ550 is selected.
- `QTimer` `NameError` fixed (missing `QtCore.` prefix).
- Config path separated to `~/.wizconfig` with auto-migration (fixes first-run crash);
  `default.yaml` keys aligned with code access keys; `auto_hide` staleness fixed.

### Build / Docs
- Build tooling: Everything-based search-tool auto-discovery + bootloader wheel cache.
- Developer hand-off documentation set added under `doc/`.

### Tests
- Accessor-key ⊆ baseline invariant test (T1); WIZ550 WEB YAML ghost-field removal +
  `dns_domain` validation updated; changelog footer test scope narrowed to curriculum docs.

---

## [1.6.2.6] – 2026-05-22

### Features
- Log Level submenu added under the Options menu.
- F4 (Apply Settings) / F8 (FW Upload) keyboard shortcuts added.

### Bug Fixes
- `WIZ550Searcher` now broadcasts on all NICs.
- SET_INFO now sent to the device's current IP rather than the newly-assigned IP.

---

## [1.6.2.5] – 2026-05-22

### Features
- Warn-and-confirm dialog when no NIC exists on the target subnet (WIZ550).
- Runtime log-level switching via a watched YAML config file.
- GUI strings translated Korean → English throughout.

### Bug Fixes
- WIZ550 FW upload: NIC auto-selection for TFTP server binding and upload socket; server IP now
  resolved via OS routing probe / target-IP subnet match, call moved to just before upload.
- WIZ550: firewall rules auto-added/removed around FW upload.
- WIZ550: BOOT-state detection and `working_mode` mapping overhaul; Apply button disabled while
  in BOOT state.
- WIZ550: SET_INFO/RESET now auto-select NIC via OS routing.
- `WIZMSGHandler`: fixed two syntax/indentation errors (empty `if` block).

### Refactoring
- Search-related verbose/TIMING/DIAG logs commented out (multiple rounds); temporary FW-upload
  debug logs removed.

---

## [1.6.2.4] – 2026-05-20

### Features
- WIZ550 FW from Git: TFTP upload integrated into a single dialog (`FWGitDialog`) — separate
  upload window removed. `wiz550_config` carries `target_ip`/`mac`/`pw_setting`; password field
  shown conditionally; download completion auto-triggers TFTP upload, dialog closes 1.5s after
  success.

### Bug Fixes
- 0xD1 unicast: switched from broadcast to per-device IP unicast (per Java reference §4.3).
- WIZ550 FW from Git device-type filter: prevents SR↔S2E cross-flashing.
- `fill_devinfo_wiz550`: fixed missing IP-field disable on DHCP selection.
- Searched-results count re-syncs to include WIZ550 devices after re-search.

### Refactoring
- `WIZ550FWUploadThread` logging reduced (verbose → DEBUG; tftpy → WARNING+).

---

## [1.6.2.3] – 2026-05-19

### Bug Fixes
- **WIZ550 device list text color**: `search_each_dev()` was overwriting WIZ550 rows with the
  orange-red loading color (`QColor(200, 80, 0)`). WIZ550 rows now keep black text and green
  background during S2E device re-query.
- **WIZ550 Channel #0 tab entirely grayed out**: `disable_object()` disables `channel_tab`, but
  the WIZ550 guard in `dev_selected()` only re-enabled `generalTab`. Added
  `channel_tab.setEnabled(True)` to the WIZ550 path.
- **WIZ550 Operation Mode radio buttons disabled**: `_show_wiz1x0_panel(False)` has a side effect
  of disabling `btn_setting`. The WIZ550 branch now explicitly re-enables the four radio buttons,
  restores `btn_setting`, and calls `event_opmode()`.
- **WIZ550 Data Bits combo index out of range**: Protocol encodes data_bits as 2=7-bit / 3=8-bit,
  but code was calling `setCurrentIndex(3)` on a 2-item combo ("7", "8"). Fixed with a lookup
  table `{2: '7', 3: '8'}` + `findText()`. Reverse mapping applied in `fill_setinfo_wiz550()`.

### Refactoring
- Korean comments in WIZ550 code sections translated to English.

---

## [1.6.2.2] – 2026-05-14

### Features
- **JSON Schema validation**: `device.schema.json` and `command-group.schema.json` define strict
  contracts for all DeviceSpec YAML files. `validate_schemas.py` validates all 22 YAML files.
- **WIZ550 protocol engine**: `WIZ550MSGHandler.py` (UDP discovery/get-info/set/reset over
  port 6550) and `WIZ550Profile.py` (SR 162B / S2E 162+ext / WEB 133B struct parsers and
  builders) added as new modules.
- **WIZ550 GUI integration**: Search (`_merge_wiz550_results`), device panel (generalTab reuse),
  Apply / Reset / Factory Reset flows wired up.
- **WIZ550 DeviceSpec YAML**: `specs/devices/wiz550sr.yaml`, `wiz550s2e.yaml`, `wiz550web.yaml`
  added with full field definitions.
- **Test infrastructure**: `tests/conftest.py` with dummy packet fixtures for SR/WEB/S2E
  variants; pytest suite (28 passed, 5 xfailed).

### Bug Fixes
- `version_compare()` crash on non-standard firmware version strings (e.g. empty component).
- `fill_devinfo_wiz550()` GET_INFO payload parse offset was off by 2 bytes — corrected to
  `payload[6:]` for config bytes.

### Refactoring
- Dead code removed: `TCPMulticastScanner.py`, `version_compare_old()`.
- `device_spec_loader` imports consolidated at module level (removed 3 duplicates inside functions).
- Channel widget names unified to 0-indexed convention (`ch0_`, `ch1_`).
- `object_config_for_device()` split into three sub-methods for clarity.

---

## [1.6.2.1] – 2026-05-11

### Features
- **DeviceSpec YAML — serial/pin/security migration**: `_config_serial_for_device()`,
  `_config_status_pin/security_options()` fully migrated from hardcoded device lists to
  DeviceSpec YAML field definitions.
- **YAML `meta:` blocks**: 11 `specs/commands/*.yaml` files annotated with module metadata
  (module name, type, protocol, port, baudrate range).
- **DeviceSpec `module_meta`**: Loader reads `meta:` from command YAML; schema auto-validation
  on load via `validate_schemas.py`.
- **W55RP20 YAML fixes**: 3 YAML errors corrected; `WIZ5XXSR-RP` variant added.
- **`min_version` filtering + WidgetOverride + cache architecture** in `device_spec_loader.py`.

### Documentation
- Wiki updated to v1.6.2.1 with screenshots: Win11 environment, FW from Git dropdown/dialog,
  Terminal panel, WIZ107/108SR configuration.

---

## [1.6.2] – 2026-04-27

### Features
- **FW from Git** (`fw_git_dialog.py`, `fw_git_fetcher.py`): Select and download firmware
  directly from GitHub releases. Dropdown lists available releases per device; downloads to
  temp and hands off to the existing FW upload flow.
- **Terminal utility panel** (`terminal/` package): Full serial/TCP/UDP terminal replacing
  external tools like Hercules.
  - Named macro sequences with preset save/load.
  - TX/RX byte statistics, Send input on the right, Clear resets stats.
  - UDP local port two-row layout with labeled fields.
  - Floating window (Qt.Tool), `Ctrl+T` shortcut, menu entry.
  - Run button focus fix, IP:Port gap fix, macro name bug fix.
- **Exit button restored** on toolbar; `Ctrl+Q` shortcut added to Exit menu.
- Toolbar `columnStretch` migrated to automatic proportional distribution.

### Bug Fixes
- `FWUploadThread`: `WIZMSGHandler.run()` direct call removed (QThread design violation).
- `FWUploadThread`: `timer1` cancel on failure + `print` → `logger` conversion.
- `WIZMSGHandler`: opcode-level fallback `emit` added to prevent UI hang on exception.
- `RotatingFileHandler` assignment bug fixed; `funclog` exception re-raise restored;
  remaining `print` calls converted to `logger`.
- `config/*.json` packaging: `fw_sources.json` was missing from PyInstaller bundle.
- Terminal `TCPClientHandler`: intermediate `emit` in `run()` causing QThread GC crash removed.
- `event_search_method` converted to event-based pattern (was polling).

### Style
- Toolbar: 9 button heights unified to 68 px (`_btn_terminal` included).

---

## [1.6.1.1] – 2026-04-17

### Security Fixes
- **HIGH-01**: `struct.unpack` call wrapped in try/except to prevent crash on malformed packets.
- **HIGH-03**: UDP response `split()` unbounded loop defended; multi-packet test added.
- **HIGH-04**: FW response parsing `IndexError`/`ValueError` guarded.
- **MED-01, MED-02, LOW-01**: Three additional security vulnerabilities corrected.

### Features
- **BOOT file upload block**: Warning dialog shown when user tries to upload a BOOT-type
  firmware image; upload is prevented.
- **Multi-packet / multi-device UDP reception** (#35): Missing response packets from
  simultaneous devices corrected.
- **About dialog**: Firefox-style version check; direct link to GitHub Releases; layout and
  background style improvements.

---

## [1.6.1] – 2026-04-03

### Features
- **WIZ1x0SR support** (WIZ100SR / WIZ105SR / WIZ110SR):
  - Binary FIND / IMIN / SETT / SETC protocol over UDP port 1460.
  - New modules: `WIZ1x0MSGHandler.py`, `WIZ1x0Profile.py` (163-byte struct).
  - Dedicated 3-tab panel (`wiz1x0_tab`): Network / Serial / Option — fully separate from
    `generalTab`.
  - Search result rows highlighted with a light blue background.
  - Apply / Reset / Upload button routing for WIZ1x0SR devices.
  - F5 search shortcut + compact layout refinements.

### Bug Fixes (8 issues found during real device testing)
- `BOARD_INFO_SIZE` corrected 163 → 159 (search was failing entirely).
- Receive socket bound to `INADDR_ANY` so cross-subnet search works.
- SETT packet sent as broadcast (was unicast — device never received it).
- NIC IP bound for WIZ1x0SR Searcher (was unbound).
- `WinError 10048 / 10049` on repeated search fixed (socket reuse).
- Apply response: incomplete reply caused `int('')` crash — switched to `dev_profile.update()`
  merge instead of full replacement.
- `resizeRowsToContents()` called after WIZ1x0SR row insertion (row height mismatch).
- `WIZ1x0SR` rows: removed per-row `midfont`, now inherits default table font.

---

## [1.6.0.1] – 2026-03-31

### Bug Fixes
- WIZ107SR DDNS server list corrected to `dyndns.com` only (firmware supports one entry).
- WIZ107SR/108SR: PPPoE selected → local IP fields now disabled correctly.
- Error response dialog now shows the device's raw `ER` reply text directly.
- `build.ps1`: PFX password parameter removed (supports passwordless self-signed certificate).

---

## [1.6.0] – 2026-03-26

### Features
- **WIZ107SR / WIZ108SR full support**:
  - `cmd_107sr`: 42-command set including DD (DDNS) and PO (Telnet/TCP Raw).
  - DDNS set commands: DD, DX, DP, DI, DW, DH.
  - PPPoE set commands: PI, PP; IM=2 for PPPoE mode.
  - Telnet / TCP Raw selection via PO command.
  - TR command excluded from set list; "Transfer" UI element hidden.
  - 9-bit data-bits constraint enforced: parity locked to NONE, stop bits locked to 1.
  - Maximum baud rate capped at 230400.
  - PPPoE selection disables IP/gateway/subnet fields.
  - DDNS / PPPoE tab content shown only for WIZ107/108 devices.
  - DDNS server list expanded from 3 to 7 entries (matching VB.NET original).
- **107_108_config independent tool** (`107_108_config/`): Python port of VB.NET
  ConfigTool107 v1.4.4.1. Run with `uv run python -m 107_108_config`.
- **build.ps1 code signing**: Self-signed certificate support; `-NoSign` flag skips signing;
  signed build gets `_signed` filename suffix.

### Bug Fixes
- `get_setting_result()` response parsing switched to content-based approach (MC field 17-char
  check), matching VB.NET original — prevents crash when device reboots immediately after Set.
- Network interface list: IPv4-only filter strengthened; entries sorted; first entry
  auto-selected on startup.
- DDNS / PPPoE tab layout redesigned for WIZ107/108 (PPPoE+NetProto side-by-side, DDNS in
  scroll area).

---

## [1.5.9] – 2026-03-12

### Bug Fixes
- `KeyError` crash when clicking a device row while search is still running.
- CSV load: `mn_list` bytes→str conversion was missing; invalid bytes now displayed as `(xxyy)`.
- `_merge_search_results()`: empty values no longer overwrite existing Name data on second search.
- `_finalize_timer` disconnect `TypeError` fixed; timer accumulation on repeated search removed.
- Progress bar: disappearance during Querying phase removed at root; `auto_hide_delay` setting
  now applied immediately without restart.
- FW upload failure now shows a statusbar message.

### Refactoring
- Comprehensive Pylance type-safety pass: all type errors resolved.
- Dead code removed (I-02, I-05); retry delay now configurable via Advanced settings (I-06).
- `getsearch_each_dev()` rewritten O(N²) → O(1) with `mn_list` synchronization.
- Packaging: `WIZMakeCMD.py` runtime dependency added explicitly.

### i18n
- Advanced Search Options dialog UI text translated to English.

---

## [1.5.8.x] – 2026-02-19 ~ 2026-03-09

### Features
- **YAML-based search timing configuration** (`config/device_search_timing.yaml`): broadcast
  timeout, retry count, query delay, and pgbar `auto_hide_delay` all configurable at runtime
  without code changes.
- **Parallel per-device UDP queries**: each device queried through its own dedicated socket
  (ThreadPoolExecutor); significantly reduces total search time.
- **Unified progress bar** across multiple retry rounds: Phase 1 (0–60%), Phase 3 (60–90%),
  completion (100%); indeterminate animation while querying.
- **Clear Results button** + retry search time tracking.
- **Broadcast timeout UI** field in Advanced Search Options.
- System search time displayed in status bar immediately.

### Bug Fixes
- Per-row `try/except` + `errors='replace'` decode in table display prevents crash on
  corrupted device data.
- Atomic per-packet parsing in `check_parameter()` prevents MAC/name/version list misalignment.
- Bounds checks added for `mn`/`vr`/`st_list` in `_merge_search_results`.
- Safe MC field access in `getsearch_each_dev()`; missing MC logged + shown in status bar.
- Deduplication fix + presearch flag to prevent double-run on first search.
- Stale progress bar on new search cleared.
- pgbar text moved to status bar (was floating over results).
- CSV path: `Decimal` YAML type support added for float precision.
- Retry search now runs even when no devices found (`devnum == 0`).

---

## [1.5.7.x / 1.5.6.x] – 2026-02 (cumulative search & search methods)

### Features
- **Cumulative search mode**: "Detected" column tracks devices seen across multiple searches;
  previous results are preserved between runs.
- **TCP multicast scanner** (`ThreadPoolExecutor`): reaches devices on different subnets.
- **Mixed search mode**: combines broadcast and TCP multicast in a single pass.
- **IP20 support**: integrated into `W55RP20_FAMILY` and `W55RP20_CMDSET`.
- **W55RP20 high-speed baudrates**: 1 M / 2 M / 4 M / 8 M bps added for applicable firmware
  versions; firmware-version-based branching implemented.
- Elapsed search time displayed in status bar.
- Progress bar auto-hide after search completion.

### Bug Fixes
- `W55RP20-S2E-2CH`: `ch2_baud` index offset corrected.
- `W55RP20-S2E`: SO / RO SSL receive timeout handling improved.
- `conf_sock` created for TCP multicast and Mixed search modes.
- Search completion message restored after per-device query.

---

## [1.5.6] – 2024-07-17

### Features
- BOOT / UPGRADE mode detection: only boot commands used in those modes; Options tab and
  Channel tab disabled automatically.
- `build.ps1` introduced as the canonical build script.
- `version` file: version string moved from code to external `version` file.

### Bug Fixes
- Apply setting failed on WIZ5xx firmware < 1.0.8.
- `group_packing_12` renamed to `group_modbus_option`.
- Raw string notation added to regex patterns for IP/port (was causing SyntaxWarning).

---

*Versions prior to 1.5.5 are not covered in this log.*
