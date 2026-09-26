"""4G QMI network verification helper."""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
from datetime import datetime


IP_RE = re.compile(r"inet addr:(\d+\.\d+\.\d+\.\d+)|inet\s+(\d+\.\d+\.\d+\.\d+)")


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


def run_command(cmd, timeout=30, shell=False):
    printable = cmd if isinstance(cmd, str) else " ".join(cmd)
    print("$ " + printable)
    completed = subprocess.run(
        cmd,
        shell=shell,
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


def write_qmi_config(path, apn, ip_type, proxy):
    content = "APN={}\nIP_TYPE={}\nPROXY={}\n".format(apn, ip_type, proxy)
    print("Writing {}".format(path))
    print(content.rstrip())
    with open(path, "w", encoding="utf-8") as config_file:
        config_file.write(content)


def extract_ip(ifconfig_output):
    match = IP_RE.search(ifconfig_output)
    if not match:
        return ""
    return match.group(1) or match.group(2) or ""


def format_table(rows):
    lines = [
        "Step                         Status  Details",
        "------------------------------------------------------------",
    ]
    for row in rows:
        lines.append("{step:<28} {status:<7} {details}".format(**row))
    return "\n".join(lines)


def add_row(rows, failures, step, ok, details, failure_text=None):
    rows.append({"step": step, "status": "PASS" if ok else "FAIL", "details": details})
    if not ok:
        failures.append(failure_text or "{} failed".format(step))


def run_qtp_test(interface, qmi_device, apn, config_path, ping_host, ping_count):
    log_path = make_target_log_path("TC-08_4G_Network_Verification")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    rows = []
    failures = []
    ip_address = ""

    with open(log_path, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(Tee(os.sys.stdout, log_file)):
            print("4G network verification")
            print("Interface={} QMI device={} APN={}".format(interface, qmi_device, apn))

            write_qmi_config(config_path, apn, 4, "yes")
            add_row(rows, failures, "Write QMI config", True, config_path)

            run_command(["ifconfig", interface, "down"], timeout=10)
            add_row(rows, failures, "Interface down", True, interface)

            raw_ip_path = "/sys/class/net/{}/qmi/raw_ip".format(interface)
            try:
                with open(raw_ip_path, "w", encoding="utf-8") as raw_ip_file:
                    raw_ip_file.write("Y\n")
                add_row(rows, failures, "Enable raw IP", True, raw_ip_path)
            except OSError as exc:
                add_row(rows, failures, "Enable raw IP", False, str(exc))

            code, _ = run_command(["ifconfig", interface, "up"], timeout=10)
            add_row(rows, failures, "Interface up", code == 0, interface)

            code, start_output = run_command(["qmi-network", qmi_device, "start"], timeout=45)
            first_start_ok = code == 0 and "Network started successfully" in start_output
            add_row(rows, failures, "QMI start", first_start_ok, qmi_device)

            code, stop_output = run_command(["qmi-network", qmi_device, "stop"], timeout=45)
            stop_ok = code == 0 and "Network stopped successfully" in stop_output
            add_row(rows, failures, "QMI stop", stop_ok, qmi_device)

            code, restart_output = run_command(["qmi-network", qmi_device, "start"], timeout=45)
            restart_ok = code == 0 and "Network started successfully" in restart_output
            add_row(rows, failures, "QMI restart", restart_ok, qmi_device)

            code, dhcp_output = run_command(
                ["udhcpc", "-i", interface, "-s", "/usr/share/udhcpc/default.script"],
                timeout=60,
            )
            dhcp_ok = code == 0 and "lease of" in dhcp_output and "obtained" in dhcp_output
            add_row(rows, failures, "DHCP lease", dhcp_ok, interface)

            code, ifconfig_output = run_command(["ifconfig", interface], timeout=10)
            ip_address = extract_ip(ifconfig_output)
            add_row(rows, failures, "Interface IP", code == 0 and bool(ip_address), ip_address or "No IPv4 address")

            code, ping_output = run_command(
                ["ping", "-I", interface, "-c", str(ping_count), ping_host],
                timeout=45,
            )
            ping_ok = code == 0 and "bytes from" in ping_output
            add_row(rows, failures, "Ping", ping_ok, "{} via {}".format(ping_host, interface))

            print("Target full log saved: {}".format(log_path))

    status = "PASS" if rows and not failures else "FAIL"
    message = "Target full log saved: {}".format(log_path)
    if ip_address:
        message += "\n4G IP address: {}".format(ip_address)
    if failures:
        message += "\n\nFailures:\n- " + "\n- ".join(failures)
    return {
        "status": status,
        "message": message,
        "measurements": {
            "table": format_table(rows),
            "target_log": log_path,
            "ip_address": ip_address,
            "rows": rows,
        },
    }
