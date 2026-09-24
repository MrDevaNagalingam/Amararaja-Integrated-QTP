# Amararaja Integrated QTP — Project Skeleton

## 1. Project Structure

```text
Amararaja-Integrated-QTP/
|
|-- README.md
|-- PROJECT_SKELETON.md
|
|-- docs/
|   |-- hardware_mapping.md
|   |-- test_matrix.md
|   '-- tcp_tlv_data_frame.md
|
|-- Amararaja_Integrated_QTP_Host/
|   |
|   |-- main.py
|   |-- interactive_menu.py
|   |-- command_handler.py
|   |-- tcp_handler.py
|   |-- config.py
|   |-- requirements.txt
|   |
|   |-- test_log/
|   |   |-- test_log_<timestamp>.txt
|   |   '-- test_summary_<timestamp>.txt
|   |
|   '-- __pycache__/
|
'-- Amararaja_Integrated_QTP_Target/
    |
    |-- main.py
    |-- config.py
    |-- tcp_server.py
    |-- dispatcher.py
    |-- gpio.py
    |-- tests.py
    |-- requirements.txt
    |
    '-- __pycache__/
```

---

## 2. Top-Level Files

### `README.md`

Main project documentation.

It contains:

* Amararaja Integrated QTP overview
* Host and target architecture
* Software requirements
* Setup instructions
* Ethernet configuration
* TCP connection details
* Test execution procedure
* Available QTP test cases
* Log information
* Troubleshooting information

---

### `PROJECT_SKELETON.md`

Defines the complete Amararaja Integrated QTP directory structure and explains the responsibility of each file and directory.

---

### `docs/`

Contains supporting documentation for the QTP framework.

```text
docs/
|-- hardware_mapping.md
|-- test_matrix.md
'-- tcp_tlv_data_frame.md
```

---

## 3. Documentation Files

### `docs/hardware_mapping.md`

Contains hardware-related information used by the QTP tests.

Examples:

* GPIO mappings
* LED mappings
* Ethernet interface
* CAN interface
* UART interfaces used by individual hardware tests
* USB interfaces
* SD card interfaces
* I2C devices
* SPI devices
* PCIe interfaces
* Board connectors
* Peripheral mappings

Only hardware information required by the Amararaja QTP test cases should be maintained here.

---

### `docs/test_matrix.md`

Contains the complete QTP test-case definition.

Each test case may include:

```text
Test Case ID
Test Name
Command Name
Purpose
Prerequisites
Test Procedure
Expected Result
PASS Criteria
FAIL Criteria
Cleanup
Log Information
```

Example structure:

```text
TC-01
    |
    +-- Test Name
    +-- QTP Command
    +-- Prerequisites
    +-- Test Procedure
    +-- Expected Result
    +-- PASS/FAIL Criteria
    '-- Cleanup
```

---

### `docs/tcp_tlv_data_frame.md`

Defines the communication protocol used between the Amararaja Integrated QTP Host and Target.

The protocol uses:

```text
Ethernet
   |
   v
TCP/IP
   |
   v
QTP Fixed Header
   |
   v
TLV Payload
```

This document defines:

* TCP connection
* QTP header format
* MAGIC value
* Protocol version
* Payload length
* TLV format
* TLV types
* Request ID
* Command format
* Parameter format
* Stream output
* Final result
* Frame validation
* TCP receive-buffer handling
* Request/response flow
* Error handling

The detailed protocol is documented separately in `tcp_tlv_data_frame.md`.

---

# 4. Host Application

```text
Amararaja_Integrated_QTP_Host/
|
|-- main.py
|-- interactive_menu.py
|-- command_handler.py
|-- tcp_handler.py
|-- config.py
|-- requirements.txt
|
|-- test_log/
|   |-- test_log_<timestamp>.txt
|   '-- test_summary_<timestamp>.txt
|
'-- __pycache__/
```

The Host application runs on the PC and provides the operator interface for executing QTP tests.

The Host communicates with the Amararaja target over Ethernet using TCP/IP.

