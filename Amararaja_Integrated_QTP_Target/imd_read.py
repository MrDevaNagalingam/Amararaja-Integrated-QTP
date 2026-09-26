#!/usr/bin/env python3
"""
read_imd.py
------------
Reads parameters from the Insulation Monitoring Device (IMD) - Bender
ISOMETER isoCHA425HV + AGH420-1/AGH421-1 - over Modbus RTU.

Self-contained: implements the Modbus RTU framing/CRC/decoding itself
(only dependency is pyserial: `pip install pyserial`) so every byte of
the transmitted request and received response can be printed in full
detail.

This version is corrected against two authoritative sources:
  1. Bender's official manual isoCHA425HV_D00404_06_M_XXEN, chapter 5
     "Data access via RS-485 interface" (register map, byte layout).
  2. EVerest's Bender_isoCHA425HV driver (isolation_monitorImpl.cpp/.hpp),
     which implements the same protocol in production.

Both sources agree on every point below, in particular:
  - Each "measurement channel" is FOUR consecutive holding registers:
        reg+0, reg+1  -> 32-bit IEEE-754 float, standard big-endian
                          word order (reg+0 = high word, reg+1 = low
                          word - NO word swap / NO byte swap)
        reg+2 (HiByte) -> Alarm type + Test type (AT&T)
        reg+2 (LoByte) -> Unit + Range/validity (R&U)
        reg+3          -> Channel description code (full 16-bit word)
  - The previous version of this script assumed a word-swapped (CDAB)
    32-bit layout copied from an unrelated DC meter. That was WRONG for
    this device and has been removed.

Serial settings (from EVSE_Interface.docx, IMD test):
    COM Port : /dev/ttyCH9344USB0
    Baudrate : 9600, 8 data bits, No parity, 1 stop bit  (device default
               is 8E1 - even parity - confirm against your device's
               actual "out" menu configuration, see test procedure)
    Slave ID : 5 (Channel A / COM4)  or  4 (Channel C / COM11, 2nd IMD)
               Note: Bender's own factory default bus address is 3.
               Use whatever your commissioning docs / device menu show.

Confirmed register map (isoCHA425HV manual, section 5.3.1 / 5.3.2):
    1000-1003  RF    Insulation resistance                [kOhm]
    1008-1011  Un    System voltage (L1/+ to L2/-)         [V]
    1012-1015  Ce    System leakage capacitance            [F]
    1016-1019  UL1e  Residual voltage L1/+ to earth        [V]
    1020-1023  UL2e  Residual voltage L2/- to earth        [V]
    1024-1027  R%    Fault location                        [%]
    1028-1031  RFU   One-pole insulation resistance        [kOhm]
    1032-1035  --    Measured value update counter
    9800-9809  Device name (ASCII, 2 chars/word, 10 words)
    9820-9825  Firmware info: ident, version, year, month, day, modbus
               driver version

Write-only command registers used for testing:
    8005  WO  Start self test          -> write 0x5445 ("TE")
    8006  WO  Reset command            -> write 0x434C ("CL")
    8003  WO  Factory reset (all)      -> write 0x6661 ("fa")
    8004  WO  Factory reset (FAC-only) -> write 0x4653 ("FS")

Usage:
    python3 read_imd.py
    python3 read_imd.py --port /dev/ttyCH9344USB0 --slave 5
    python3 read_imd.py --slave 4                     # 2nd IMD
    python3 read_imd.py --loop --interval 2
    python3 read_imd.py --self-test                   # trigger self test
    python3 read_imd.py --reset                       # clear fault memory
"""

from __future__ import annotations

import contextlib
import os
import struct
import sys
import time
from datetime import datetime

try:
    import serial
except ImportError:
    serial = None


# ==========================================================================
# Modbus RTU helpers (framing, CRC16, decoding, serial transaction w/ full
# TX/RX logging)
# ==========================================================================

