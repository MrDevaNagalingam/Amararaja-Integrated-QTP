#!/usr/bin/env python3
"""
read_ac_energymeter_permodel.py
--------------------------------
Reads the AC Energy Meter (Selec EM4M) over Modbus RTU, one parameter at
a time -- a *separate* single-register Read Input Registers (FC 0x04)
request per measurand, exactly as EVerest's GenericPowermeter driver does
when it walks the Selec_EM4M.yaml model file (rather than the single
10-register burst read used by the original read_ac_energymeter.py).

Self-contained: only dependency is pyserial (`pip install pyserial`).

Serial settings:
    Port     : /dev/ttyCH9344USB4  (Channel E / COM31)
    Baudrate : 9600, 8 data bits, No parity, 1 stop bit
    Slave ID : 1

Register map below is taken directly from the corrected Selec_EM4M.yaml
model file:
    - voltage_V is CONFIRMED (live-captured against a known 228V input).
    - power_W, current_A, frequency_Hz, reactive_power_VAR, and
      energy_Wh_import/export addresses are UNCONFIRMED placeholders
      (num_registers was fixed from an invalid 0 -> 1 so the driver can
      actually issue the read, but the addresses themselves still need
      live verification the same way voltage_V was confirmed).

Usage:
    python3 read_ac_energymeter_permodel.py
    python3 read_ac_energymeter_permodel.py --port /dev/ttyCH9344USB4 --slave 1
    python3 read_ac_energymeter_permodel.py --loop --interval 2
"""

import argparse
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


def build_read_input_registers_request(slave_id: int, start_addr: int,
                                        quantity: int) -> bytes:
    """
    Build a Modbus RTU 'Read Input Registers' (function 0x04) request:
        [Slave ID][Func 0x04][Start Addr Hi][Start Addr Lo]
        [Qty Hi][Qty Lo][CRC Lo][CRC Hi]
    """
    body = struct.pack('>B B H H', slave_id, 0x04, start_addr, quantity)
    return body + crc16_modbus(body)


class ModbusError(Exception):
    pass


def parse_read_input_registers_response(resp: bytes):
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


def open_serial(port: str, baudrate: int = 9600, timeout: float = 1.0):
    if serial is None:
        raise RuntimeError("pyserial is required for live Selec EM4M serial reads")
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


def read_single_register(ser, slave_id: int, addr: int,
                          label: str = "") -> dict:
    """
    Send a single-register Read Input Registers (FC 0x04, qty=1) request
    -- the same per-parameter request shape EVerest issues -- and print
    full TX/RX detail. Returns a dict with the parsed result (or raises
    ModbusError).
    """
    request = build_read_input_registers_request(slave_id, addr, 1)

    print(f"[{_ts()}] >>> TX  {label}")
    print(f"    addr={addr} (0x{addr:04X})  qty=1  "
          f"Raw frame: {hx(request)}")

    ser.reset_input_buffer()
    ser.reset_output_buffer()
    t0 = time.time()
    ser.write(request)
    ser.flush()

    expected_len = 3 + 2 + 2  # id+func+bytecount + 1 register(2 bytes) + crc(2)
    response = bytearray()
    deadline = time.time() + max(ser.timeout or 1.0, 0.5)
    while len(response) < expected_len and time.time() < deadline:
        chunk = ser.read(expected_len - len(response))
        if chunk:
            response.extend(chunk)
        else:
            break
    elapsed_ms = (time.time() - t0) * 1000.0

    if not response:
        print(f"[{_ts()}] <<< RX  (round-trip {elapsed_ms:.1f} ms)  !! No response (timeout)")
        raise ModbusError(f"No response / timeout reading addr {addr}")

    print(f"[{_ts()}] <<< RX  (round-trip {elapsed_ms:.1f} ms)  Raw frame: {hx(bytes(response))}")

    (slave_id_r, func_r, byte_count, registers,
     crc_ok, crc_rx, crc_calc) = parse_read_input_registers_response(bytes(response))

    status = "OK" if crc_ok else "MISMATCH!"
    print(f"    CRC received: {hx(crc_rx)}  CRC calculated: {hx(crc_calc)}  [{status}]")

    return {
        "raw": registers[0] if registers else None,
        "crc_ok": crc_ok,
    }