---

## `main.py`

Host-side application entry point.

Main responsibilities:

```text
Start Host application
        |
        v
Load configuration
        |
        v
Initialize TCP client
        |
        v
Connect to Target
        |
        v
Start interactive QTP menu
        |
        v
Execute selected tests
```

Typical responsibilities:

* Initialize the application
* Load host configuration
* Create TCP connection
* Verify target connectivity
* Start the interactive menu
* Handle clean application shutdown

---

## `interactive_menu.py`

Provides the user-facing QTP test menu.

Responsibilities:

* Display available test cases
* Accept operator selections
* Validate operator input
* Trigger the corresponding command
* Display test execution status
* Display PASS/FAIL results
* Allow repeated test execution
* Allow application exit

Example flow:

```text
QTP Main Menu

1. TC-01
2. TC-02
3. TC-03
4. TC-04
...
0. Exit
```

The actual test names and test IDs shall be defined according to the Amararaja QTP test matrix.

---

## `command_handler.py`

Acts as the application layer between the interactive menu and TCP communication layer.

Responsibilities:

* Map menu selections to QTP command names
* Generate command requests
* Provide optional command parameters
* Call the TCP communication layer
* Receive streamed output
* Receive final results
* Display results
* Store test results
* Generate test summaries

Logical flow:

```text
Interactive Menu
       |
       v
Command Handler
       |
       v
TCP Handler
       |
       v
Target
```

---

## `tcp_handler.py`

Provides the Host-side TCP/IP transport and QTP protocol handling.

This replaces the UART communication module used by the previous QTP implementation.

Responsibilities:

* Create TCP client socket
* Connect to the configured target IP address
* Connect to the configured QTP TCP port
* Maintain the TCP connection
* Build QTP frames
* Encode TLV entries
* Send QTP frames
* Maintain a persistent TCP receive buffer
* Reconstruct complete frames from the TCP byte stream
* Decode QTP headers
* Decode TLV entries
* Match responses using the request ID
* Handle streamed target output
* Receive final test results
* Detect connection loss
* Handle TCP timeouts
* Close sockets cleanly

Logical communication:

```text
Host Application
      |
      v
tcp_handler.py
      |
      | Ethernet / TCP-IP
      |
      v
Target TCP Server
```

---

## `config.py`

Contains Host-side configuration.

Typical configuration items:

```text
TARGET_IP
QTP_TCP_PORT
CONNECT_TIMEOUT
RESPONSE_TIMEOUT
RECV_BUFFER_SIZE
MAX_PAYLOAD_SIZE
PROTOCOL_VERSION
MAGIC
LOG_DIRECTORY
```

Network-dependent configuration should be maintained here instead of being hardcoded throughout the application.

---

## `requirements.txt`

Contains Host-side Python dependencies.

Example:

```text
Python package dependencies required by the QTP Host.
```

Only packages actually required by the implementation should be included.

---

# 5. Host Test Logs

```text
test_log/
|-- test_log_<timestamp>.txt
'-- test_summary_<timestamp>.txt
```

---

## `test_log_<timestamp>.txt`

Stores full detailed runtime information for the QTP session.

May contain:

* Connection status
* Test start time
* Test end time
* Command name
* Request ID
* Stream output
* Target response
* PASS status
* FAIL status
* ERROR status
* Timeout information

---

## `test_summary_<timestamp>.txt`

Stores the final summary of tests executed during the session.

Example:

```text
Amararaja Integrated QTP Test Summary

TC-01    PASS
TC-02    PASS
TC-03    FAIL
TC-04    PASS

Total Tests : 4
Passed      : 3
Failed      : 1
```

---

# 6. Target Application

```text
Amararaja_Integrated_QTP_Target/
|
|-- main.py
|-- config.py
|-- tcp_server.py
|-- dispatcher.py
|-- gpio.py
|-- tests.py
|-- requirements.txt
|
'-- __pycache__/
```

The Target application runs on the Amararaja target board.

