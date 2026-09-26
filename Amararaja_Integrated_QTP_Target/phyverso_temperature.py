"""Phyverso CLI temperature sensor QTP helper."""

from __future__ import annotations

import contextlib
import os
import re
import select
import subprocess
import sys
import time
from datetime import datetime


GUN_TEMP_RE = re.compile(
    r"(Gun[12])\s+(Negative \(N\)|Positive \(P\))\s+Temperature:\s+(-?\d+(?:\.\d+)?)\s*C",
    re.IGNORECASE,
)
CONNECTOR_RE = re.compile(r"Connector\s*:\s*(\d+)", re.IGNORECASE)
GET_TEMP_RE = re.compile(r"get_temp\(\)\s*:\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)


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
        "Sensor                         Temperature(C)  Status",
        "-------------------------------------------------------",
    ]
    for row in rows:
        lines.append("{sensor:<30} {temperature:>14}  {status}".format(**row))
    return "\n".join(lines)


def parse_temperatures(output):
    rows = []
    for match in GUN_TEMP_RE.finditer(output):
        sensor = "{} {}".format(match.group(1), match.group(2))
        value = float(match.group(3))
        rows.append({
            "sensor": sensor,
            "temperature": "{:.2f}".format(value),
            "status": "PASS" if value > -9.0 else "NO SENSOR",
            "value": value,
        })

    if rows:
        return rows

    current_connector = None
    connector_counts = {}
    for line in output.splitlines():
        connector_match = CONNECTOR_RE.search(line)
        if connector_match:
            current_connector = connector_match.group(1)
            connector_counts.setdefault(current_connector, 0)
            continue
        temp_match = GET_TEMP_RE.search(line)
        if temp_match and current_connector is not None:
            connector_counts[current_connector] = connector_counts.get(current_connector, 0) + 1
            value = float(temp_match.group(1))
            rows.append({
                "sensor": "Connector {} Temp {}".format(current_connector, connector_counts[current_connector]),
                "temperature": "{:.2f}".format(value),
                "status": "PASS" if value > -9.0 else "NO SENSOR",
                "value": value,
            })
    return rows


def run_phyverso_cli(cli_path, serial_port, config_path, command, startup_wait, read_timeout):
    cmd = [cli_path, serial_port, config_path]
    print("$ " + " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=0,
    )
    output_parts = []
    deadline = time.time() + read_timeout
    command_sent = False
    try:
        while time.time() < deadline:
            readable, _, _ = select.select([proc.stdout], [], [], 0.2)
            if readable:
                chunk = proc.stdout.read(1)
                if chunk:
                    output_parts.append(chunk)
                    print(chunk, end="")
            if not command_sent and time.time() >= deadline - read_timeout + startup_wait:
                print("\nSending temperature command: {}".format(command))
                proc.stdin.write(command)
                proc.stdin.flush()
                command_sent = True
            if command_sent and "Temperature:" in "".join(output_parts):
                time.sleep(0.5)
                while True:
                    readable, _, _ = select.select([proc.stdout], [], [], 0)
                    if not readable:
                        break
                    chunk = proc.stdout.read(1)
                    if not chunk:
                        break
                    output_parts.append(chunk)
                    print(chunk, end="")
                break
            if command_sent and len(parse_temperatures("".join(output_parts))) >= 4:
                break
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
        print("")
    return "".join(output_parts)


def run_qtp_test(cli_path, serial_port, config_path, command="T", startup_wait=2.0, read_timeout=12.0):
    log_path = make_target_log_path("TC-07_PT1000_Thermistor_10k_Temperature_Sensor")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    rows = []
    failures = []
    with open(log_path, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(Tee(sys.stdout, log_file)):
            print("PT1000/Thermistor-10k Temperature Sensor QTP")
            print("CLI={} Serial={} Config={}".format(cli_path, serial_port, config_path))
            output = run_phyverso_cli(cli_path, serial_port, config_path, command, startup_wait, read_timeout)
            rows = parse_temperatures(output)
            if not rows:
                failures.append("Temperature readings were not found in phyverso_cli output")
            elif not any(row["status"] == "PASS" for row in rows):
                failures.append("No valid sensor temperature detected; check PT1000/Thermistor-10k connection")
            print("Target full log saved: {}".format(log_path))

    status = "PASS" if rows and not failures else "FAIL"
    message = "Target full log saved: {}".format(log_path)
    if failures:
        message += "\n\nFailures:\n- " + "\n- ".join(failures)
    return {
        "status": status,
        "message": message,
        "measurements": {
            "table": format_table(rows) if rows else "",
            "target_log": log_path,
            "rows": rows,
        },
    }
