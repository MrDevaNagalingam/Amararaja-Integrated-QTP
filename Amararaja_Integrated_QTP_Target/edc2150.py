#!/usr/bin/env python3
"""
read_edc2150.py  (per-parameter version)
------------------------------------------
Reads the DC Energy Meter (Elmeasure EDC2150 / EDC2150D / EDC2450 /
EDC2450D / EDC2450H) over Modbus RTU, one parameter at a time -- a
*separate* Read Holding Registers (FC 0x03) request per measurand --
exactly the way EVerest's GenericPowermeter driver walks a model YAML
file, and in the same style as read_ac_energymeter_permodel.py (mfm.py)
for the Selec EM4M AC meter.

This REPLACES the old single burst-read version of this script (which
read all 100 registers 4100..4199 in one FC03 request). That version is
still useful for discovery/dumping the whole map; this version is for
walking the model file field-by-field the way the driver actually does
it in production.

Self-contained: only dependency is pyserial (`pip install pyserial`).

Serial settings (unchanged from the original script):
    COM Port : /dev/ttyCH9344USB1
    Baudrate : 9600, 8 data bits, No parity, 1 stop bit
    Slave ID : 2 (Channel B / COM30)  or  3 (Channel D / COM27, 2nd meter)

Register map / scaling below is taken directly from the EDC2150 model
YAML (the file with energy_Wh_import / energy_Wh_export / power_W /
voltage_V / current_A / reactive_power_VAR / frequency_Hz blocks):

    Parameter            start_register  num_registers  multiplier  FC
    ------------------------------------------------------------------
    voltage_V                  4100            2            1       03
    current_A                  4102            2            1       03
    power_W                    4104            2            1       03
    energy_Wh_import           4106            2          0.001     03
    energy_Wh_export           4112            2          0.001     03
    reactive_power_VAR            0            0            -       -   (not available)
    frequency_Hz                   0           0            -       -   (not available)

*** DISCREPANCY - RESOLVED ***
The YAML file's own header comment said the intended offsets are
Voltage=4100, Current CH1=4102, Watts CH1=4104, KWh Received CH1=4106,
KWh Delivered CH1=4112, but the YAML body had them set ONE HIGHER
(4101/4103/4105/4107/4113). The live capture in read_edc2150.py's
burst-read output (which reads the whole 4100..4199 block in a single
FC03 request and indexes into it) confirmed the LOWER numbers are
correct: "Voltage" is built from registers 4100 (lo) + 4101 (hi), and
"KWh Received CH1" from 4106 (lo) + 4107 (hi) -- not 4101/4102 or
4107/4108.

This script now ONLY reads the confirmed offsets (4100, 4102, 4104,
4106, 4112). The old (buggy) YAML-literal offsets (4101/4103/4105/
4107/4113) have been removed entirely -- this script no longer reads
or reports on them. The EVerest DC meter model YAML should be
corrected to match these same base addresses.

Usage:
    python3 read_edc2150.py
    python3 read_edc2150.py --port /dev/ttyCH9344USB1 --slave 2
    python3 read_edc2150.py --slave 3          # 2nd DC meter
    python3 read_edc2150.py --loop --interval 2
"""

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
# TX/RX logging) -- same as the original read_edc2150.py, this meter uses
# Read HOLDING Registers (FC 0x03), unlike the EM4M script which uses
# Read INPUT Registers (FC 0x04).
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
    """
    Build a Modbus RTU 'Read Holding Registers' (function 0x03) request:
        [Slave ID][Func 0x03][Start Addr Hi][Start Addr Lo]
        [Qty Hi][Qty Lo][CRC Lo][CRC Hi]
    """
    body = struct.pack('>B B H H', slave_id, 0x03, start_addr, quantity)
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
        raise ModbusError(
            f"Modbus EXCEPTION response from slave {slave_id}: "
            f"function 0x{func_code:02X}, exception code {exc_code}"
        )

    byte_count = resp[2]
    expected_len = 3 + byte_count + 2
    if len(resp) < expected_len:
        raise ModbusError(
            f"Incomplete frame: expected {expected_len} bytes, got {len(resp)}: {hx(resp)}"
        )

    data = resp[3:3 + byte_count]
    crc_received = resp[3 + byte_count:3 + byte_count + 2]
    crc_calc = crc16_modbus(resp[:3 + byte_count])
    crc_ok = (crc_received == crc_calc)

    registers = [
        int.from_bytes(data[i:i + 2], 'big')
        for i in range(0, len(data), 2)
    ]

    return slave_id, func_code, byte_count, registers, crc_ok, crc_received, crc_calc