It receives QTP commands from the Host over Ethernet/TCP, executes the requested hardware test, and returns the result.

---

## `main.py`

Target-side application entry point.

Typical execution flow:

```text
Start Target Application
        |
        v
Load Configuration
        |
        v
Initialize TCP Server
        |
        v
Listen for Host Connection
        |
        v
Receive QTP Frame
        |
        v
Dispatcher
        |
        v
Execute Test
        |
        v
Return Result
```

Responsibilities:

* Initialize the target application
* Load configuration
* Start the TCP server
* Accept Host connections
* Pass received requests to the dispatcher
* Handle application shutdown

---

## `config.py`

Contains Target-side configuration.

Typical configuration may include:

```text
QTP_BIND_ADDRESS
QTP_TCP_PORT
PROTOCOL_VERSION
MAGIC
MAX_PAYLOAD_SIZE
SOCKET_TIMEOUT

GPIO paths
Device paths
Network interfaces
Storage paths
Peripheral names
Test timings
Test thresholds
```

Board-specific configuration should be centralized in this file wherever practical.

---

## `tcp_server.py`

Provides the Target-side TCP server and QTP frame transport handling.

Responsibilities:

* Create TCP server socket
* Bind to the configured TCP port
* Listen for Host connections
* Accept Host connections
* Maintain client connection
* Receive TCP byte streams
* Maintain a persistent receive buffer
* Reconstruct complete QTP frames
* Validate QTP fixed headers
* Decode TLV payloads
* Send stream-output frames
* Send final-result frames
* Detect disconnected clients
* Handle socket errors
* Handle connection timeouts
* Allow Host reconnection

Logical flow:

```text
Windows QTP Host
       |
       | TCP/IP
       v
tcp_server.py
       |
       v
dispatcher.py
       |
       v
tests.py
```

---

## `dispatcher.py`

Provides the Target-side command-dispatch layer.

Responsibilities:

* Validate incoming commands
* Validate request IDs
* Validate optional parameters
* Identify the requested test
* Map commands to test functions
* Execute the corresponding test
* Handle unsupported commands
* Handle execution exceptions
* Send streamed output when required
* Return the final result

Example logical mapping:

```text
COMMAND
   |
   +-- TEST_01 ------------> test_01()
   |
   +-- TEST_02 ------------> test_02()
   |
   +-- TEST_03 ------------> test_03()
   |
   '-- UNKNOWN ------------> NOT_IMPLEMENTED
```

The actual command names shall be defined according to the Amararaja QTP test matrix.

---

## `gpio.py`

Provides reusable GPIO operations required by hardware tests.

Typical responsibilities:

* GPIO initialization
* GPIO direction configuration
* GPIO read
* GPIO write
* GPIO toggle
* GPIO cleanup
* GPIO error handling

Hardware-specific GPIO mappings should remain in configuration or hardware-mapping documentation rather than being scattered throughout the test code.

---

## `tests.py`

Contains the actual Amararaja hardware test implementations.

Each test should normally:

```text
Receive Parameters
       |
       v
Check Prerequisites
       |
       v
Execute Hardware Test
       |
       v
Evaluate Result
       |
       v
Perform Cleanup
       |
       v
Return Structured Result
```

Typical result:

```json
{
    "test": "TEST_NAME",
    "status": "PASS",
    "message": "Test completed successfully"
}
```

Failure example:

```json
{
    "test": "TEST_NAME",
    "status": "FAIL",
    "message": "Test failed"
}
```

Execution-error example:

```json
{
    "test": "TEST_NAME",
    "status": "ERROR",
    "message": "Test execution error"
}
```

The actual hardware tests shall be added according to the Amararaja Integrated QTP requirements.

---

## `requirements.txt`

Contains Target-side Python dependencies.

Only packages required by the Target implementation should be included.

---

# 7. Generated and Runtime Content

## `__pycache__/`

Python bytecode-cache directory automatically generated during execution.

It is not part of the functional QTP source code.

---

## `test_log/`

