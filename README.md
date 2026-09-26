# Amararaja Integrated QTP

Python TCP host/target project based on the supplied socket examples and project skeleton. Uses the BOSCH reference's `[QTP]`, `[HOST]`, and `[TARGET]` console prefixes. Python 3.8+. TC-02 and TC-03 live Modbus meter testing require `pyserial` on the target.

## Run

The Host and Target folders are self-contained, each including `qtp_protocol.py`. Copy the contents of `Amararaja_Integrated_QTP_Target` to `/root/qtp_testing` on the target. Start the target first:

```sh
cd /root/qtp_testing
python3.12 main.py
```

On the PC:

```powershell
cd Amararaja-Integrated-QTP\Amararaja_Integrated_QTP_Host
python main.py 192.168.11.69
```

Use the target's actual IP. Your examples contain both `192.168.11.69` and `192.169.11.69`; this project defaults to the former, from your base code. Python needs the script name before the IP; `python 192.168.11.69` alone is not valid.

The target listens on TCP port 5000. To change it, pass `--port 6000` to both programs. Target `--host <IP>` restricts the bind address. Host `--report-dir <folder>` changes the log directory. Ensure PC-to-target routing and TCP port access. This is a trusted-lab protocol with no authentication or encryption.

## Commands

The host automatically sends `PING` after connection as a startup transport check; the target prints the received command and returns PONG. The interactive TC-01 menu command follows the BOSCH reference style: host command `TEST_PING` is translated by `command_handler.py` to target command `PING_TEST`.

| PC input (then Enter) | Behavior |
| --- | --- |
| `1` or `ping` | Run TC-01 Ping test over TCP and record the result |
| `2` | Run TC-02 Selec EM4M AC Energy Meter live Modbus read test and record the result |
| `3` | Run TC-03 EDC 2150 DC Energy Meter live Modbus read test and record the result |
| `4` | Run TC-04 Read IMD 1 |
| `5` | Run TC-04 Read IMD 2 |
| `6` | Run TC-05 CAN Controller Node Start all |
| `7` | Run TC-05 CAN Controller Node Stop All |
| `8` | Run TC-05 CAN Controller Node Set All |
| `9` | Run TC-05 CAN Controller Node Start |
| `10` | Run TC-05 CAN Controller Node Stop |
| `11` | Run TC-06 RFID Verification |
| `12` | Run TC-07 PT1000/Thermistor-10k Temperature Sensor |
| `13` | Run TC-08 4G network verification |
| `14` | Run TC-12 Relay Control All OFF |
| `15` | Run TC-12 Relay Control DC1 ON |
| `16` | Run TC-12 Relay Control DC2 ON |
| `17` | Run TC-12 Relay Control AC ON |
| `18` | Run TC-12 Relay Control MERGER ON |
| `19` | Flash Phytec_MSP_DC.bin binary |
| `20` | Flash Coil_Control.bin binary |
| `echo hello` | Target returns `hello` |
| `q` | Send STOP_QTP, await acknowledgment, exit host and target |
| `exit` or `0` | Same as q |
| Other text | Send as uppercase command; unknown commands return NOT_IMPLEMENTED |

The target needs no keyboard input. STOP_QTP stops the target Python server, not the board/OS. Restart the target script before a new session. Ctrl+C/EOF at the host prompt also requests STOP_QTP. A network failure or an interruption during a request does not confirm remote shutdown. An ordinary client disconnect leaves the target listening for reconnection.

TC-02 copies the standalone Selec EM4M Modbus code into target `selec_EM4M.py` and runs the live per-register Modbus RTU reads from the QTP menu. Before communication starts, the host asks whether to use `/dev/ttyCH9344USB4 @ 9600 8N1, slave ID 1` or enter a custom port, baud rate, and slave ID. The PC result displays the parameter table with address, raw hex, raw decimal, scaled value, and verified status. The target saves the full TX/RX debug log at `/home/root/TC_02_Selec_EM4M_AC_Energy_Meter_<date>.txt`. The test passes when all configured parameters return valid responses with valid CRC and the confirmed voltage values match these references within tolerance: L1 228.930 V, L2 229.090 V, L3 229.040 V, Avg/Total 229.020 V. Current, power, reactive power, frequency, and energy values are logged as valid responses but remain unconfirmed until checked against known reference inputs.

TC-03 copies the standalone EDC2150 DC Energy Meter code into target `edc2150.py` and runs live per-parameter Modbus RTU FC03 reads. Before communication starts, the host asks whether to use `/dev/ttyCH9344USB1 @ 9600 8N1, slave ID 2` or enter a custom port, baud rate, and slave ID. The PC result displays the EDC2150 parameter table with start address, raw float, scaled value, and availability. The target saves the full TX/RX debug log at `/home/root/TC_03_EDC2150_DC_Energy_Meter_<date>.txt`. The test passes when all available configured parameters return valid responses with valid CRC; reactive power and frequency are marked not available because their YAML start register is 0.

TC-04 reads both Bender IMD devices through target `imd_read.py`. IMD1 uses default `/dev/ttyCH9344USB0 @ 9600 8N1, slave ID 5` and IMD2 uses default `/dev/ttyCH9344USB2 @ 9600 8N1, slave ID 4`. The host asks whether to use those defaults or enter a custom port, baud rate, parity, and slave ID. The PC output shows the decoded measurement table before the result status. Target full TX/RX logs are saved at `/home/root/TC_04_Read_IMD_1_<date>.txt` and `/home/root/TC_04_Read_IMD_2_<date>.txt`.

