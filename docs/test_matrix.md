# Initial test matrix

Prerequisite: start target and connect host. Hardware qualification is limited to cases with defined references.

| ID | Command | Procedure / expected result | Cleanup |
| --- | --- | --- | --- |
| TC-01 Ping test | TEST_PING -> PING_TEST | Select 1 or ping; PASS requires target PASS and exact PONG - target received command response. Unexpected response is FAIL; communication error aborts the test. Startup PING is not counted. | None |
| TC-02 Selec EM4M AC Energy Meter | TEST_SELEC_EM4M -> SELEC_EM4M_TEST | Select 2; choose default `/dev/ttyCH9344USB4 @ 9600 8N1, slave ID 1` or enter port, baud rate, and slave ID. PASS requires all configured Modbus RTU FC04 reads to return valid responses with valid CRC. Confirmed voltage values must be within tolerance of the stored references: L1 228.930 V, L2 229.090 V, L3 229.040 V, Avg/Total 229.020 V. PC output shows the parameter table. Target full TX/RX log is saved under `/home/root/TC_02_Selec_EM4M_AC_Energy_Meter_<date>.txt`. Current, power, reactive power, frequency, and energy values are logged but remain unconfirmed until checked against known reference inputs. | None |
| TC-03 EDC 2150 DC Energy Meter | TEST_EDC2150 -> EDC2150_TEST | Select 3; choose default `/dev/ttyCH9344USB1 @ 9600 8N1, slave ID 2` or enter port, baud rate, and slave ID. PASS requires all available configured Modbus RTU FC03 reads to return valid responses with valid CRC. PC output shows the parameter table. Target full TX/RX log is saved under `/home/root/TC_03_EDC2150_DC_Energy_Meter_<date>.txt`. Reactive power and frequency are skipped as unavailable because their YAML start register is 0. | None |
| TC-04 CAN Controller Node Start all | TEST_CAN_CONTROLLER_START_ALL -> CAN_CONTROLLER_START_ALL_TEST | Select 4; sends broadcast `start_all` on CAN using target config defaults. PASS means the command frame was encoded and sent without exception. PC output shows action/channel/bitrate/log path. | None |
| TC-04 CAN Controller Node Stop All | TEST_CAN_CONTROLLER_STOP_ALL -> CAN_CONTROLLER_STOP_ALL_TEST | Select 5; sends broadcast `stop_all` on CAN using target config defaults. PASS means the command frame was encoded and sent without exception. | None |
| TC-04 CAN Controller Node Set All | TEST_CAN_CONTROLLER_SET_ALL -> CAN_CONTROLLER_SET_ALL_TEST | Select 6; enter group, voltage, and current or press Enter for defaults. Sends broadcast `set_all`. PASS means the command frame was encoded and sent without exception. | None |
| TC-04 CAN Controller Node Start | TEST_CAN_CONTROLLER_START -> CAN_CONTROLLER_START_TEST | Select 7; enter module address, voltage, and current or press Enter for defaults. Sends per-module `start`. PASS means the command frame was encoded and sent without exception. | None |
| TC-04 CAN Controller Node Stop | TEST_CAN_CONTROLLER_STOP -> CAN_CONTROLLER_STOP_TEST | Select 8; enter module address or press Enter for default. Sends per-module `stop`. PASS means the command frame was encoded and sent without exception. | None |
| TC-05 RFID Verification | TEST_RFID -> RFID_TEST | Select 9; choose default `/dev/ttyUSB0 @ 115200 8N1` or enter port and baud rate. Target sends `02 00 02 34 31 03 06` and reads repeated responses. PASS requires a valid response with operation status `0x59` and a 4-byte card serial number. PC output shows only the detected card serial number and target log path. Status `0x4E` responses are stored only in the target log. Target full TX/RX log is saved under `/home/root/TC_05_RFID_Verification_<date>.txt`. | None |
| COM-02 | ECHO | Enter echo hello; target returns PASS with hello | None |
| COM-03 | Unknown | Enter UNKNOWN; target returns NOT_IMPLEMENTED and remains available | None |
| COM-04 | STOP_QTP | Enter q; receive PASS, host and target exit | Restart target |
| COM-05 | Reconnect | Disconnect client without STOP_QTP, connect again; PING succeeds | STOP_QTP |

Host logs command execution and final results. Add hardware cases only once prerequisites, mappings, pass/fail criteria, and cleanup are defined.
