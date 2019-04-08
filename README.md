- [Overview](#overview)
  - [Environment](#environment)
- [Support Devices](#support-devices)
  - [1 Port Serial to Ethernet Module](#1-port-serial-to-ethernet-module)
  - [2 Port Serial to Ethernet Module](#2-port-serial-to-ethernet-module)
- [CLI Configuration Tool](#cli-configuration-tool)
- [Wiki](#wiki)
- [TroubleShooting](#troubleshooting)


# Overview
WIZnet-S2E-Tool-GUI is Configuration Tool for WIZnet serial to ethernet devices. \
Python interpreter based and it is platform independent. It works on version 3.x python. 

<img src="https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/blob/master/doc/images/wizconfig_main_V1.0.0.png" width="85%"></img>


## Environment

### Windows 

You can refer to below wiki page.

  * [WIZnet-S2E-Tool-GUI wiki: Getting started guide](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/wiki/Getting-started-guide)


- Windows 7  

  * If the Windows 7 service pack version is low, there may be a problem running this tool.


- Windows 10  

Recommended to use tool at a resolution of **1440*900 or higher.** 

You can download Windows excutable file from [release page.](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/releases)


### Linux

You can refer to below wiki page.

  * [Getting started guide: Using Python - Linux](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/wiki/Getting-started-guide#using-python-linux)

#### Ubuntu 

WIZnet-S2E-Tool-GUI is worked on **python 3.x** version.

So please check the ubuntu version.

    $ python --version

Install:

    $ git clone https://github.com/Wiznet/WIZnet-S2E-Tool-GUI
    $ cd WIZnet-S2E-Tool-GUI
    $ sudo pip install -r requirements.txt

Now, run the configuration tool.

    $ python main_gui.py
  
You can use the [CLI configuration tool](https://github.com/Wiznet/WIZnet-S2E-Tool) also.

----

# Support Devices

## 1 Port Serial to Ethernet Module
- [WIZ750SR](http://wizwiki.net/wiki/doku.php?id=products:wiz750sr:start)
  - [WIZ750SR Github page](https://github.com/Wiznet/WIZ750SR)
- [WIZ750SR-100](http://wizwiki.net/wiki/doku.php?id=products:wiz750sr-100:start)
- [WIZ750SR-105](http://wizwiki.net/wiki/doku.php?id=products:wiz750sr-105:start)
- [WIZ750SR-110](http://wizwiki.net/wiki/doku.php?id=products:wiz750sr-110:start)
- [WIZ107SR](http://www.wiznet.io/product-item/wiz107sr/) & [WIZ108SR](http://www.wiznet.io/product-item/wiz108sr/)

## 2 Port Serial to Ethernet Module
- [WIZ752SR-120](https://wizwiki.net/wiki/doku.php?id=products:s2e_module:wiz752sr-120:start)
- [WIZ752SR-125](https://wizwiki.net/wiki/doku.php?id=products:s2e_module:wiz752sr-125:start)

----
# CLI Configuration Tool

CLI: Command Line Interface Configuration Tool.

CLI configuration tool for S2E devices can be refer from [WIZnet-S2E-Tool github page.](https://github.com/Wiznet/WIZnet-S2E-Tool)

----

# Wiki

You can check the contents of configuration tool wiki on the [WIZnet-S2E-Tool-GUI wiki page.](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/wiki)

----
# TroubleShooting

If you have any problems, use one of the links below and **please report the problem.**

- [Github Issue page](https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/issues)
- [WIZnet Forum](https://forum.wiznet.io/)

----

