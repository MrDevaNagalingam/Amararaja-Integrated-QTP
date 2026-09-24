# Initial test matrix

Prerequisite: start target and connect host. Hardware qualification is limited to cases with defined references.

| ID | Command | Procedure / expected result | Cleanup |
| --- | --- | --- | --- |
| TC-01 Ping test | TEST_PING -> PING_TEST | Select 1 or ping; PASS requires target PASS and exact PONG - target received command response. Unexpected response is FAIL; communication error aborts the test. Startup PING is not counted. | None |
| TC-02 Selec EM4M AC Energy Meter | TEST_SELEC_EM4M -> SELEC_EM4M_TEST | Select 2; PASS requires all configured Modbus RTU FC04 reads to return valid responses with valid CRC. Confirmed voltage values must be within tolerance of the stored references: L1 228.930 V, L2 229.090 V, L3 229.040 V, Avg/Total 229.020 V. Current, power, reactive power, frequency, and energy values are logged but remain unconfirmed until checked against known reference inputs. | None |
| COM-02 | ECHO | Enter echo hello; target returns PASS with hello | None |
| COM-03 | Unknown | Enter UNKNOWN; target returns NOT_IMPLEMENTED and remains available | None |
| COM-04 | STOP_QTP | Enter q; receive PASS, host and target exit | Restart target |
| COM-05 | Reconnect | Disconnect client without STOP_QTP, connect again; PING succeeds | STOP_QTP |

Host logs command execution and final results. Add hardware cases only once prerequisites, mappings, pass/fail criteria, and cleanup are defined.
