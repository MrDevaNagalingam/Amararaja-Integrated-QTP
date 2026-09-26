"""Relay control QTP helper for MCU coil-control firmware."""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import serial
except ImportError:
    serial = None


RELAY_ACTIONS = {
    "all_on": {"command": "0", "title": "Relay Control All OFF", "expected": "ALL ON"},
    "dc1_on": {"command": "1", "title": "Relay Control DC1 ON", "expected": "DC1 ON"},
    "dc2_on": {"command": "2", "title": "Relay Control DC2 ON", "expected": "DC2 ON"},
    "ac_on": {"command": "3", "title": "Relay Control AC ON", "expected": "AC ON"},
    "merger_on": {"command": "4", "title": "Relay Control MERGER ON", "expected": "MERGER ON"},
}


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


def format_table(rows):
    lines = [
        "Step                         Status  Details",
        "------------------------------------------------------------",
    ]
    for row in rows:
        lines.append("{step:<28} {status:<7} {details}".format(**row))
    return "\n".join(lines)


def run_process(cmd, timeout, cwd=None):
    print("$ " + " ".join(cmd))
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        timeout=timeout,
        check=False,
    )
    output = completed.stdout or ""
    if output:
        print(output.rstrip())
    return completed.returncode, output


def flash_firmware(flasher, serial_port, image_path, timeout, cwd=None):
    code, output = run_process([flasher, "flash", serial_port, image_path], timeout, cwd=cwd)
    programmed = "Programmed: 1" in output
    verified = "Verified: 1" in output or "Verified programmed data" in output
    started = "Started: 1" in output or "Starting application" in output
    already_current = "Already up-to-date" in output
    failed = any(text in output for text in (
        "Could not connect",
        "Stopping...",
        "Failed",
        "failed",
        "ERROR",
        "Error",
    ))
    ok = code == 0 and not failed and verified and started and (programmed or already_current)
    if ok and already_current and not programmed:
        summary = "Already up-to-date; verified and started"
    elif ok:
        summary = "Programmed, verified, and started"
    elif failed:
        summary = "Flasher reported failure"
    else:
        summary = "Flasher output did not confirm success"
    return ok, output, summary


def send_relay_command(serial_port, baudrate, command, expected, timeout):
    if serial is None:
        raise RuntimeError("pyserial is required for live relay UART control")
    print("Opening MCU UART {} @ {} 8N1 ...".format(serial_port, baudrate))
    response = bytearray()
    with serial.Serial(serial_port, baudrate, timeout=0.2) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print("[DEBUG] Sending relay command: {!r} (0x{:02X})".format(command, ord(command)))
        written = ser.write(command.encode("ascii"))
        ser.flush()
        print("Sent command: {} (wrote {} byte successfully)".format(command, written))
        deadline = time.time() + timeout
        while time.time() < deadline:
            chunk = ser.read(256)
            if chunk:
                response.extend(chunk)
                decoded = chunk.decode(errors="replace")
                print(decoded, end="" if decoded.endswith("\n") else "\n")
                if expected in response.decode(errors="replace"):
                    break
    text = response.decode(errors="replace")
    return expected in text, text


def run_qtp_test(action, serial_port, baudrate, uart_timeout=5):
    if action not in RELAY_ACTIONS:
        return {"status": "ERROR", "message": "Unsupported relay action: " + action}

    action_info = RELAY_ACTIONS[action]
    test_name = "TC-12_" + action_info["title"].replace(" ", "_")
    log_path = make_target_log_path(test_name)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    rows = []
    failures = []

    with open(log_path, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(Tee(sys.stdout, log_file)):
            print("Relay Control QTP action: {}".format(action_info["title"]))
            print("Serial={} Baudrate={}".format(serial_port, baudrate))
            uart_ok, response = send_relay_command(
                serial_port, baudrate, action_info["command"], action_info["expected"], uart_timeout)
            rows.append({
                "step": "Send relay command",
                "status": "PASS" if uart_ok else "FAIL",
                "details": "{} -> {}".format(action_info["command"], action_info["expected"]),
            })
            if not uart_ok:
                failures.append("MCU response did not contain expected text: " + action_info["expected"])
                failures.append("Check the flashed MCU binary to Test relay")
            print("Target full log saved: {}".format(log_path))

    status = "PASS" if rows and not failures else "FAIL"
    message = "Target full log saved: {}".format(log_path)
    if failures:
        message += "\n\nFailures:\n- " + "\n- ".join(failures)
    return {
        "status": status,
        "message": message,
        "measurements": {
            "table": "",
            "target_log": log_path,
            "rows": rows,
        },
    }


def run_flash_test(image_name, serial_port, flasher, coil_bin, default_bin, flash_timeout=90):
    images = {
        "default": {
            "title": "Flash Phytec_MSP_DC.bin binary",
            "path": default_bin,
        },
        "coil": {
            "title": "Flash Coil_Control.bin binary",
            "path": coil_bin,
        },
    }
    if image_name not in images:
        return {"status": "ERROR", "message": "Unsupported MCU flash image: " + image_name}
    image = images[image_name]
    image_path = str(Path(image["path"]))
    test_name = image["title"].replace(" ", "_").replace(".", "_")
    log_path = make_target_log_path(test_name)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    rows = []
    failures = []
    cwd = str(Path(image_path).resolve().parent) if image_name == "coil" else None
    with open(log_path, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(Tee(sys.stdout, log_file)):
            print("MCU Flash QTP action: {}".format(image["title"]))
            print("Serial={}".format(serial_port))
            print("Firmware image: {}".format(image_path))
            ok, _, summary = flash_firmware(flasher, serial_port, image_path, flash_timeout, cwd=cwd)
            rows.append({
                "step": "Flash firmware",
                "status": "PASS" if ok else "FAIL",
                "details": "{} ({})".format(image_path, summary),
            })
            if not ok:
                failures.append("Firmware flash failed: " + image_path)
            print("Target full log saved: {}".format(log_path))
    status = "PASS" if rows and not failures else "FAIL"
    message = "Target full log saved: {}".format(log_path)
    if failures:
        message += "\n\nFailures:\n- " + "\n- ".join(failures)
    return {
        "status": status,
        "message": message,
        "measurements": {
            "table": "",
            "target_log": log_path,
            "rows": rows,
        },
    }
