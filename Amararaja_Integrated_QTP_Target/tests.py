"""QTP target tests."""

import contextlib
import os
import sys
import time
from datetime import datetime

import config
import selec_EM4M
import edc2150
import imd_read
import can_controller_qtp
import relay_control
import phyverso_temperature
import network_4g

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


def imd1(params):
    device_config = dict(imd_read.IMD1_CONFIG)
    device_config["undervoltage_alarm_threshold_V"] = config.IMD1_UNDERVOLTAGE_ALARM_THRESHOLD_V
    device_config["overvoltage_alarm_threshold_V"] = config.IMD1_OVERVOLTAGE_ALARM_THRESHOLD_V
    return imd_read.run_qtp_test(
        test_name="TC-04_Read_IMD_1",
        port=params.get("port", config.IMD1_PORT),
        baudrate=int(params.get("baudrate", config.IMD1_BAUDRATE)),
        parity=params.get("parity", config.IMD1_PARITY),
        slave_id=int(params.get("slave_id", config.IMD1_SLAVE_ID)),
        timeout=float(params.get("timeout", config.IMD1_TIMEOUT)),
        device_config=device_config,
    )


def imd2(params):
    device_config = dict(imd_read.IMD2_CONFIG)
    device_config["undervoltage_alarm_threshold_V"] = config.IMD2_UNDERVOLTAGE_ALARM_THRESHOLD_V
    device_config["overvoltage_alarm_threshold_V"] = config.IMD2_OVERVOLTAGE_ALARM_THRESHOLD_V
    return imd_read.run_qtp_test(
        test_name="TC-04_Read_IMD_2",
        port=params.get("port", config.IMD2_PORT),
        baudrate=int(params.get("baudrate", config.IMD2_BAUDRATE)),
        parity=params.get("parity", config.IMD2_PARITY),
        slave_id=int(params.get("slave_id", config.IMD2_SLAVE_ID)),
        timeout=float(params.get("timeout", config.IMD2_TIMEOUT)),
        device_config=device_config,
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


def can_keep_alive_start(params):
    return can_controller_qtp.start_keep_alive(params)


def can_keep_alive_stop(params):
    return can_controller_qtp.stop_keep_alive(params)


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
    log_path = make_target_log_path("TC-06_RFID_Verification")
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


def temperature_sensor(params):
    return phyverso_temperature.run_qtp_test(
        cli_path=params.get("cli_path", config.PHYVERSO_CLI),
        serial_port=params.get("serial_port", config.TEMP_SENSOR_SERIAL_PORT),
        config_path=params.get("config_path", config.PHYVERSO_CONFIG_PATH),
        command=params.get("command", config.TEMP_SENSOR_COMMAND),
        startup_wait=float(params.get("startup_wait", config.TEMP_SENSOR_STARTUP_WAIT)),
        read_timeout=float(params.get("read_timeout", config.TEMP_SENSOR_READ_TIMEOUT)),
    )


def network_4g_test(params):
    return network_4g.run_qtp_test(
        interface=params.get("interface", config.FOURG_INTERFACE),
        qmi_device=params.get("qmi_device", config.FOURG_QMI_DEVICE),
        apn=params.get("apn", config.FOURG_APN),
        config_path=params.get("config_path", config.FOURG_QMI_CONFIG),
        ping_host=params.get("ping_host", config.FOURG_PING_HOST),
        ping_count=int(params.get("ping_count", config.FOURG_PING_COUNT)),
    )


def run_relay_control(action, params):
    return relay_control.run_qtp_test(
        action=action,
        serial_port=params.get("serial_port", config.RELAY_MCU_SERIAL_PORT),
        baudrate=int(params.get("baudrate", config.RELAY_MCU_BAUDRATE)),
        uart_timeout=float(params.get("uart_timeout", config.RELAY_UART_TIMEOUT)),
    )


def relay_control_on_all(params):
    return run_relay_control("all_on", params)


def relay_control_dc1_on(params):
    return run_relay_control("dc1_on", params)


def relay_control_dc2_on(params):
    return run_relay_control("dc2_on", params)


def relay_control_ac_on(params):
    return run_relay_control("ac_on", params)


def relay_control_merger_on(params):
    return run_relay_control("merger_on", params)


def run_flash_binary(image_name, params):
    return relay_control.run_flash_test(
        image_name=image_name,
        serial_port=params.get("serial_port", config.RELAY_MCU_SERIAL_PORT),
        flasher=params.get("flasher", config.RELAY_FLASHER),
        coil_bin=params.get("coil_bin", config.RELAY_COIL_CONTROL_BIN),
        default_bin=params.get("default_bin", config.RELAY_DEFAULT_BIN),
        flash_timeout=float(params.get("flash_timeout", config.RELAY_FLASH_TIMEOUT)),
    )


def flash_phytec_msp_dc(params):
    return run_flash_binary("default", params)


def flash_coil_control(params):
    return run_flash_binary("coil", params)


TESTS = {
    "PING": ping,
    "ECHO": echo,
    "SELEC_EM4M": selec_em4m,
    "EDC2150": edc2150_meter,
    "IMD1": imd1,
    "IMD2": imd2,
    "CAN_CONTROLLER_START_ALL": can_controller_start_all,
    "CAN_CONTROLLER_STOP_ALL": can_controller_stop_all,
    "CAN_CONTROLLER_SET_ALL": can_controller_set_all,
    "CAN_CONTROLLER_START": can_controller_start,
    "CAN_CONTROLLER_STOP": can_controller_stop,
    "CAN_KEEP_ALIVE_START": can_keep_alive_start,
    "CAN_KEEP_ALIVE_STOP": can_keep_alive_stop,
    "RFID": rfid,
    "TEMPERATURE_SENSOR": temperature_sensor,
    "NETWORK_4G": network_4g_test,
    "RELAY_CONTROL_ALL_OFF": relay_control_on_all,
    "RELAY_CONTROL_DC1_ON": relay_control_dc1_on,
    "RELAY_CONTROL_DC2_ON": relay_control_dc2_on,
    "RELAY_CONTROL_AC_ON": relay_control_ac_on,
    "RELAY_CONTROL_MERGER_ON": relay_control_merger_on,
    "FLASH_PHYTEC_MSP_DC": flash_phytec_msp_dc,
    "FLASH_COIL_CONTROL": flash_coil_control,
}