def crc16_modbus(data: bytes) -> bytes:
    """Return the 2-byte Modbus CRC16 for `data`, low byte first (as it is
    transmitted on the wire)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return struct.pack('<H', crc)


def hx(data: bytes) -> str:
    return ' '.join(f'{b:02X}' for b in data)


def build_read_holding_registers_request(slave_id: int, start_addr: int,
                                          quantity: int) -> bytes:
    """Function 0x03 - Read Holding Registers."""
    body = struct.pack('>B B H H', slave_id, 0x03, start_addr, quantity)
    return body + crc16_modbus(body)


def build_write_multiple_registers_request(slave_id: int, start_addr: int,
                                            values) -> bytes:
    """Function 0x10 - Write Multiple Registers (matches manual 5.2.2 and
    the EVerest driver's call_modbus_write_multiple_registers)."""
    quantity = len(values)
    byte_count = quantity * 2
    body = struct.pack('>B B H H B', slave_id, 0x10, start_addr, quantity, byte_count)
    for v in values:
        body += struct.pack('>H', v)
    return body + crc16_modbus(body)


class ModbusError(Exception):
    pass


def parse_read_holding_registers_response(resp: bytes):
    if len(resp) < 5:
        raise ModbusError(f"Response too short ({len(resp)} bytes): {hx(resp)}")

    slave_id = resp[0]
    func_code = resp[1]

    if func_code & 0x80:
        exc_code = resp[2] if len(resp) > 2 else None
        exc_meanings = {
            0x01: "Impermissible function", 0x02: "Impermissible data access",
            0x03: "Impermissible data value", 0x04: "Internal fault",
            0x05: "Acknowledgement of receipt (delayed answer)",
            0x06: "Request not accepted (repeat if necessary)",
        }
        meaning = exc_meanings.get(exc_code, "Unknown")
        raise ModbusError(
            f"Modbus EXCEPTION from slave {slave_id}: function 0x{func_code:02X}, "
            f"exception 0x{exc_code:02X} ({meaning})"
        )

    byte_count = resp[2]
    expected_len = 3 + byte_count + 2
    if len(resp) < expected_len:
        raise ModbusError(f"Incomplete frame: expected {expected_len} bytes, got {len(resp)}: {hx(resp)}")

    data = resp[3:3 + byte_count]
    crc_received = resp[3 + byte_count:3 + byte_count + 2]
    crc_calc = crc16_modbus(resp[:3 + byte_count])
    crc_ok = (crc_received == crc_calc)

    registers = [int.from_bytes(data[i:i + 2], 'big') for i in range(0, len(data), 2)]
    return slave_id, func_code, byte_count, registers, crc_ok, crc_received, crc_calc


def parse_write_response(resp: bytes):
    """Function 0x10 echoes: [id][func 0x10][start hi][start lo][qty hi][qty lo][crc]."""
    if len(resp) < 8:
        raise ModbusError(f"Write response too short ({len(resp)} bytes): {hx(resp)}")
    slave_id = resp[0]
    func_code = resp[1]
    if func_code & 0x80:
        exc_code = resp[2] if len(resp) > 2 else None
        raise ModbusError(f"Modbus EXCEPTION on write from slave {slave_id}: "
                           f"function 0x{func_code:02X}, exception code {exc_code}")
    start_addr = int.from_bytes(resp[2:4], 'big')
    qty = int.from_bytes(resp[4:6], 'big')
    crc_received = resp[6:8]
    crc_calc = crc16_modbus(resp[:6])
    return slave_id, func_code, start_addr, qty, crc_received == crc_calc


# --------------------------------------------------------------------------
# 32-bit float decoding - CONFIRMED standard big-endian (ABCD), no word
# swap. Source: isoCHA425HV manual section 5.3.1.2 "Float = Floating point
# value" (IEEE 754, register N = bits 31..16, register N+1 = bits 15..0),
# and isolation_monitorImpl.cpp::read_register():
#     value = (reg[0] << 16) | reg[1];  val = *reinterpret_cast<float*>(&value);
# --------------------------------------------------------------------------
def regs_to_float_be(reg_hi_word, reg_lo_word) -> float:
    raw = struct.pack('>HH', reg_hi_word, reg_lo_word)
    return struct.unpack('>f', raw)[0]


# --------------------------------------------------------------------------
# AT&T byte (register+2, high byte): alarm type (bits 0-2) + test type
# (bits 6-7). Source: manual 5.3.1.3, matches to_alarm_type()/to_test_type()
# in isolation_monitorImpl.hpp.
# --------------------------------------------------------------------------
def decode_alarm_type(att_hi_byte: int) -> str:
    t = att_hi_byte & 0x07
    test_bits = (att_hi_byte >> 6) & 0x03
    if t == 0x00:
        return "NoAlarm"
    if t == 0x01:
        return "PreWarning"
    if t == 0x02 and (att_hi_byte & 0xC0) == 0x00:
        return "DeviceError"
    if t == 0x04:
        return "Warning"
    if t == 0x05:
        return "Alarm"
    return "Reserved"


def decode_test_type(att_hi_byte: int) -> str:
    t = (att_hi_byte >> 6) & 0x03
    if t == 0x01:
        return "InternalTest"
    if t == 0x02:
        return "ExternalTest"
    return "NoTest"


# --------------------------------------------------------------------------
# R&U byte (register+2, low byte): unit (bits 0-4) + range/validity
# (bits 6-7). Source: manual 5.3.1.4, matches to_unit_type()/to_valid_type().
# --------------------------------------------------------------------------
UNIT_TYPES = {
    0: "Invalid", 1: "NoUnit", 2: "Ohm", 3: "Ampere", 4: "Volt", 5: "Percent",
    6: "Hertz", 7: "Baud", 8: "Farad", 9: "Henry", 10: "DegC", 11: "DegF",
    12: "Seconds", 13: "Minutes", 14: "Hours", 15: "Days", 16: "Months",
}


def decode_unit(ru_lo_byte: int) -> str:
    return UNIT_TYPES.get(ru_lo_byte & 0x1F, "Invalid")


def decode_valid(ru_lo_byte: int) -> str:
    t = (ru_lo_byte >> 6) & 0x03
    if t == 1:
        return "TrueValueIsSmaller"
    if t == 2:
        return "TrueValueIsBigger"
    if t == 3:
        return "Invalid"
    return "TrueValue"


# --------------------------------------------------------------------------
# Channel description (register+3, full 16-bit word). Source: manual
# 5.3.1.5, matches to_channel_description().
# --------------------------------------------------------------------------
CHANNEL_DESCRIPTIONS = {
    1: "IsolationError", 71: "IsolationError_rF", 76: "Voltage",
    77: "UnderVoltage", 78: "OverVoltage", 82: "Capacity",
    86: "IsolationError_Zi", 101: "GridConnection", 102: "EarthConnection",
    115: "DeviceErrorIsometer", 129: "DeviceError", 145: "OwnAddress",
}


def decode_channel_description(raw: int) -> str:
    return CHANNEL_DESCRIPTIONS.get(raw, f"Undefined({raw})")


def decode_measurement_channel(regs4):
    """Decode a 4-register measurement channel block (reg+0..reg+3)."""
    if len(regs4) != 4:
        raise ValueError("A measurement channel is exactly 4 registers")
    reg0, reg1, reg2, reg3 = regs4
    att_hi = (reg2 >> 8) & 0xFF
    ru_lo = reg2 & 0xFF
    return {
        "value": regs_to_float_be(reg0, reg1),
        "alarm": decode_alarm_type(att_hi),
        "test": decode_test_type(att_hi),
        "unit": decode_unit(ru_lo),
        "valid": decode_valid(ru_lo),
        "description": decode_channel_description(reg3),
        "raw_registers": regs4,
    }


def open_serial(port: str, baudrate: int, parity: str, timeout: float):
    if serial is None:
        raise RuntimeError("pyserial is required for live IMD serial reads")
    parity_map = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}
    return serial.Serial(
        port=port, baudrate=baudrate, bytesize=serial.EIGHTBITS,
        parity=parity_map.get(parity.upper(), serial.PARITY_NONE),
        stopbits=serial.STOPBITS_ONE, timeout=timeout,
    )


