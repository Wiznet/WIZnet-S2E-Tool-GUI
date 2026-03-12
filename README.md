- [Configuration Tool Wiki](#configuration-tool-wiki)
- [Overview](#overview)
  - [Support Devices](#support-devices)
    - [1 Port Serial to Ethernet Module](#1-port-serial-to-ethernet-module)
    - [2 Port Serial to Ethernet Module](#2-port-serial-to-ethernet-module)
    - [Pre-programmed MCU](#pre-programmed-mcu)
- [What's New](#whats-new)
- [CLI Configuration Tool](#cli-configuration-tool)
- [TroubleShooting](#troubleshooting)
  - [Report](#report)

---

# [Configuration Tool Wiki](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/wiki)

New to the WIZnet Configuration Tool? Visit the Wiki page.

The wiki page contains getting started guides, how to use tool, and troubleshooting guides.

You can check the contents of configuration tool wiki on the [Wiki tab.](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/wiki)


# Overview

WIZnet-S2E-Tool-GUI is Configuration Tool for WIZnet serial to ethernet devices.

Python interpreter based and it is platform independent. It works on python version 3.6 or later.

<img src="https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/blob/master/doc/images/wizconfig_main_V1.0.0.png" width="85%"></img>


## Support Devices

### 1 Port Serial to Ethernet Module

- [WIZ750SR](https://docs.wiznet.io/Product/S2E-Module/WIZ750SR)
  - [WIZ750SR Github repository](https://github.com/Wiznet/WIZ750SR)
- [WIZ750SR-100](https://docs.wiznet.io/Product/S2E-Module/WIZ750SR-1xx-Series/WIZ750SR-100)
- [WIZ750SR-105](https://docs.wiznet.io/Product/S2E-Module/WIZ750SR-1xx-Series/WIZ750SR-105)
- [WIZ750SR-110](https://docs.wiznet.io/Product/S2E-Module/WIZ750SR-1xx-Series/WIZ750SR-110)
- [WIZ107SR](https://docs.wiznet.io/Product/S2E-Module/WIZ107SR) & [WIZ108SR](https://docs.wiznet.io/Product/S2E-Module/WIZ108SR)
- WIZ5xxSR-RP Series
  - [WIZ500SR-RP](https://docs.wiznet.io/Product/S2E-Module/WIZ5xxSR-RP-Series/WIZ500SR-RP/overview)
  - [WIZ505SR-RP](https://docs.wiznet.io/Product/S2E-Module/WIZ5xxSR-RP-Series/WIZ505SR-RP/overview)
  - [WIZ510SR-RP](https://docs.wiznet.io/Product/S2E-Module/WIZ5xxSR-RP-Series/WIZ510SR-RP/overview)

### 2 Port Serial to Ethernet Module

- [WIZ752SR-120](https://docs.wiznet.io/Product/S2E-Module/WIZ752SR-12x-Series/WIZ752SR-120)
- [WIZ752SR-125](https://docs.wiznet.io/Product/S2E-Module/WIZ752SR-12x-Series/WIZ752SR-125)

### Pre-programmed MCU
- [W7500(P)-S2E](https://docs.wiznet.io/Product/Pre-programmed-MCU/W7500P-S2E/w7500p-s2e-EN)


## Supported Firmware Versions

**Important Compatibility Note**: WIZnet-S2E-Tool-GUI version 1.5.5 requires firmware version 1.0.8 or higher to function correctly.


# What's New

## v1.5.9

### New Devices Support

- **W55RP20-S2E-2CH**: 2-channel variant support with dedicated command set and UI
- **W232N / IP20**: Added device support including SSL TCP Client and MQTTS features (firmware v1.1.8+)
- **W55RP20 high-speed baudrates**: 1M / 2M / 4M / 8M bps options for W55RP20 series
- **WIZ750SR Modbus**: MB (Modbus) parameter support

### Retry Search

- Search automatically repeats up to **3 times** by default, accumulating results across rounds to minimize missed devices
- Stops early when the expected device count is reached
- Configure via: Search options > **Set search retry count**

### Advanced Search Options

YAML-based configuration system (`device_search_config.yaml`) for fine-grained control:

| Setting | Description |
|---------|-------------|
| Phase 1 broadcast timeout | UDP broadcast wait time |
| Phase 1 loop select timeout | Additional wait after last response |
| Phase 3 device query timeout | Per-device info query timeout |
| Progress bar update step | pgbar refresh granularity (%) |
| Progress bar auto-hide delay | Delay before pgbar disappears after search (ms) |
| Show timing in status bar | Debug: show elapsed seconds and retry count |
| On-demand device query | Skip Phase 3 at search time; fetch info on first click instead |

### Performance Improvements

- **Parallel UDP queries**: Phase 3 device queries use dedicated sockets per device, all started simultaneously — total time ≈ slowest single device RTT instead of sum of all RTTs
- **O(1) search result processing**: `getsearch_each_dev()` refactored from O(N²) full re-scan to O(1) per-packet update
- **mn_list synchronization**: Fixed list misalignment between MAC/MN/VR/ST lists that caused incorrect device info display

### Bug Fixes

- Fixed blank Name column on second search: `_merge_search_results()` no longer overwrites existing model name with empty bytes from Phase 1
- Fixed progress bar disappearing during "Querying devices..." — root cause was `SearchContext.__exit__()` scheduling an uncancellable `QTimer.singleShot(2000, pgbar.hide)` at search start, which fired during Phase 3 `processEvents()`
- Fixed `_finalize_timer` accumulation (BUG-04): timer is now stopped and reconnected on each use instead of stacking `singleShot` callbacks
- Fixed per-row decode errors in table display using `errors='replace'`
- Fixed search response packet parsing to be atomic per-packet, preventing list misalignment
- Fixed FW upload failure not updating status bar message
- Fixed Advanced Search Options changes (pgbar auto-hide delay) not taking effect immediately due to missing in-memory sync between `device_search_config` and `timing_config` instances

### Progress Bar

- Shows indeterminate animation from the moment search starts (previously appeared several seconds late)
- Maintained continuously across all retry cycles without resetting
- Snaps to 100% on completion, then auto-hides after configurable delay

---

# CLI Configuration Tool

In addition to this GUI configuration tool, we provides a command line based configuration tool.

With just a few options, you can easily set up your device.

One of the features of the CLI tool is that **it supports multi device configuration**. If you have multiple devices, try it.

CLI configuration tool can be refer from [WIZnet-S2E-Tool github page.](https://github.com/Wiznet/WIZnet-S2E-Tool)


# TroubleShooting

## Report

If you have any problems, use one of the links below and **please report the problem.**

- [WIZnet Developer Forum](https://forum.wiznet.io/)
- [Github Issue page](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/issues)
- [Discusstion](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/discussions)


