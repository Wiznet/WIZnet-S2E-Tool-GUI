# WIZnet S2E 명령어 레퍼런스

**생성일**: 2026-01-14 16:19:22
**소스**: config\devices\devices_sample.json

---

## 목차

- [WIZ750SR](#wiz750sr)
- [W55RP20-S2E](#w55rp20-s2e)
- [W55RP20-S2E-2CH (Dual Channel)](#w55rp20-s2e-2ch)
- [IP20](#ip20)

---

## WIZ750SR

**모델 ID**: `WIZ750SR`
**카테고리**: ONE_PORT

**최소 펌웨어 버전**: 1.0.0

### 명령어 목록

| 코드 | 이름 | 접근 | 패턴 | 옵션 | UI 위젯 |
|------|------|------|------|------|---------|
| `BR` | UART Baud rate | 읽기/쓰기 | `^([0-9]|1[0-5])$` | 16개 옵션 | `combo` |
| `CA` | Type and Direction of User I/O pin A | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CB` | Type and Direction of User I/O pin B | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CC` | Type and Direction of User I/O pin C | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CD` | Type and Direction of User I/O pin D | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CP` | Connection Password Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `DB` | UART Data bit length | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `DG` | Serial Debug Message Enable | 읽기/쓰기 | `^[0-4]$` | 5개 옵션 | `combo` |
| `DS` | DNS Server address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `FL` | UART Flow Control | 읽기/쓰기 | `^[0-4]$` | 5개 옵션 | `combo` |
| `FR` | Device Factory Reset | 쓰기전용 | - | - | `text` |
| `GW` | Gateway address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `IM` | IP address Allocation Mode | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `IT` | Inactivity Timer Value | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `KA` | TCP Keep-alive Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `KE` | TCP Keep-alive Retry Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `KI` | TCP Keep-alive Initial Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `LI` | Local IP address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `LP` | Local port number | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `MC` | MAC address | 읽기전용 | `^([0-9a-fA-F]{2}:){5}([0-9a...` | - | `mac` |
| `MN` | Product Name | 읽기전용 | - | - | `text` |
| `NP` | Connection Password | 읽기/쓰기 | - | - | `text` |
| `OP` | Network Operation Mode | 읽기/쓰기 | `^[0-3]$` | 4개 옵션 | `combo` |
| `PD` | Char Delimiter | 읽기/쓰기 | `^([0-9a-fA-F][0-9a-fA-F])$` | - | `text` |
| `PR` | UART Parity bit | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `PS` | Size Delimiter | 읽기/쓰기 | `^([0-9]|[1-9][0-9]|1[0-9]{2...` | - | `number` |
| `PT` | Time Delimiter | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `RH` | Remote Host IP address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `RI` | TCP Reconnection Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `RP` | Remote Host Port number | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `RT` | Device Reboot | 쓰기전용 | - | - | `text` |
| `S0` | Status of pin S0 (PHY Link or DTR) | 읽기전용 | `^[0-1]$` | 2개 옵션 | `text` |
| `S1` | Status of pin S1 (TCP Connection or DST) | 읽기전용 | `^[0-1]$` | 2개 옵션 | `text` |
| `SB` | UART Stop bit length | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `SC` | Status pin S0 and S1 Operation Mode Setting | 읽기/쓰기 | `^([0-1]{2})$` | 2개 옵션 | `combo` |
| `SM` | Subnet mask | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `SP` | Search ID Code | 읽기/쓰기 | - | - | `text` |
| `SS` | Command mode Switch Code | 읽기/쓰기 | `^(([0-9a-fA-F][0-9a-fA-F]){...` | - | `text` |
| `ST` | Operation status | 읽기전용 | - | - | `text` |
| `SV` | Save Device Setting | 쓰기전용 | - | - | `text` |
| `TE` | Command mode Switch Code Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `TR` | TCP Retransmission Retry count | 읽기/쓰기 | `^([1-9]|[1-9][0-9]|1[0-9][0...` | - | `number` |
| `VR` | Firmware Version | 읽기전용 | - | - | `text` |

### 명령어 상세

#### BR - UART Baud rate

| 값 | 설명 |
|-----|------|
| `0` | 300 |
| `1` | 600 |
| `2` | 1200 |
| `3` | 1800 |
| `4` | 2400 |
| `5` | 4800 |
| `6` | 9600 |
| `7` | 14400 |
| `8` | 19200 |
| `9` | 28800 |
| `10` | 38400 |
| `11` | 57600 |
| `12` | 115200 |
| `13` | 230400 |
| `14` | 460800 |
| `15` | 921600 |

#### CA - Type and Direction of User I/O pin A

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CB - Type and Direction of User I/O pin B

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CC - Type and Direction of User I/O pin C

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CD - Type and Direction of User I/O pin D

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CP - Connection Password Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### DB - UART Data bit length

| 값 | 설명 |
|-----|------|
| `0` | 7-bit |
| `1` | 8-bit |

#### DG - Serial Debug Message Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable Level 1 |
| `2` | Enable Level 2 |
| `3` | Enable Level 3 |
| `4` | Enable Level 4 |

#### FL - UART Flow Control

| 값 | 설명 |
|-----|------|
| `0` | NONE |
| `1` | XON/XOFF |
| `2` | RTS/CTS |
| `3` | RTS on TX |
| `4` | RTS on TX (invert) |

#### IM - IP address Allocation Mode

| 값 | 설명 |
|-----|------|
| `0` | Static IP |
| `1` | DHCP |

#### KA - TCP Keep-alive Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### OP - Network Operation Mode

| 값 | 설명 |
|-----|------|
| `0` | TCP Client mode |
| `1` | TCP Server mode |
| `2` | TCP Mixed mode |
| `3` | UDP mode |

#### PR - UART Parity bit

| 값 | 설명 |
|-----|------|
| `0` | NONE |
| `1` | ODD |
| `2` | EVEN |

#### S0 - Status of pin S0 (PHY Link or DTR)

| 값 | 설명 |
|-----|------|
| `0` | PHY Link Up or Device not ready |
| `1` | PHY Link Down or Device ready |

#### S1 - Status of pin S1 (TCP Connection or DST)

| 값 | 설명 |
|-----|------|
| `0` | Not connected |
| `1` | Connected |

#### SB - UART Stop bit length

| 값 | 설명 |
|-----|------|
| `0` | 1-bit |
| `1` | 2-bit |

#### SC - Status pin S0 and S1 Operation Mode Setting

| 값 | 설명 |
|-----|------|
| `00` | PHY Link Status or TCP Connection Status |
| `11` | DTR/DSR |

#### TE - Command mode Switch Code Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

---

## W55RP20-S2E

**모델 ID**: `W55RP20-S2E`
**카테고리**: SECURITY_ONE_PORT

**최소 펌웨어 버전**: 1.0.0

### 명령어 목록

| 코드 | 이름 | 접근 | 패턴 | 옵션 | UI 위젯 |
|------|------|------|------|------|---------|
| `BR` | UART Baud rate | 읽기/쓰기 | `^([0-9]|1[0-5])$` | 16개 옵션 | `combo` |
| `CA` | Type and Direction of User I/O pin A | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CB` | Type and Direction of User I/O pin B | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CC` | Type and Direction of User I/O pin C | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CD` | Type and Direction of User I/O pin D | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CE` | Client Certificate Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `CP` | Connection Password Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `DB` | UART Data bit length | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `DG` | Serial Debug Message Enable | 읽기/쓰기 | `^[0-4]$` | 5개 옵션 | `combo` |
| `DS` | DNS Server address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `FL` | UART Flow Control | 읽기/쓰기 | `^[0-4]$` | 5개 옵션 | `combo` |
| `FR` | Device Factory Reset | 쓰기전용 | - | - | `text` |
| `GW` | Gateway address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `IM` | IP address Allocation Mode | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `IT` | Inactivity Timer Value | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `KA` | TCP Keep-alive Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `KE` | TCP Keep-alive Retry Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `KI` | TCP Keep-alive Initial Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `LC` | Client Certificate | 쓰기전용 | - | - | `textarea` |
| `LI` | Local IP address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `LP` | Local port number | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `MC` | MAC address | 읽기전용 | `^([0-9a-fA-F]{2}:){5}([0-9a...` | - | `mac` |
| `MN` | Product Name | 읽기전용 | - | - | `text` |
| `NP` | Connection Password | 읽기/쓰기 | - | - | `text` |
| `OC` | Root CA | 쓰기전용 | - | - | `textarea` |
| `OP` | Network Operation Mode - Extended | 읽기/쓰기 | `^[0-6]$` | 7개 옵션 | `combo` |
| `PD` | Char Delimiter | 읽기/쓰기 | `^([0-9a-fA-F][0-9a-fA-F])$` | - | `text` |
| `PK` | Private Key | 쓰기전용 | - | - | `textarea` |
| `PO` | Status of Modbus protocol | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `PR` | UART Parity bit | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `PS` | Size Delimiter | 읽기/쓰기 | `^([0-9]|[1-9][0-9]|1[0-9]{2...` | - | `number` |
| `PT` | Time Delimiter | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `PU` | MQTT Publish topic | 읽기/쓰기 | - | - | `text` |
| `QC` | MQTT options - Client ID | 읽기/쓰기 | - | - | `text` |
| `QK` | MQTT Keep-Alive | 읽기/쓰기 | - | - | `number` |
| `QO` | MQTT QoS level | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `QP` | MQTT options - Password | 읽기/쓰기 | - | - | `text` |
| `QU` | MQTT Options - User name | 읽기/쓰기 | - | - | `text` |
| `RC` | Root CA Option | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `RH` | Remote Host IP address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `RI` | TCP Reconnection Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `RP` | Remote Host Port number | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `RT` | Device Reboot | 쓰기전용 | - | - | `text` |
| `SB` | UART Stop bit length | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `SM` | Subnet mask | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `SO` | SSL receive timeout | 읽기/쓰기 | - | - | `number` |
| `SP` | Search ID Code | 읽기/쓰기 | - | - | `text` |
| `SS` | Command mode Switch Code | 읽기/쓰기 | `^(([0-9a-fA-F][0-9a-fA-F]){...` | - | `text` |
| `ST` | Operation status | 읽기전용 | - | - | `text` |
| `SV` | Save Device Setting | 쓰기전용 | - | - | `text` |
| `TE` | Command mode Switch Code Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `U0` | MQTT Subscribe topic 1 | 읽기/쓰기 | - | - | `text` |
| `U1` | MQTT Subscribe topic 2 | 읽기/쓰기 | - | - | `text` |
| `U2` | MQTT Subscribe topic 3 | 읽기/쓰기 | - | - | `text` |
| `VR` | Firmware Version | 읽기전용 | - | - | `text` |

### 명령어 상세

#### BR - UART Baud rate

| 값 | 설명 |
|-----|------|
| `0` | 300 |
| `1` | 600 |
| `2` | 1200 |
| `3` | 1800 |
| `4` | 2400 |
| `5` | 4800 |
| `6` | 9600 |
| `7` | 14400 |
| `8` | 19200 |
| `9` | 28800 |
| `10` | 38400 |
| `11` | 57600 |
| `12` | 115200 |
| `13` | 230400 |
| `14` | 460800 |
| `15` | 921600 |

#### CA - Type and Direction of User I/O pin A

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CB - Type and Direction of User I/O pin B

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CC - Type and Direction of User I/O pin C

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CD - Type and Direction of User I/O pin D

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CE - Client Certificate Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### CP - Connection Password Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### DB - UART Data bit length

| 값 | 설명 |
|-----|------|
| `0` | 7-bit |
| `1` | 8-bit |

#### DG - Serial Debug Message Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable Level 1 |
| `2` | Enable Level 2 |
| `3` | Enable Level 3 |
| `4` | Enable Level 4 |

#### FL - UART Flow Control

| 값 | 설명 |
|-----|------|
| `0` | NONE |
| `1` | XON/XOFF |
| `2` | RTS/CTS |
| `3` | RTS on TX |
| `4` | RTS on TX (invert) |

#### IM - IP address Allocation Mode

| 값 | 설명 |
|-----|------|
| `0` | Static IP |
| `1` | DHCP |

#### KA - TCP Keep-alive Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### OP - Network Operation Mode - Extended

| 값 | 설명 |
|-----|------|
| `0` | TCP Client mode |
| `1` | TCP Server mode |
| `2` | TCP Mixed mode |
| `3` | UDP mode |
| `4` | SSL TCP Client mode |
| `5` | MQTT Client |
| `6` | MQTTS Client |

#### PO - Status of Modbus protocol

| 값 | 설명 |
|-----|------|
| `0` | None |
| `1` | Modbus RTU |
| `2` | Modbus ASCII |

#### PR - UART Parity bit

| 값 | 설명 |
|-----|------|
| `0` | NONE |
| `1` | ODD |
| `2` | EVEN |

#### QO - MQTT QoS level

| 값 | 설명 |
|-----|------|
| `0` | At most once |
| `1` | At least once |
| `2` | Exactly once |

#### RC - Root CA Option

| 값 | 설명 |
|-----|------|
| `0` | None |
| `1` | Optional |
| `2` | Required |

#### SB - UART Stop bit length

| 값 | 설명 |
|-----|------|
| `0` | 1-bit |
| `1` | 2-bit |

#### TE - Command mode Switch Code Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

---

## W55RP20-S2E-2CH (Dual Channel)

**모델 ID**: `W55RP20-S2E-2CH`
**카테고리**: SECURITY_TWO_PORT

**최소 펌웨어 버전**: 1.0.0

### 명령어 목록

| 코드 | 이름 | 접근 | 패턴 | 옵션 | UI 위젯 |
|------|------|------|------|------|---------|
| `BR` | UART Baud rate | 읽기/쓰기 | `^([0-9]|1[0-5])$` | 16개 옵션 | `combo` |
| `CA` | Type and Direction of User I/O pin A | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CB` | Type and Direction of User I/O pin B | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CC` | Type and Direction of User I/O pin C | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CD` | Type and Direction of User I/O pin D | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CE` | Client Certificate Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `CP` | Connection Password Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `DB` | UART Data bit length | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `DG` | Serial Debug Message Enable | 읽기/쓰기 | `^[0-4]$` | 5개 옵션 | `combo` |
| `DS` | DNS Server address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `FL` | UART Flow Control | 읽기/쓰기 | `^[0-4]$` | 5개 옵션 | `combo` |
| `FR` | Device Factory Reset | 쓰기전용 | - | - | `text` |
| `GW` | Gateway address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `IM` | IP address Allocation Mode | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `IT` | Inactivity Timer Value | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `KA` | TCP Keep-alive Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `KE` | TCP Keep-alive Retry Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `KI` | TCP Keep-alive Initial Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `LC` | Client Certificate | 쓰기전용 | - | - | `textarea` |
| `LI` | Local IP address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `LP` | Local port number | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `MC` | MAC address | 읽기전용 | `^([0-9a-fA-F]{2}:){5}([0-9a...` | - | `mac` |
| `MN` | Product Name | 읽기전용 | - | - | `text` |
| `NP` | Connection Password | 읽기/쓰기 | - | - | `text` |
| `OC` | Root CA | 쓰기전용 | - | - | `textarea` |
| `OP` | Network Operation Mode - Extended | 읽기/쓰기 | `^[0-6]$` | 7개 옵션 | `combo` |
| `PD` | Char Delimiter | 읽기/쓰기 | `^([0-9a-fA-F][0-9a-fA-F])$` | - | `text` |
| `PK` | Private Key | 쓰기전용 | - | - | `textarea` |
| `PO` | Status of Modbus protocol | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `PR` | UART Parity bit | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `PS` | Size Delimiter | 읽기/쓰기 | `^([0-9]|[1-9][0-9]|1[0-9]{2...` | - | `number` |
| `PT` | Time Delimiter | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `PU` | MQTT Publish topic | 읽기/쓰기 | - | - | `text` |
| `QC` | MQTT options - Client ID | 읽기/쓰기 | - | - | `text` |
| `QK` | MQTT Keep-Alive | 읽기/쓰기 | - | - | `number` |
| `QO` | MQTT QoS level | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `QP` | MQTT options - Password | 읽기/쓰기 | - | - | `text` |
| `QU` | MQTT Options - User name | 읽기/쓰기 | - | - | `text` |
| `RC` | Root CA Option | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `RH` | Remote Host IP address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `RI` | TCP Reconnection Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `RP` | Remote Host Port number | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `RT` | Device Reboot | 쓰기전용 | - | - | `text` |
| `SB` | UART Stop bit length | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `SM` | Subnet mask | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `SO` | SSL receive timeout | 읽기/쓰기 | - | - | `number` |
| `SP` | Search ID Code | 읽기/쓰기 | - | - | `text` |
| `SS` | Command mode Switch Code | 읽기/쓰기 | `^(([0-9a-fA-F][0-9a-fA-F]){...` | - | `text` |
| `ST` | Operation status | 읽기전용 | - | - | `text` |
| `SV` | Save Device Setting | 쓰기전용 | - | - | `text` |
| `TE` | Command mode Switch Code Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `U0` | MQTT Subscribe topic 1 | 읽기/쓰기 | - | - | `text` |
| `U1` | MQTT Subscribe topic 2 | 읽기/쓰기 | - | - | `text` |
| `U2` | MQTT Subscribe topic 3 | 읽기/쓰기 | - | - | `text` |
| `VR` | Firmware Version | 읽기전용 | - | - | `text` |

### 명령어 상세

#### BR - UART Baud rate

| 값 | 설명 |
|-----|------|
| `0` | 300 |
| `1` | 600 |
| `2` | 1200 |
| `3` | 1800 |
| `4` | 2400 |
| `5` | 4800 |
| `6` | 9600 |
| `7` | 14400 |
| `8` | 19200 |
| `9` | 28800 |
| `10` | 38400 |
| `11` | 57600 |
| `12` | 115200 |
| `13` | 230400 |
| `14` | 460800 |
| `15` | 921600 |

#### CA - Type and Direction of User I/O pin A

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CB - Type and Direction of User I/O pin B

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CC - Type and Direction of User I/O pin C

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CD - Type and Direction of User I/O pin D

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CE - Client Certificate Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### CP - Connection Password Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### DB - UART Data bit length

| 값 | 설명 |
|-----|------|
| `0` | 7-bit |
| `1` | 8-bit |

#### DG - Serial Debug Message Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable Level 1 |
| `2` | Enable Level 2 |
| `3` | Enable Level 3 |
| `4` | Enable Level 4 |

#### FL - UART Flow Control

| 값 | 설명 |
|-----|------|
| `0` | NONE |
| `1` | XON/XOFF |
| `2` | RTS/CTS |
| `3` | RTS on TX |
| `4` | RTS on TX (invert) |

#### IM - IP address Allocation Mode

| 값 | 설명 |
|-----|------|
| `0` | Static IP |
| `1` | DHCP |

#### KA - TCP Keep-alive Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### OP - Network Operation Mode - Extended

| 값 | 설명 |
|-----|------|
| `0` | TCP Client mode |
| `1` | TCP Server mode |
| `2` | TCP Mixed mode |
| `3` | UDP mode |
| `4` | SSL TCP Client mode |
| `5` | MQTT Client |
| `6` | MQTTS Client |

#### PO - Status of Modbus protocol

| 값 | 설명 |
|-----|------|
| `0` | None |
| `1` | Modbus RTU |
| `2` | Modbus ASCII |

#### PR - UART Parity bit

| 값 | 설명 |
|-----|------|
| `0` | NONE |
| `1` | ODD |
| `2` | EVEN |

#### QO - MQTT QoS level

| 값 | 설명 |
|-----|------|
| `0` | At most once |
| `1` | At least once |
| `2` | Exactly once |

#### RC - Root CA Option

| 값 | 설명 |
|-----|------|
| `0` | None |
| `1` | Optional |
| `2` | Required |

#### SB - UART Stop bit length

| 값 | 설명 |
|-----|------|
| `0` | 1-bit |
| `1` | 2-bit |

#### TE - Command mode Switch Code Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

---

## IP20

**모델 ID**: `IP20`
**카테고리**: SECURITY_ONE_PORT

**최소 펌웨어 버전**: 1.1.8

### 명령어 목록

| 코드 | 이름 | 접근 | 패턴 | 옵션 | UI 위젯 |
|------|------|------|------|------|---------|
| `BR` | UART Baud rate | 읽기/쓰기 | `^([0-9]|1[0-5])$` | 16개 옵션 | `combo` |
| `CA` | Type and Direction of User I/O pin A | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CB` | Type and Direction of User I/O pin B | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CC` | Type and Direction of User I/O pin C | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CD` | Type and Direction of User I/O pin D | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `CE` | Client Certificate Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `CP` | Connection Password Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `DB` | UART Data bit length | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `DG` | Serial Debug Message Enable | 읽기/쓰기 | `^[0-4]$` | 5개 옵션 | `combo` |
| `DS` | DNS Server address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `FL` | UART Flow Control | 읽기/쓰기 | `^[0-4]$` | 5개 옵션 | `combo` |
| `FR` | Device Factory Reset | 쓰기전용 | - | - | `text` |
| `GW` | Gateway address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `IM` | IP address Allocation Mode | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `IT` | Inactivity Timer Value | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `KA` | TCP Keep-alive Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `KE` | TCP Keep-alive Retry Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `KI` | TCP Keep-alive Initial Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `LC` | Client Certificate | 쓰기전용 | - | - | `textarea` |
| `LI` | Local IP address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `LP` | Local port number | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `MC` | MAC address | 읽기전용 | `^([0-9a-fA-F]{2}:){5}([0-9a...` | - | `mac` |
| `MN` | Product Name | 읽기전용 | - | - | `text` |
| `NP` | Connection Password | 읽기/쓰기 | - | - | `text` |
| `OC` | Root CA | 쓰기전용 | - | - | `textarea` |
| `OP` | Network Operation Mode - Extended | 읽기/쓰기 | `^[0-6]$` | 7개 옵션 | `combo` |
| `PD` | Char Delimiter | 읽기/쓰기 | `^([0-9a-fA-F][0-9a-fA-F])$` | - | `text` |
| `PK` | Private Key | 쓰기전용 | - | - | `textarea` |
| `PO` | Status of Modbus protocol | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `PR` | UART Parity bit | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `PS` | Size Delimiter | 읽기/쓰기 | `^([0-9]|[1-9][0-9]|1[0-9]{2...` | - | `number` |
| `PT` | Time Delimiter | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `PU` | MQTT Publish topic | 읽기/쓰기 | - | - | `text` |
| `QC` | MQTT options - Client ID | 읽기/쓰기 | - | - | `text` |
| `QK` | MQTT Keep-Alive | 읽기/쓰기 | - | - | `number` |
| `QO` | MQTT QoS level | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `QP` | MQTT options - Password | 읽기/쓰기 | - | - | `text` |
| `QU` | MQTT Options - User name | 읽기/쓰기 | - | - | `text` |
| `RC` | Root CA Option | 읽기/쓰기 | `^[0-2]$` | 3개 옵션 | `combo` |
| `RH` | Remote Host IP address | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `RI` | TCP Reconnection Interval | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `RP` | Remote Host Port number | 읽기/쓰기 | `^([0-9]|[1-9][0-9]{1,3}|[1-...` | - | `number` |
| `RT` | Device Reboot | 쓰기전용 | - | - | `text` |
| `SB` | UART Stop bit length | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `combo` |
| `SM` | Subnet mask | 읽기/쓰기 | `^(([0-9]|[1-9][0-9]|1[0-9]{...` | - | `ip` |
| `SO` | SSL receive timeout | 읽기/쓰기 | - | - | `number` |
| `SP` | Search ID Code | 읽기/쓰기 | - | - | `text` |
| `SS` | Command mode Switch Code | 읽기/쓰기 | `^(([0-9a-fA-F][0-9a-fA-F]){...` | - | `text` |
| `ST` | Operation status | 읽기전용 | - | - | `text` |
| `SV` | Save Device Setting | 쓰기전용 | - | - | `text` |
| `TE` | Command mode Switch Code Enable | 읽기/쓰기 | `^[0-1]$` | 2개 옵션 | `checkbox` |
| `U0` | MQTT Subscribe topic 1 | 읽기/쓰기 | - | - | `text` |
| `U1` | MQTT Subscribe topic 2 | 읽기/쓰기 | - | - | `text` |
| `U2` | MQTT Subscribe topic 3 | 읽기/쓰기 | - | - | `text` |
| `VR` | Firmware Version | 읽기전용 | - | - | `text` |

### 명령어 상세

#### BR - UART Baud rate

| 값 | 설명 |
|-----|------|
| `0` | 300 |
| `1` | 600 |
| `2` | 1200 |
| `3` | 1800 |
| `4` | 2400 |
| `5` | 4800 |
| `6` | 9600 |
| `7` | 14400 |
| `8` | 19200 |
| `9` | 28800 |
| `10` | 38400 |
| `11` | 57600 |
| `12` | 115200 |
| `13` | 230400 |
| `14` | 460800 |
| `15` | 921600 |

#### CA - Type and Direction of User I/O pin A

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CB - Type and Direction of User I/O pin B

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CC - Type and Direction of User I/O pin C

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CD - Type and Direction of User I/O pin D

| 값 | 설명 |
|-----|------|
| `0` | Digital Input |
| `1` | Digital Output |
| `2` | Analog Input |

#### CE - Client Certificate Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### CP - Connection Password Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### DB - UART Data bit length

| 값 | 설명 |
|-----|------|
| `0` | 7-bit |
| `1` | 8-bit |

#### DG - Serial Debug Message Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable Level 1 |
| `2` | Enable Level 2 |
| `3` | Enable Level 3 |
| `4` | Enable Level 4 |

#### FL - UART Flow Control

| 값 | 설명 |
|-----|------|
| `0` | NONE |
| `1` | XON/XOFF |
| `2` | RTS/CTS |
| `3` | RTS on TX |
| `4` | RTS on TX (invert) |

#### IM - IP address Allocation Mode

| 값 | 설명 |
|-----|------|
| `0` | Static IP |
| `1` | DHCP |

#### KA - TCP Keep-alive Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

#### OP - Network Operation Mode - Extended

| 값 | 설명 |
|-----|------|
| `0` | TCP Client mode |
| `1` | TCP Server mode |
| `2` | TCP Mixed mode |
| `3` | UDP mode |
| `4` | SSL TCP Client mode |
| `5` | MQTT Client |
| `6` | MQTTS Client |

#### PO - Status of Modbus protocol

| 값 | 설명 |
|-----|------|
| `0` | None |
| `1` | Modbus RTU |
| `2` | Modbus ASCII |

#### PR - UART Parity bit

| 값 | 설명 |
|-----|------|
| `0` | NONE |
| `1` | ODD |
| `2` | EVEN |

#### QO - MQTT QoS level

| 값 | 설명 |
|-----|------|
| `0` | At most once |
| `1` | At least once |
| `2` | Exactly once |

#### RC - Root CA Option

| 값 | 설명 |
|-----|------|
| `0` | None |
| `1` | Optional |
| `2` | Required |

#### SB - UART Stop bit length

| 값 | 설명 |
|-----|------|
| `0` | 1-bit |
| `1` | 2-bit |

#### TE - Command mode Switch Code Enable

| 값 | 설명 |
|-----|------|
| `0` | Disable |
| `1` | Enable |

---

## 명령어 세트

### common

**명령어 수**: 39

### wiz75x_extended

**상속**: `common`

**명령어 수**: 4

### security_base

**상속**: `common`

**명령어 수**: 17
