# Amararaja Integrated QTP

Python TCP host/target project based on the supplied socket examples and project skeleton. Uses the BOSCH reference's `[QTP]`, `[HOST]`, and `[TARGET]` console prefixes. Python 3.8+. TC-02 live Selec EM4M testing requires `pyserial` on the target.

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
| `echo hello` | Target returns `hello` |
| `q` | Send STOP_QTP, await acknowledgment, exit host and target |
| `exit` or `0` | Same as q |
| Other text | Send as uppercase command; unknown commands return NOT_IMPLEMENTED |

The target needs no keyboard input. STOP_QTP stops the target Python server, not the board/OS. Restart the target script before a new session. Ctrl+C/EOF at the host prompt also requests STOP_QTP. A network failure or an interruption during a request does not confirm remote shutdown. An ordinary client disconnect leaves the target listening for reconnection.

TC-02 copies the standalone Selec EM4M Modbus code into target `selec_EM4M.py` and runs the live per-register Modbus RTU reads from the QTP menu. The test passes when all configured parameters return valid responses with valid CRC and the confirmed voltage values match these references within tolerance: L1 228.930 V, L2 229.090 V, L3 229.040 V, Avg/Total 229.020 V. Current, power, reactive power, frequency, and energy values are logged as valid responses but remain unconfirmed until checked against known reference inputs. Add future visible tests to the host `TESTS` table, translate them in `command_handler.py`, and register target-side implementations in dispatcher `COMMANDS`. Current commands run synchronously and have a 10-second host response deadline; long-running tests need cancellation and timeout design before integration.

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