TC-05 copies the CAN controller support into target `can_setup.py`, `can_controller_node.py`, `can_controller_qtp.py`, and `tonhe_can_messages_6modules.csv`. The QTP entries ask whether to use default SocketCAN settings `mcu_mcan0 @ 125000 bit/s` or enter a custom channel and bitrate, then send controller commands using target `config.py` defaults for the remaining values, group `1`, voltage `500.0`, current `41.0`, module address `1`. Each one-shot QTP CAN action configures the CAN interface and sends the timing command `C_M_3` once before the selected command. Menu 6 starts a background keep-alive that sends `C_M_3` every 5 seconds, and menu 7 stops that background keep-alive. The copied controller shell commands remain available in `can_controller_node.py` for future use, including `disable_gun`, `dual_gun`, `exit`, `gun`, `help`, `only_rx`, `only_tx`, `quiet`, `set_address`, `set_address_mode`, `set_input_mode`, `show_both`, `status`, `stop`, and `verbose`. Target TX/RX command logs are saved under `/home/root/TC_05_CAN_Controller_..._<date>.txt`.

TC-06 runs RFID verification inside target `tests.py`. Before communication starts, the host asks whether to use `/dev/ttyUSB0 @ 115200 8N1` or enter a custom port and baud rate. The target sends `02 00 02 34 31 03 06`, reads repeated responses, and passes when a response contains operation status `0x59` with a 4-byte card serial number. Status `0x4E` means no card serial number returned. The PC result displays only the detected card serial number and target log path; no-card responses are kept in the target log only. The target saves the full TX/RX debug log at `/home/root/TC_06_RFID_Verification_<date>.txt`.

TC-07 runs PT1000/Thermistor-10k temperature verification through target `phyverso_temperature.py`. The target runs `phyverso_cli /dev/ttyS6 /root/config.json`, sends `T`, parses either `Gun... Temperature` lines or `Connector/get_temp()` debug lines, and shows a compact temperature table on the PC. The test passes when at least one valid temperature above the no-sensor value is detected. The full CLI output is saved under `/home/root/TC_07_PT1000_Thermistor_10k_Temperature_Sensor_<date>.txt`.

TC-08 runs 4G QMI network verification through target `network_4g.py`. The target configures `/etc/qmi-network.conf` with APN `airtelgprs.com`, brings `wwu1u1i4` down/up in raw-IP mode, starts/stops/starts `qmi-network /dev/cdc-wdm0`, requests an IPv4 lease with `udhcpc`, checks `ifconfig wwu1u1i4`, and pings `google.com` using the 4G interface. The PC output shows the step table and target log path. Full command output is saved under `/home/root/TC_08_4G_Network_Verification_<date>.txt`.

TC-12 runs MCU relay control through target `relay_control.py`. Relay actions 16-20 only send one UART command at `/dev/ttyS6 @ 115200 8N1` (`0` = all, `1` = DC1, `2` = DC2, `3` = AC, `4` = MERGER) and check the MCU response text. Flashing is handled separately by menu 21 and 22: menu 21 flashes `/usr/lib/firmware/Phytec_MSP_DC.bin`, and menu 22 flashes `Amararaja_Integrated_QTP_Target/MCU_binary/Coil_Control.bin`. The helper does not use `phyVERSO_MCU_debug`.

Add future visible tests to the host `TESTS` table, translate them in `command_handler.py`, and register target-side implementations in dispatcher `COMMANDS`. Current commands run synchronously and have a 10-second host response deadline; long-running tests need cancellation and timeout design before integration.

## Logs

Host `test_log/` contains timestamped `test_log_<timestamp>.txt` and `test_summary_<timestamp>.txt`. Detailed logs include connection events, commands, target output, status, and errors. Reports use the BOSCH reference format: TEST #, Command, Started, [EXECUTING], [RESULT], Result, Details, Working as Expected, Completed, and TEST EXECUTION SUMMARY with statistics and detailed results. Only explicitly selected test runs count in the summary; startup PING, ECHO, and STOP_QTP remain in the detailed log. TC-01 requires PASS and the expected PONG message, then asks the operator `Is this test working as expected? (y/n):`. Answering `n` records the test as FAIL. This is a TCP application ping, not an ICMP/network ping or hardware qualification test.

## Layout

The supplied PROJECT_SKELETON.md is retained. Host modules handle the CLI, menu, command logs, and TCP client. Target modules handle server lifecycle, dispatch, and tests. The root `qtp_protocol.py` is the canonical protocol source. Identical copies are bundled in each application folder for standalone deployment; when changing the protocol, update all three copies. Verification checks that they match. `verification/test_tcp.py` contains automated transport checks.

```sh
python -m unittest discover -s verification -v
```

See `docs/tcp_tlv_data_frame.md`, `docs/test_matrix.md`, and `docs/hardware_mapping.md`.

If connecting fails, check the IP, start the target first, and check port/firewall access. A bind error usually means the port is already in use. The original plain-text socket examples cannot directly communicate with this framed QTP implementation; use the new host and target together.

The host `test_logger.py` maintains the reference-style detailed test log and summary.