# --------------------------------------------------------------------------
# 32-bit value decoding (2 consecutive holding registers -> float)
# --------------------------------------------------------------------------
# Confirmed via Modbus Poll testing (EVSE_Interface.docx, "Figure 5: Data
# Format for Floating-Point Values") that this meter uses word-swapped
# (CDAB) ordering: the FIRST register (lower address) holds the LOW 16
# bits, the SECOND register (higher address) holds the HIGH 16 bits.
def regs_to_float_cdab(reg_lo, reg_hi) -> float:
    raw = struct.pack('>HH', reg_hi, reg_lo)
    return struct.unpack('>f', raw)[0]


def open_serial(port: str, baudrate: int, timeout: float):
    if serial is None:
        raise RuntimeError("pyserial is required for live EDC2150 serial reads")
    return serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=timeout,
    )


def _ts() -> str:
    return datetime.now().strftime('%H:%M:%S.%f')[:-3]


def read_param_registers(ser, slave_id: int, start_addr: int,
                          num_registers: int, label: str = "") -> dict:
    """
    Send a single Read Holding Registers (FC 0x03) request covering just
    this one parameter's registers -- the same per-parameter request
    shape EVerest issues when walking a model YAML -- and print full
    TX/RX detail. Returns a dict with the parsed result (or raises
    ModbusError).
    """
    request = build_read_holding_registers_request(slave_id, start_addr, num_registers)

    print(f"[{_ts()}] >>> TX  {label}")
    print(f"    Slave={slave_id}  Func=0x03  start_addr={start_addr} "
          f"(0x{start_addr:04X})  qty={num_registers}  "
          f"Raw frame: {hx(request)}")

    ser.reset_input_buffer()
    ser.reset_output_buffer()
    t0 = time.time()
    ser.write(request)
    ser.flush()

    expected_len = 3 + (2 * num_registers) + 2  # id+func+bytecount + data + crc
    response = bytearray()
    deadline = time.time() + max(ser.timeout or 1.0, 0.5) + (num_registers * 0.002)
    while len(response) < expected_len and time.time() < deadline:
        chunk = ser.read(expected_len - len(response))
        if chunk:
            response.extend(chunk)
        else:
            break
    elapsed_ms = (time.time() - t0) * 1000.0

    if not response:
        print(f"[{_ts()}] <<< RX  (round-trip {elapsed_ms:.1f} ms)  !! No response (timeout)")
        raise ModbusError(f"No response / timeout reading start_addr {start_addr}")

    print(f"[{_ts()}] <<< RX  (round-trip {elapsed_ms:.1f} ms)  Raw frame: {hx(bytes(response))}")

    (slave_id_r, func_r, byte_count, registers,
     crc_ok, crc_rx, crc_calc) = parse_read_holding_registers_response(bytes(response))

    status = "OK" if crc_ok else "MISMATCH!"
    print(f"    -> Registers: " +
          ', '.join(f"[{start_addr + i}]=0x{r:04X}({r})" for i, r in enumerate(registers)))
    print(f"    CRC received: {hx(crc_rx)}  CRC calculated: {hx(crc_calc)}  [{status}]")

    return {
        "registers": registers,
        "crc_ok": crc_ok,
    }


# ==========================================================================
# Register map -- taken directly from the EDC2150 model YAML, using the
# confirmed-correct base addresses (see discrepancy note above). This is
# the ONLY register map the script reads; the old YAML-literal offsets
# (4101/4103/4105/4107/4113) have been removed.
# Each entry is one independent FC03 read of `num_registers` registers,
# matching how EVerest's GenericPowermeter driver walks this model.
# start_register == 0 means "not available on this device" per the YAML.
#
#   name                     start_register       num_registers  multiplier
# ==========================================================================
PARAMS = [
    ("Voltage (V)",                    4100, 2, 1,     True),
    ("Current CH1 (A)",                4102, 2, 1,     True),
    ("Power CH1 (W)",                  4104, 2, 1,     True),
    ("Energy Import CH1 (kWh->Wh)",    4106, 2, 0.001, True),  # KWh Received
    ("Energy Export CH1 (kWh->Wh)",    4112, 2, 0.001, True),  # KWh Delivered
    ("Reactive Power (VAR)",              0, 0, 0.001, False),  # not available
    ("Frequency (Hz)",                    0, 0, 1,     False),  # not available
]


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


def make_target_log_path(test_name: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in test_name).strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join("/home/root", "{}_{}.txt".format(safe, timestamp))


def format_parameter_table(rows: list) -> str:
    lines = [
        "{:<30}{:>10}  {:>14}  {:>14}  {}".format(
            "Parameter", "StartAddr", "RawFloat", "Scaled", "Available?"),
        "-" * 92,
    ]
    for row in rows:
        raw = row["raw"]
        scaled = row["scaled"]
        raw_s = "{:.6f}".format(raw) if isinstance(raw, float) else "--"
        scaled_s = "{:.6f}".format(scaled) if isinstance(scaled, float) else "--"
        available = "yes" if row["available"] else "N/A (not in YAML)"
        lines.append("{:<30}{:>10}  {:>14}  {:>14}  {}".format(
            row["name"], row["address"], raw_s, scaled_s, available))
    return "\n".join(lines)