def _ts() -> str:
    return datetime.now().strftime('%H:%M:%S.%f')[:-3]


def read_holding_registers(ser: serial.Serial, slave_id: int, start_addr: int,
                            quantity: int, label: str = "") -> dict:
    request = build_read_holding_registers_request(slave_id, start_addr, quantity)

    print("-" * 78)
    print(f"[{_ts()}] >>> TX  ({label})" if label else f"[{_ts()}] >>> TX")
    print(f"    Slave/Address ID   : {slave_id}")
    print(f"    Function code      : 0x03 (Read Holding Registers)")
    print(f"    Start address      : {start_addr} (0x{start_addr:04X})")
    print(f"    Quantity           : {quantity} registers")
    print(f"    Raw frame ({len(request)} bytes): {hx(request)}")

    ser.reset_input_buffer()
    ser.reset_output_buffer()
    t0 = time.time()
    ser.write(request)
    ser.flush()

    expected_len = 3 + (2 * quantity) + 2
    response = bytearray()
    deadline = time.time() + max(ser.timeout or 1.0, 0.5) + (quantity * 0.002)
    while len(response) < expected_len and time.time() < deadline:
        chunk = ser.read(expected_len - len(response))
        if chunk:
            response.extend(chunk)
        else:
            break
    elapsed_ms = (time.time() - t0) * 1000.0

    print(f"[{_ts()}] <<< RX  (round-trip {elapsed_ms:.1f} ms)")
    if not response:
        print("    !! No response received (timeout). Check wiring, slave ID, port, baud, parity.")
        raise ModbusError("No response / timeout")

    print(f"    Raw frame ({len(response)} bytes): {hx(bytes(response))}")

    (slave_id_r, func_r, byte_count, registers,
     crc_ok, crc_rx, crc_calc) = parse_read_holding_registers_response(bytes(response))

    print(f"    -> Byte count      : {byte_count}")
    print(f"    -> CRC             : {'OK' if crc_ok else 'MISMATCH!'}")
    print(f"    -> Registers ({len(registers)}): " +
          ', '.join(f"[{start_addr + i}]=0x{r:04X}({r})" for i, r in enumerate(registers)))

    return {"slave_id": slave_id_r, "function": func_r, "registers": registers,
            "crc_ok": crc_ok, "start_addr": start_addr}


