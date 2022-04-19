- [Overview](#overview)
  - [Support Devices](#support-devices)
    - [1 Port Serial to Ethernet Module](#1-port-serial-to-ethernet-module)
    - [2 Port Serial to Ethernet Module](#2-port-serial-to-ethernet-module)
    - [Pre-programmed MCU](#pre-programmed-mcu)
    - [Security Serial to Ethernet Module](#security-serial-to-ethernet-module)
- [Wiki](#wiki)
- [Environment](#environment)
  - [Windows](#windows)
  - [Linux](#linux)
    - [Ubuntu](#ubuntu)
- [CLI Configuration Tool](#cli-configuration-tool)
- [TroubleShooting](#troubleshooting)

---

# Overview

WIZnet-S2E-Tool-GUI is Configuration Tool for WIZnet serial to ethernet devices.

Python interpreter based and it is platform independent. It works on python version 3.6 or later.

<img src="https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/blob/master/doc/images/wizconfig_main_V1.0.0.png" width="85%"></img>


## Support Devices

### 1 Port Serial to Ethernet Module

- [WIZ750SR](https://docs.wiznet.io/Product/S2E-Module/WIZ750SR/wiz750sr)
  - [WIZ750SR Github repository](https://github.com/Wiznet/WIZ750SR)
- [WIZ750SR-100](https://docs.wiznet.io/Product/S2E-Module/WIZ750SR-1xx-Series/WIZ750SR-100/wiz750sr_100)
- [WIZ750SR-105](https://docs.wiznet.io/Product/S2E-Module/WIZ750SR-1xx-Series/WIZ750SR-105/wiz750sr_105)
- [WIZ750SR-110](https://docs.wiznet.io/Product/S2E-Module/WIZ750SR-1xx-Series/WIZ750SR-110/wiz750sr_110)
- [WIZ107SR](http://www.wiznet.io/product-item/wiz107sr/) & [WIZ108SR](http://www.wiznet.io/product-item/wiz108sr/)

### 2 Port Serial to Ethernet Module

- [WIZ752SR-120](https://docs.wiznet.io/Product/S2E-Module/WIZ752SR-12x-Series/WIZ752SR-120/wiz752sr_120)
- [WIZ752SR-125](https://docs.wiznet.io/Product/S2E-Module/WIZ752SR-12x-Series/WIZ752SR-125/wiz752sr_125)

### Pre-programmed MCU
- [W7500(P)-S2E](https://docs.wiznet.io/Product/Pre-programmed-MCU/W7500P-S2E/w7500p-s2e-EN)

### Security Serial to Ethernet Module

- [WIZ510SSL](https://docs.wiznet.io/Product/S2E-Module/WIZ510SSL/wiz510ssl)

---

# Wiki

New to the WIZnet Configuration Tool? Visit the Wiki page.

The wiki page contains getting started guides, how to use tool, and troubleshooting guides.

You can check the contents of configuration tool wiki on the [Wiki tab.](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/wiki)

---

# Environment

## Windows

Please refer to below repository's wiki page.

- [WIZnet-S2E-Tool-GUI wiki: Getting started guide](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/wiki/Getting-started-guide_en)

* Windows 7

  - If the Windows 7 service pack version is low, there may be a problem running this tool.

* Windows 10

Recommended to use tool at a resolution of **1440\*900 or higher.**

You can download Windows excutable file from [release page.](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/releases)

## Linux

Please refer to refer to below wiki page.

- [Getting started guide: Using Python - Linux](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/wiki/Getting-started-guide_en#using-python-linux)

### Ubuntu

WIZnet-S2E-Tool-GUI is worked on **python 3.x** version.

Check the python version with below command

```
$ python --version
```

Install:

```
$ git clone https://github.com/Wiznet/WIZnet-S2E-Tool-GUI
$ cd WIZnet-S2E-Tool-GUI
$ sudo pip install -r requirements.txt
```

Now, run the configuration tool.
```
$ python main_gui.py
```

You can use the [CLI configuration tool](https://github.com/Wiznet/WIZnet-S2E-Tool) also.

---

# CLI Configuration Tool

In addition to this GUI configuration tool, we provides a command line based configuration tool.

With just a few options, you can easily set up your device.

One of the features of the CLI tool is that **it supports multi device configuration**. If you have multiple devices, try it.

CLI configuration tool can be refer from [WIZnet-S2E-Tool github page.](https://github.com/Wiznet/WIZnet-S2E-Tool)

---

# TroubleShooting

If you have any problems, use one of the links below and **please report the problem.**

- [Github Issue page](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/issues)
- [WIZnet Developer Forum](https://forum.wiznet.io/)

---