def read_all_parameters(ser, slave_id: int) -> list:
    rows = []
    for name, addr, num_regs, multiplier, available in PARAMS:
        if not available:
            print("-" * 78)
            print("    ({}) -- start_register=0 in YAML: not available on this device, skipping.".format(name))
            rows.append({
                "name": name,
                "address": addr,
                "raw": None,
                "scaled": None,
                "available": available,
                "crc_ok": True,
                "error": "",
            })
            continue
        print("-" * 78)
        try:
            result = read_param_registers(ser, slave_id, addr, num_regs, label="({})".format(name))
            regs = result["registers"]
            if len(regs) < 2:
                raise ModbusError("Not enough registers returned to decode a float")
            raw = regs_to_float_cdab(regs[0], regs[1])
            scaled = raw * multiplier
            crc_ok = result["crc_ok"]
            error = ""
        except ModbusError as exc:
            raw = None
            scaled = None
            crc_ok = False
            error = str(exc)
        rows.append({
            "name": name,
            "address": addr,
            "raw": raw,
            "scaled": scaled,
            "available": available,
            "crc_ok": crc_ok,
            "error": error,
        })
    return rows


def run_qtp_test(port: str, baudrate: int, slave_id: int,
                 timeout: float) -> dict:
    log_path = make_target_log_path("TC-03_EDC2150_DC_Energy_Meter")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(Tee(sys.stdout, log_file)):
            print("Opening serial port {} @ {} 8N1 ...".format(port, baudrate))
            print("\n########## DC Energy Meter (EDC2150) | per-parameter read | slave ID {} ##########".format(slave_id))
            print("    (using confirmed register offsets 4100/4102/4104/4106/4112 -- see file header)")
            ser = open_serial(port, baudrate, timeout)
            try:
                rows = read_all_parameters(ser, slave_id)
            finally:
                ser.close()
            print("\n" + "=" * 92)
            print(format_parameter_table(rows))
            print("=" * 92)
            print("Target full log saved: {}".format(log_path))

    failures = []
    for row in rows:
        if not row["available"]:
            continue
        if row["error"]:
            failures.append("{}: {}".format(row["name"], row["error"]))
        elif not row["crc_ok"]:
            failures.append("{}: CRC mismatch".format(row["name"]))
    message = "Target full log saved: {}".format(log_path)
    if failures:
        message += "\n\nFailures:\n" + "\n".join("- " + failure for failure in failures)
    return {
        "status": "PASS" if not failures else "FAIL",
        "message": message,
        "measurements": {
            "port": port,
            "baudrate": baudrate,
            "slave_id": slave_id,
            "target_log": log_path,
            "table": format_parameter_table(rows),
            "rows": rows,
            "failures": failures,
        },
    }


def run_once(ser, slave_id: int):
    print(f"\n########## DC Energy Meter (EDC2150) | per-parameter read | slave ID {slave_id} ##########")
    print("    (using confirmed register offsets 4100/4102/4104/4106/4112 -- see file header)")
    rows = []
    for name, addr, num_regs, multiplier, available in PARAMS:
        print("-" * 78)
        if not available:
            print(f"    ({name}) -- start_register=0 in YAML: not available on this device, skipping.")
            rows.append((name, addr, None, None, available))
            continue
        try:
            result = read_param_registers(ser, slave_id, addr, num_regs, label=f"({name})")
        except ModbusError as e:
            print(f"    !! Read failed: {e}")
            rows.append((name, addr, None, None, available))
            continue

        regs = result["registers"]
        if len(regs) < 2:
            print("    !! Not enough registers returned to decode a float.")
            rows.append((name, addr, regs, None, available))
            continue

        raw_float = regs_to_float_cdab(regs[0], regs[1])
        scaled = raw_float * multiplier
        if not result["crc_ok"]:
            print("    !! WARNING: CRC mismatch - value may be corrupt.")
        rows.append((name, addr, raw_float, scaled, available))

    print("\n" + "=" * 92)
    print(f"{'Parameter':<30}{'StartAddr':>10}  {'RawFloat':>14}  {'Scaled':>14}  {'Available?'}")
    print("-" * 92)
    for name, addr, raw, scaled, available in rows:
        raw_s = f"{raw:.6f}" if isinstance(raw, float) else "--"
        scaled_s = f"{scaled:.6f}" if isinstance(scaled, float) else "--"
        avail_s = "yes" if available else "N/A (not in YAML)"
        print(f"{name:<30}{addr:>10}  {raw_s:>14}  {scaled_s:>14}  {avail_s}")
    print("=" * 92)
    print("NOTE: this run used the confirmed-correct register offsets (4100, 4102,\n"
          "      4104, 4106, 4112), matching read_edc2150.py's burst-read capture.")