def write_multiple_registers(ser: serial.Serial, slave_id: int, start_addr: int,
                              values, label: str = "") -> bool:
    request = build_write_multiple_registers_request(slave_id, start_addr, values)

    print("-" * 78)
    print(f"[{_ts()}] >>> TX WRITE ({label})" if label else f"[{_ts()}] >>> TX WRITE")
    print(f"    Slave ID: {slave_id}  Start: {start_addr} (0x{start_addr:04X})  Values: {values}")
    print(f"    Raw frame ({len(request)} bytes): {hx(request)}")

    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(request)
    ser.flush()

    response = bytearray()
    deadline = time.time() + max(ser.timeout or 1.0, 0.5)
    while len(response) < 8 and time.time() < deadline:
        chunk = ser.read(8 - len(response))
        if chunk:
            response.extend(chunk)
        else:
            break

    print(f"[{_ts()}] <<< RX")
    if not response:
        print("    !! No response received (timeout).")
        return False
    print(f"    Raw frame ({len(response)} bytes): {hx(bytes(response))}")

    try:
        slave_id_r, func_r, start_r, qty_r, crc_ok = parse_write_response(bytes(response))
    except ModbusError as e:
        print(f"    !! {e}")
        return False

    print(f"    -> Echoed start={start_r}, qty={qty_r}, CRC {'OK' if crc_ok else 'MISMATCH!'}")
    return crc_ok


# ==========================================================================
# Confirmed register map (isoCHA425HV manual section 5.3.1)
# ==========================================================================
MEASUREMENT_CHANNELS = [
    (1000, "RF", "Insulation resistance"),
    (1008, "Un", "System voltage (L1/+ to L2/-)"),
    (1012, "Ce", "System leakage capacitance"),
    (1016, "UL1e", "Residual voltage L1/+ to earth"),
    (1020, "UL2e", "Residual voltage L2/- to earth"),
    (1024, "R%", "Fault location"),
    (1028, "RFU", "One-pole insulation resistance"),
    (1032, "UpdCnt", "Measured value update counter"),
]

DEVICE_NAME_ADDR = 9800
DEVICE_NAME_QTY = 10
FIRMWARE_ADDR = 9820
FIRMWARE_QTY = 6

CMD_START_SELF_TEST = (8005, 0x5445)   # "TE"
CMD_RESET = (8006, 0x434C)             # "CL"

