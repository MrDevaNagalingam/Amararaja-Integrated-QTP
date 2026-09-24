import contextlib
import os
import sys
from datetime import datetime

import can_controller_node
import can_setup
import config


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


def _csv_path():
    if os.path.isabs(config.CAN_DBC_PATH):
        return config.CAN_DBC_PATH
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), config.CAN_DBC_PATH)


def _open_controller():
    db = can_setup.load_db(_csv_path())
    bus = can_setup.open_bus(
        channel=config.CAN_CHANNEL,
        bustype=config.CAN_BUSTYPE,
        bitrate=config.CAN_BITRATE,
        auto_configure=config.CAN_AUTO_CONFIGURE,
        restart_ms=config.CAN_RESTART_MS,
    )
    return can_controller_node.Controller(db, bus, verbose=True)


def _format_table(action, params, log_path):
    lines = [
        "{:<26}  {}".format("Field", "Value"),
        "-" * 60,
        "{:<26}  {}".format("Action", action),
        "{:<26}  {}".format("CAN Channel", config.CAN_CHANNEL),
        "{:<26}  {}".format("Bitrate", config.CAN_BITRATE),
    ]
    for key in sorted(params):
        lines.append("{:<26}  {}".format(key, params[key]))
    lines.append("{:<26}  {}".format("Target Log", log_path))
    return "\n".join(lines)


def run_qtp_command(action, params=None):
    params = params or {}
    normalized = action.strip().lower()
    names = {
        "start_all": "TC-04_CAN_Controller_Node_Start_All",
        "stop_all": "TC-04_CAN_Controller_Node_Stop_All",
        "set_all": "TC-04_CAN_Controller_Node_Set_All",
        "start": "TC-04_CAN_Controller_Node_Start",
        "stop": "TC-04_CAN_Controller_Node_Stop",
    }
    if normalized not in names:
        return {"status": "ERROR", "message": "Unsupported CAN controller action: " + action}

    log_path = make_target_log_path(names[normalized])
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(Tee(sys.stdout, log_file)):
            print("CAN Controller QTP action: {}".format(normalized))
            print("Channel={} Bustype={} Bitrate={}".format(
                config.CAN_CHANNEL, config.CAN_BUSTYPE, config.CAN_BITRATE))
            controller = _open_controller()
            controller._send("C_M_3", {"Reserved_Standby": 0}, "CYCLIC")
            group = int(params.get("group", config.CAN_DEFAULT_GROUP))
            voltage = float(params.get("voltage", config.CAN_DEFAULT_VOLTAGE))
            current = float(params.get("current", config.CAN_DEFAULT_CURRENT))
            address = int(params.get("address", config.CAN_DEFAULT_MODULE_ADDRESS))

            command_params = {}
            if normalized == "start_all":
                command_params = {"group": group}
                controller.start_all(group)
            elif normalized == "stop_all":
                command_params = {"group": group}
                controller.stop_all(group)
            elif normalized == "set_all":
                command_params = {"group": group, "voltage": voltage, "current": current}
                controller.set_all_params(voltage, current, group)
            elif normalized == "start":
                command_params = {"address": address, "voltage": voltage, "current": current}
                controller.start_module(address, voltage, current)
            elif normalized == "stop":
                command_params = {"address": address}
                controller.stop_module(address)
            print("Target full log saved: {}".format(log_path))

    table = _format_table(normalized, command_params, log_path)
    return {
        "status": "PASS",
        "message": "Target full log saved: {}".format(log_path),
        "measurements": {
            "table": table,
            "target_log": log_path,
            "action": normalized,
            "params": command_params,
        },
    }
