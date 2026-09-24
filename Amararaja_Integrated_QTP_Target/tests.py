"""QTP target tests."""

import contextlib
import os
import sys
import time
from datetime import datetime

import config
import selec_EM4M
import edc2150
import can_controller_qtp

try:
    import serial
except ImportError:
    serial = None

def ping(params):
    return {"status": "PASS", "message": "PONG - target received command"}


def echo(params):
    text = params.get("text", "")
    if not isinstance(text, str) or len(text.encode("utf-8")) > 16000:
        return {"status": "ERROR", "message": "Echo requires text up to 16000 UTF-8 bytes"}
    return {"status": "PASS", "message": text}


def selec_em4m(params):
    return selec_EM4M.run_qtp_test(
        port=params.get("port", config.SELEC_EM4M_PORT),
        baudrate=int(params.get("baudrate", config.SELEC_EM4M_BAUDRATE)),
        slave_id=int(params.get("slave_id", config.SELEC_EM4M_SLAVE_ID)),
        timeout=float(params.get("timeout", config.SELEC_EM4M_TIMEOUT)),
        voltage_tolerance=float(params.get("voltage_tolerance", config.SELEC_EM4M_VOLTAGE_TOLERANCE)),
    )


def edc2150_meter(params):
    return edc2150.run_qtp_test(
        port=params.get("port", config.EDC2150_PORT),
        baudrate=int(params.get("baudrate", config.EDC2150_BAUDRATE)),
        slave_id=int(params.get("slave_id", config.EDC2150_SLAVE_ID)),
        timeout=float(params.get("timeout", config.EDC2150_TIMEOUT)),
    )


def can_controller_start_all(params):
    return can_controller_qtp.run_qtp_command("start_all", params)


def can_controller_stop_all(params):
    return can_controller_qtp.run_qtp_command("stop_all", params)


def can_controller_set_all(params):
    return can_controller_qtp.run_qtp_command("set_all", params)


def can_controller_start(params):
    return can_controller_qtp.run_qtp_command("start", params)


def can_controller_stop(params):
    return can_controller_qtp.run_qtp_command("stop", params)


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


def parse_rfid_get_serial_response(resp):
    if len(resp) < 12:
        return {"status": "FAIL", "serial_hex": "", "message": "Response too short"}
    if resp[0:5] != bytes.fromhex("02 00 07 34 31"):
        return {"status": "FAIL", "serial_hex": "", "message": "Unexpected frame header"}
    status_byte = resp[5]
    card_serial = resp[6:10]
    if status_byte == 0x59:
        return {
            "status": "PASS",
            "serial_hex": card_serial.hex(" ").upper(),
            "message": "Card serial number read successfully",
        }
    if status_byte == 0x4E:
        return {"status": "FAIL", "serial_hex": "", "message": "No card serial number returned"}
    return {
        "status": "FAIL",
        "serial_hex": "",
        "message": "Unexpected operation status byte 0x{:02X}".format(status_byte),
    }


def rfid(params):
    if serial is None:
        raise RuntimeError("pyserial is required for live RFID serial reads")
    port = params.get("port", config.RFID_PORT)
    baudrate = int(params.get("baudrate", config.RFID_BAUDRATE))
    timeout = float(params.get("timeout", config.RFID_TIMEOUT))
    command = bytes.fromhex(params.get("command_hex", config.RFID_COMMAND_HEX))
    attempts = int(params.get("attempts", config.RFID_ATTEMPTS))
    interval = float(params.get("interval", config.RFID_INTERVAL))
    read_size = int(params.get("read_size", config.RFID_READ_SIZE))
    log_path = make_target_log_path("TC-05_RFID_Verification")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    detected = None
    with open(log_path, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(Tee(sys.stdout, log_file)):
            print("Opening serial port {} @ {} 8N1 ...".format(port, baudrate))
            print("RFID GET_SERIAL TX: {}".format(command.hex(" ")))
            ser = serial.Serial(port, baudrate, timeout=timeout)
            try:
                for attempt in range(1, attempts + 1):
                    ser.write(command)
                    resp = ser.read(read_size)
                    if resp:
                        print("RX: {}".format(resp.hex(" ")))
                        parsed = parse_rfid_get_serial_response(resp)
                        if parsed["status"] == "PASS":
                            detected = {
                                "attempt": attempt,
                                "rx_hex": resp.hex(" "),
                                "serial_hex": parsed["serial_hex"],
                                "message": parsed["message"],
                            }
                            break
                    else:
                        print("RX: <timeout>")
                    time.sleep(interval)
            finally:
                ser.close()
            if detected:
                print("Card detected: {}".format(detected["serial_hex"]))
            else:
                print("Card serial number not detected")
            print("Target full log saved: {}".format(log_path))
    if detected:
        table = "Card Serial Number  {}\nDetected Attempt    {}".format(
            detected["serial_hex"], detected["attempt"])
        return {
            "status": "PASS",
            "message": "Target full log saved: {}".format(log_path),
            "measurements": {
                "table": table,
                "target_log": log_path,
                "card_serial": detected["serial_hex"],
                "attempt": detected["attempt"],
            },
        }
    return {
        "status": "FAIL",
        "message": "Target full log saved: {}\n\nFailures:\n- RFID card serial number was not read successfully".format(log_path),
        "measurements": {"target_log": log_path},
    }


TESTS = {
    "PING": ping,
    "ECHO": echo,
    "SELEC_EM4M": selec_em4m,
    "EDC2150": edc2150_meter,
    "CAN_CONTROLLER_START_ALL": can_controller_start_all,
    "CAN_CONTROLLER_STOP_ALL": can_controller_stop_all,
    "CAN_CONTROLLER_SET_ALL": can_controller_set_all,
    "CAN_CONTROLLER_START": can_controller_start,
    "CAN_CONTROLLER_STOP": can_controller_stop,
    "RFID": rfid,
}