# ==========================================================================
# Device configuration (parameter) registers - mirrors
# isolation_monitorImpl.cpp::configure_device() exactly, including which
# registers are written, in what order, and the bool-vs-value casting the
# driver uses for each one. Manual section 5.3.2.1 "Parameter coding" is
# the authoritative description of each register; a couple of driver
# quirks worth knowing about are noted inline below.
#
# Defaults below come from the manual's factory settings, NOT from a real
# EVerest config.yaml (that lives in the module's manifest and wasn't
# provided). Override every value that matters for your installation
# with the --set-* flags before running --configure on real hardware.
# ==========================================================================
CONFIG_REGISTERS = [
    # (register, description, get_value_fn(cfg))
    (3000, "Ue> voltage-to-earth alarm enable",
     lambda cfg: 1 if cfg["voltage_to_earth_monitoring_alarm_enable"] else 0),
    (3005, "R1 prewarning threshold [kOhm]", lambda cfg: cfg["r1_prealarm_kohm"]),
    (3007, "R2 alarm threshold [kOhm]", lambda cfg: cfg["r2_alarm_kohm"]),
    (3008, "Undervoltage alarm enable", lambda cfg: 1 if cfg["undervoltage_alarm_enable"] else 0),
    (3009, "Undervoltage threshold [V]", lambda cfg: cfg["undervoltage_alarm_threshold_V"]),
    (3010, "Overvoltage alarm enable", lambda cfg: 1 if cfg["overvoltage_alarm_enable"] else 0),
    (3011, "Overvoltage threshold [V]", lambda cfg: cfg["overvoltage_alarm_threshold_V"]),
    (3012, "Fault memory (M) enable", lambda cfg: 1 if cfg["alarm_memory_enable"] else 0),
    (3013, "Relay K1 mode (0=n/o, 1=n/c)", lambda cfg: 1 if cfg["relais_r1_mode"] else 0),
    (3014, "Relay K2 mode (0=n/o, 1=n/c)", lambda cfg: 1 if cfg["relais_r2_mode"] else 0),
    # NOTE: the manual defines register 3018 as the numeric start-up delay
    # "t" in seconds (0-10), but the EVerest driver writes it as a bool
    # (config.delay_startup_device ? 1 : 0) - i.e. it only ever writes 0
    # or 1, not an actual second count. Reproduced here faithfully; if you
    # need a specific delay in seconds, write it separately.
    (3018, "Start-up delay 't' (driver writes bool 0/1, NOT seconds - see note)",
     lambda cfg: 1 if cfg["delay_startup_device"] else 0),
    (3019, "Response delay ton [s]", lambda cfg: cfg["delay_t_on_k1_k2"]),
    (3020, "Delay on release toff [s]", lambda cfg: cfg["delay_t_off_k1_k2"]),
    # NOTE: register 3023 is the insulation-monitoring MODE (0=dc/CCS,
    # 1=CHd, 2=CHA per the manual), but the driver only ever writes 0 or 1
    # via a bool cast - so this driver can select "dc" or "CHd", never
    # "CHA", even though the Conf field is named chademo_mode.
    (3023, "Insulation monitoring mode (0=dc/CCS, 1=CHd; driver can't select CHA)",
     lambda cfg: 1 if cfg["chademo_mode"] else 0),
    (3024, "Self test: system connection test 'nEt' (driver writes bool 0/1, "
           "manual also allows 2='on U')",
     lambda cfg: 1 if cfg["selftest_enable_gridconnection"] else 0),
    (3025, "Self test at device start 'S.Ct'", lambda cfg: 1 if cfg["selftest_enable_at_start"] else 0),
    # "start up": request stop mode register, 1 = run normally (not stopped)
    (3026, "Request stop mode (1 = run normally)", lambda cfg: 1),
]

DEFAULT_CONFIG = {
    "voltage_to_earth_monitoring_alarm_enable": False,   # manual factory default: off
    "r1_prealarm_kohm": 600,                              # manual factory default
    "r2_alarm_kohm": 120,                                 # manual factory default
    "undervoltage_alarm_enable": False,
    "undervoltage_alarm_threshold_V": 10,
    "overvoltage_alarm_enable": False,
    "overvoltage_alarm_threshold_V": 1100,
    "alarm_memory_enable": False,
    "relais_r1_mode": True,   # manual factory default: n/c (True here => 1 => n/c)
    "relais_r2_mode": True,
    "delay_startup_device": False,
    "delay_t_on_k1_k2": 0,
    "delay_t_off_k1_k2": 0,
    "chademo_mode": False,    # False -> dc/CCS mode (manual factory default)
    "selftest_enable_gridconnection": False,
    "selftest_enable_at_start": False,
}