# ==========================================================================
# Register map -- taken directly from the corrected Selec_EM4M.yaml model
# file. Each entry is one independent single-register FC04 read, matching
# how EVerest's GenericPowermeter driver walks this model.
#
#   name                         addr   multiplier   confirmed?
# ==========================================================================
PARAMS = [
    # --- voltage_V -- CONFIRMED (live-captured against a 228V input) ---
    ("Voltage L1",                 1000, 0.01,  True),
    ("Voltage L2",                 1002, 0.01,  True),
    ("Voltage L3",                 1004, 0.01,  True),
    ("Voltage Avg/Total",          1006, 0.01,  True),

    # --- current_A -- UNCONFIRMED placeholder addresses ---
    ("Current L1",                 1016, 1,     False),
    ("Current L2",                 1018, 1,     False),
    ("Current L3",                 1020, 1,     False),
    ("Current Total",              1022, 1,     False),

    # --- power_W -- UNCONFIRMED placeholder addresses ---
    ("Power L1",                   1036, 1,     False),
    ("Power L2",                   1038, 1,     False),
    ("Power L3 / Total",           1040, 1,     False),  # yaml: L3 and total share addr 1040

    # --- reactive_power_VAR -- UNCONFIRMED, total only (L1/L2/L3 unavailable) ---
    ("Reactive Power Total",       1042, 0.001, False),

    # --- frequency_Hz -- UNCONFIRMED, total only (L1/L2/L3 unavailable) ---
    ("Frequency",                  1056, 1,     False),

    # --- energy_Wh_import -- UNCONFIRMED placeholder addresses ---
    ("Energy Import L1 / Total",   1076, 0.001, False),  # yaml: L1 and total share addr 1076
    ("Energy Import L2",           1078, 1,     False),
    ("Energy Import L3",           1080, 1,     False),

    # --- energy_Wh_export -- UNCONFIRMED placeholder addresses ---
    ("Energy Export L1 / Total",   1082, 0.001, False),  # yaml: L1 and total share addr 1082
    ("Energy Export L2",           1084, 1,     False),
    ("Energy Export L3",           1086, 1,     False),
]


REFERENCE_VOLTAGES = {
    "Voltage L1": 228.930,
    "Voltage L2": 229.090,
    "Voltage L3": 229.040,
    "Voltage Avg/Total": 229.020,
}


def read_all_parameters(ser, slave_id: int) -> list:
    rows = []
    for name, addr, multiplier, confirmed in PARAMS:
        try:
            result = read_single_register(ser, slave_id, addr, label=f"({name})")
            raw = result["raw"]
            scaled = raw * multiplier if raw is not None else None
            error = ""
            crc_ok = result["crc_ok"]
        except ModbusError as exc:
            raw = None
            scaled = None
            error = str(exc)
            crc_ok = False
        rows.append({
            "name": name,
            "address": addr,
            "raw": raw,
            "scaled": scaled,
            "confirmed": confirmed,
            "crc_ok": crc_ok,
            "error": error,
        })
    return rows


def run_qtp_test(port: str = "/dev/ttyCH9344USB4", baudrate: int = 9600,
                 slave_id: int = 1, timeout: float = 0.3,
                 voltage_tolerance: float = 1.0) -> dict:
    """Run the live Selec EM4M Modbus read test for QTP.

    PASS requires every configured parameter to return a response with a valid
    CRC. Confirmed voltage parameters must also match the stored reference
    values within voltage_tolerance.
    """
    ser = open_serial(port, baudrate, timeout)
    try:
        rows = read_all_parameters(ser, slave_id)
    finally:
        ser.close()

    failures = []
    voltage_results = []
    for row in rows:
        if row["error"]:
            failures.append("{}: {}".format(row["name"], row["error"]))
            continue
        if not row["crc_ok"]:
            failures.append("{}: CRC mismatch".format(row["name"]))
            continue
        reference = REFERENCE_VOLTAGES.get(row["name"])
        if reference is not None:
            delta = abs(row["scaled"] - reference)
            voltage_results.append({
                "name": row["name"],
                "measured": row["scaled"],
                "reference": reference,
                "delta": delta,
                "tolerance": voltage_tolerance,
                "pass": delta <= voltage_tolerance,
            })
            if delta > voltage_tolerance:
                failures.append(
                    "{}: {:.3f} V outside {:.3f} V +/- {:.3f} V".format(
                        row["name"], row["scaled"], reference, voltage_tolerance))

    confirmed_summary = ", ".join(
        "{}={:.3f} V".format(item["name"].replace("Voltage ", "V"), item["measured"])
        for item in voltage_results
    )
    message = (
        "Selec EM4M live Modbus read completed: {}/{} valid CRC responses; "
        "confirmed voltages: {voltages}. Unconfirmed current/power/reactive/"
        "frequency/energy values require known reference validation."
    ).format(
        sum(1 for row in rows if row["crc_ok"] and not row["error"]),
        len(rows),
        voltages=confirmed_summary,
    )
    return {
        "status": "PASS" if not failures else "FAIL",
        "message": message if not failures else message + " Failures: " + "; ".join(failures),
        "measurements": {
            "port": port,
            "baudrate": baudrate,
            "slave_id": slave_id,
            "voltage_tolerance": voltage_tolerance,
            "rows": rows,
            "voltage_results": voltage_results,
            "failures": failures,
        },
    }