Host-generated runtime log directory.

The Host shall maintain the main QTP execution logs and final test summaries.

---

# 8. High-Level Software Architecture

```text
                 AMARARAJA INTEGRATED QTP


+------------------------------------------------------+
|                  WINDOWS/LINUX QTP HOST              |
|                                                      |
|  +---------------------+                             |
|  | interactive_menu.py |                             |
|  +----------+----------+                             |
|             |                                        |
|             v                                        |
|  +---------------------+                             |
|  | command_handler.py  |                             |
|  +----------+----------+                             |
|             |                                        |
|             v                                        |
|  +---------------------+                             |
|  |   tcp_handler.py    |                             |
|  +----------+----------+                             |
+-------------|----------------------------------------+
              |
              | Ethernet
              | TCP/IP
              |
+-------------|----------------------------------------+
|             v                                        |
|  +---------------------+                             |
|  |    tcp_server.py    |                             |
|  +----------+----------+                             |
|             |                                        |
|             v                                        |
|  +---------------------+                             |
|  |    dispatcher.py    |                             |
|  +----------+----------+                             |
|             |                                        |
|             v                                        |
|  +---------------------+                             |
|  |      tests.py       |                             |
|  +----------+----------+                             |
|             |                                        |
|             v                                        |
|  +---------------------+                             |
|  | Target Hardware     |                             |
|  +---------------------+                             |
|                                                      |
|              AMARARAJA TARGET                        |
+------------------------------------------------------+
```

---

# 9. Communication Architecture

The Amararaja Integrated QTP does not use UART as the main QTP console transport.

The Host and Target communicate using:

```text
Ethernet
   |
   v
TCP/IP
   |
   v
QTP Protocol
   |
   v
TLV Commands / Responses
```

The logical application flow is:

```text
HOST

Interactive Menu
      |
      v
Command Handler
      |
      v
TCP Handler
      |
      | QTP Frame
      | over TCP/IP
      v

TARGET

TCP Server
      |
      v
Dispatcher
      |
      v
Test Function
      |
      v
Hardware
```

The detailed TCP/QTP/TLV frame definition is maintained separately in:

```text
docs/tcp_tlv_data_frame.md
```

---

# 10. Final Project Skeleton

```text
Amararaja-Integrated-QTP/
|
|-- README.md
|-- PROJECT_SKELETON.md
|
|-- docs/
|   |-- hardware_mapping.md
|   |-- test_matrix.md
|   '-- tcp_tlv_data_frame.md
|
|-- Amararaja_Integrated_QTP_Host/
|   |
|   |-- main.py
|   |-- interactive_menu.py
|   |-- command_handler.py
|   |-- tcp_handler.py
|   |-- config.py
|   |-- requirements.txt
|   |
|   |-- test_log/
|   |   |-- test_log_<timestamp>.txt
|   |   '-- test_summary_<timestamp>.txt
|   |
|   '-- __pycache__/
|
'-- Amararaja_Integrated_QTP_Target/
    |
    |-- main.py
    |-- config.py
    |-- tcp_server.py
    |-- dispatcher.py
    |-- gpio.py
    |-- tests.py
    |-- requirements.txt
    |
    '-- __pycache__/
```

## Summary

The Amararaja Integrated QTP architecture is divided into three main areas:

```text
Host Application
      +
TCP/IP QTP Communication
      +
Target Test Application
```

The key change compared with the previous UART-based QTP is the communication layer:

```text
Previous QTP

Host
 |
UART
 |
Target
```

becomes:

```text
Amararaja Integrated QTP

Host
 |
Ethernet
 |
TCP/IP
 |
QTP Header + TLV Payload
 |
Target
```

The Host continues to control test execution, while the Target performs the actual hardware tests and returns streamed information and final test results.

## Standalone deployment update

Both Host and Target folders include `qtp_protocol.py` beside `main.py`. Copy the complete application folder to its machine; no parent-folder import is required. The project-root protocol file is the canonical source; keep the bundled copies identical.