IMD1_CONFIG = dict(DEFAULT_CONFIG)

IMD2_CONFIG = dict(DEFAULT_CONFIG)
IMD2_CONFIG.update({
    "undervoltage_alarm_threshold_V": 30,
    "overvoltage_alarm_threshold_V": 500,
})


def read_device_name(ser, slave_id) -> str:
    result = read_holding_registers(ser, slave_id, DEVICE_NAME_ADDR, DEVICE_NAME_QTY,
                                     label="Device name")
    chars = []
    for reg in result["registers"]:
        chars.append(chr((reg >> 8) & 0xFF))
        chars.append(chr(reg & 0xFF))
    name = ''.join(chars).replace('\n', ' ').strip('\x00 ')
    return name


def read_firmware_version(ser, slave_id) -> str:
    result = read_holding_registers(ser, slave_id, FIRMWARE_ADDR, FIRMWARE_QTY,
                                     label="Firmware version")
    r = result["registers"]
    ident, version, year, month, day, modbus_driver = r[0], r[1], r[2], r[3], r[4], r[5]
    return (f"Ident: {ident} | Version: {version / 100:.2f} | "
            f"Date: {year:04d}-{month:02d}-{day:02d} | Modbus Driver: {modbus_driver}")


def read_measurement_channel(ser, slave_id, addr, short_name, description):
    result = read_holding_registers(ser, slave_id, addr, 4, label=f"{short_name} ({description})")
    decoded = decode_measurement_channel(result["registers"])
    return decoded


def print_channel(short_name, description, decoded):
    print(f"    {short_name:8s} {description:32s} value={decoded['value']:.4f} "
          f"[{decoded['unit']}]  alarm={decoded['alarm']:12s} test={decoded['test']:12s} "
          f"valid={decoded['valid']:20s} desc={decoded['description']}")


def run_once(ser, slave_id, channels_to_read):
    print(f"\n########## IMD (ISOMETER isoCHA425HV) read | slave ID {slave_id} ##########")

    try:
        name = read_device_name(ser, slave_id)
        print(f"Device name     : {name!r}")
    except ModbusError as e:
        print(f"!! Could not read device name: {e}")

    try:
        fw = read_firmware_version(ser, slave_id)
        print(f"Firmware        : {fw}")
    except ModbusError as e:
        print(f"!! Could not read firmware version: {e}")

    print("\nMeasurement channels:")
    print("-" * 108)
    for addr, short_name, description in MEASUREMENT_CHANNELS:
        if channels_to_read and short_name not in channels_to_read:
            continue
        try:
            decoded = read_measurement_channel(ser, slave_id, addr, short_name, description)
            print_channel(short_name, description, decoded)
        except ModbusError as e:
            print(f"    !! {short_name}: read failed: {e}")
    print("-" * 108)


def configure_device(ser, slave_id, cfg, max_retries=None):
    """Write all parameter registers in isolation_monitorImpl.cpp's
    configure_device() order. Mirrors the driver's behaviour: on ANY
    write failure, wait 10s and retry the WHOLE sequence from the top
    (the real driver does this forever - `max_retries=None` here does
    the same; pass a number to bound it for interactive/test use)."""
    attempt = 0
    while True:
        attempt += 1
        print(f"\n=== configure_device: attempt {attempt} ===")
        successful = True
        for register, description, get_value in CONFIG_REGISTERS:
            value = get_value(cfg)
            ok = write_multiple_registers(ser, slave_id, register, [value & 0xFFFF],
                                           label=f"{register}: {description} = {value}")
            successful = successful and ok
            if not ok:
                print(f"    !! Failed to write register {register} ({description})")

        if successful:
            print("configure_device: all parameter registers written successfully.")
            return True

        print("configure_device: one or more writes failed.")
        if max_retries is not None and attempt >= max_retries:
            print(f"configure_device: giving up after {attempt} attempt(s).")
            return False
        print("Waiting 10s before retrying (matches driver's MODBUS backoff)...")
        time.sleep(10)


def do_self_test(ser, slave_id):
    addr, value = CMD_START_SELF_TEST
    ok = write_multiple_registers(ser, slave_id, addr, [value], label="Start self test")
    if ok:
        print("Self test command accepted. Poll the RF channel's 'test' field "
              "(InternalTest/ExternalTest) and 'alarm' field to watch it complete "
              "(typically a few seconds up to ~15 s in cable-check mode).")
    else:
        print("Self test command failed or was not acknowledged.")