def run_once(ser, slave_id: int):
    print(f"\n########## AC Energy Meter (Selec EM4M) | per-parameter read | slave ID {slave_id} ##########")
    rows = []
    for name, addr, multiplier, confirmed in PARAMS:
        print("-" * 78)
        try:
            result = read_single_register(ser, slave_id, addr, label=f"({name})")
        except ModbusError as e:
            print(f"    !! Read failed: {e}")
            rows.append((name, addr, None, None, confirmed))
            continue
        raw = result["raw"]
        scaled = raw * multiplier if raw is not None else None
        if not result["crc_ok"]:
            print("    !! WARNING: CRC mismatch - value may be corrupt.")
        rows.append((name, addr, raw, scaled, confirmed))

    print("\n" + "=" * 92)
    print(f"{'Parameter':<26}{'Addr':>6}  {'Raw(hex)':>9}  {'Raw(dec)':>9}  {'Scaled':>12}  {'Verified?'}")
    print("-" * 92)
    for name, addr, raw, scaled, confirmed in rows:
        raw_hex = f"0x{raw:04X}" if raw is not None else "  --  "
        raw_dec = f"{raw}" if raw is not None else "--"
        scaled_s = f"{scaled:.3f}" if scaled is not None else "--"
        verified = "CONFIRMED" if confirmed else "unconfirmed"
        print(f"{name:<26}{addr:>6}  {raw_hex:>9}  {raw_dec:>9}  {scaled_s:>12}  {verified}")
    print("=" * 92)
    print("NOTE: only the Voltage rows are verified against a live known-input\n"
          "      test. All other addresses are placeholders carried over from\n"
          "      Selec_EM4M.yaml and still need the same kind of live\n"
          "      confirmation (known load / known current / known power) before\n"
          "      the values should be trusted.")


def main():
    ap = argparse.ArgumentParser(
        description="Read AC Energy Meter (Selec EM4M) parameters one register at a time, per Selec_EM4M.yaml"
    )
    ap.add_argument("--port", default="/dev/ttyCH9344USB4", help="Serial port (default: /dev/ttyCH9344USB4)")
    ap.add_argument("--baud", type=int, default=9600, help="Baud rate (default: 9600)")
    ap.add_argument("--slave", type=int, default=1, help="Slave/Address ID (default: 1)")
    ap.add_argument("--timeout", type=float, default=1.0, help="Serial read timeout in seconds")
    ap.add_argument("--loop", action="store_true", help="Continuously poll instead of a single pass")
    ap.add_argument("--interval", type=float, default=2.0, help="Seconds between polls in --loop mode")
    args = ap.parse_args()

    print(f"Opening serial port {args.port} @ {args.baud} 8N1 ...")
    try:
        ser = open_serial(args.port, args.baud, args.timeout)
    except Exception as e:
        print(f"!! Could not open serial port {args.port}: {e}")
        sys.exit(1)

    try:
        if args.loop:
            while True:
                run_once(ser, args.slave)
                time.sleep(args.interval)
        else:
            run_once(ser, args.slave)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