def do_reset(ser, slave_id):
    addr, value = CMD_RESET
    ok = write_multiple_registers(ser, slave_id, addr, [value], label="Reset command")
    if ok:
        print("Reset command accepted (fault memory cleared).")
    else:
        print("Reset command failed or was not acknowledged.")



class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def make_target_log_path(test_name):
    safe = "".join(ch if ch.isalnum() else "_" for ch in test_name).strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join("/home/root", "{}_{}.txt".format(safe, timestamp))


def format_measurement_table(rows, device_name="", firmware_version=""):
    lines = [
        "Device name      : {}".format(device_name),
        "Firmware version : {}".format(firmware_version),
        "",
        "## Channel  Description                         Value        Unit      Valid                 Alarm",
        "",
    ]
    for row in rows:
        lines.append(
            "{channel:<8} {description:<32} {value:>11}  {unit:<8}  {valid:<20}  {alarm}".format(**row)
        )
    return "\n".join(lines)


def read_all_measurements(ser, slave_id, channels_to_read=None):
    rows = []
    failures = []
    device_name = ""
    firmware_version = ""
    print("\n########## IMD (ISOMETER isoCHA425HV) read | slave ID {} ##########".format(slave_id))

    try:
        device_name = read_device_name(ser, slave_id)
        print("Device name     : {!r}".format(device_name))
    except ModbusError as exc:
        failures.append("Device name read failed: {}".format(exc))
        print("!! Could not read device name: {}".format(exc))

    try:
        firmware_version = read_firmware_version(ser, slave_id)
        print("Firmware        : {}".format(firmware_version))
    except ModbusError as exc:
        failures.append("Firmware read failed: {}".format(exc))
        print("!! Could not read firmware version: {}".format(exc))

    print("\nMeasurement channels:")
    print("-" * 108)
    wanted = set(channels_to_read or [])
    for addr, short_name, description in MEASUREMENT_CHANNELS:
        if wanted and short_name not in wanted:
            continue
        try:
            decoded = read_measurement_channel(ser, slave_id, addr, short_name, description)
            print_channel(short_name, description, decoded)
            rows.append({
                "channel": short_name,
                "description": description,
                "value": "{:.4f}".format(decoded["value"]),
                "unit": decoded["unit"],
                "valid": decoded["valid"],
                "alarm": decoded["alarm"],
                "test": decoded["test"],
                "address": addr,
            })
        except ModbusError as exc:
            failures.append("{} read failed: {}".format(short_name, exc))
            print("    !! {}: read failed: {}".format(short_name, exc))
    print("-" * 108)
    return rows, failures, device_name, firmware_version


def run_qtp_test(test_name, port, baudrate, parity, slave_id, timeout=1.0,
                 channels_to_read=None, device_config=None):
    log_path = make_target_log_path(test_name)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    rows = []
    failures = []
    device_name = ""
    firmware_version = ""
    with open(log_path, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(Tee(sys.stdout, log_file)):
            print("Opening serial port {} @ {} 8{}1 ...".format(port, baudrate, parity))
            cfg = device_config or DEFAULT_CONFIG
            print("IMD config reference: undervoltage_alarm_threshold_V={} overvoltage_alarm_threshold_V={}".format(
                cfg["undervoltage_alarm_threshold_V"], cfg["overvoltage_alarm_threshold_V"]))
            ser = open_serial(port, baudrate, parity, timeout)
            try:
                rows, failures, device_name, firmware_version = read_all_measurements(ser, slave_id, channels_to_read)
            finally:
                ser.close()
            print("Target full log saved: {}".format(log_path))
    status = "PASS" if rows and not failures else "FAIL"
    message = "Target full log saved: {}".format(log_path)
    if failures:
        message += "\n\nFailures:\n- " + "\n- ".join(failures)
    return {
        "status": status,
        "message": message,
        "measurements": {
            "table": format_measurement_table(rows, device_name, firmware_version) if rows else "",
            "target_log": log_path,
            "rows": rows,
            "failures": failures,
            "device_name": device_name,
            "firmware_version": firmware_version,
        },
    }
