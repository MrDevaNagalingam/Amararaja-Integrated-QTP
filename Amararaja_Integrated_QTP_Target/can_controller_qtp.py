import contextlib
import os
import sys
import threading
import time
from datetime import datetime

import can_controller_node
import can_setup
import config


_keep_alive_lock = threading.Lock()
_keep_alive_state = {
    "running": False,
    "stop_event": None,
    "thread": None,
    "controller": None,
    "channel": None,
    "bitrate": None,
    "log_path": None,
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


def _csv_path():
    if os.path.isabs(config.CAN_DBC_PATH):
        return config.CAN_DBC_PATH
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), config.CAN_DBC_PATH)


def _open_controller(channel, bitrate):
    db = can_setup.load_db(_csv_path())
    bus = can_setup.open_bus(
        channel=channel,
        bustype=config.CAN_BUSTYPE,
        bitrate=bitrate,
        auto_configure=config.CAN_AUTO_CONFIGURE,
        restart_ms=config.CAN_RESTART_MS,
    )
    return can_controller_node.Controller(db, bus, verbose=True)


def _format_table(action, params, log_path, channel, bitrate):
    lines = [
        "{:<26}  {}".format("Field", "Value"),
        "-" * 60,
        "{:<26}  {}".format("Action", action),
        "{:<26}  {}".format("CAN Channel", channel),
        "{:<26}  {}".format("Bitrate", bitrate),
    ]
    for key in sorted(params):
        lines.append("{:<26}  {}".format(key, params[key]))
    lines.append("{:<26}  {}".format("Target Log", log_path))
    return "\n".join(lines)



def _close_controller(controller):
    if controller is None:
        return
    try:
        controller.stop_event.set()
    except Exception:
        pass
    bus = getattr(controller, "bus", None)
    shutdown = getattr(bus, "shutdown", None)
    close = getattr(bus, "close", None)
    sock = getattr(bus, "sock", None)
    try:
        if callable(shutdown):
            shutdown()
        elif callable(close):
            close()
        elif sock is not None:
            sock.close()
    except Exception:
        pass


def _append_keep_alive_log(message):
    log_path = _keep_alive_state.get("log_path")
    if not log_path:
        return
    try:
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(message + "\n")
    except OSError:
        pass


def _keep_alive_loop(stop_event, controller):
    while not stop_event.is_set():
        try:
            controller._send("C_M_3", {"Reserved_Standby": 0}, "CYCLIC")
            _append_keep_alive_log("{} [Controller] TX-CYCLIC   C_M_3: {{'Reserved_Standby': 0}}".format(
                datetime.now().strftime("%H:%M:%S.%f")[:-3]))
        except Exception as exc:
            message = "CAN keep alive send error: {}".format(exc)
            print(message)
            _append_keep_alive_log(message)
        stop_event.wait(float(getattr(config, "CAN_KEEP_ALIVE_INTERVAL", 5.0)))


def start_keep_alive(params=None):
    params = params or {}
    channel = params.get("channel", config.CAN_CHANNEL)
    bitrate = int(params.get("bitrate", config.CAN_BITRATE))
    with _keep_alive_lock:
        if _keep_alive_state["running"]:
            return {
                "status": "PASS",
                "message": "CAN keep alive already running; target full log saved: {}".format(_keep_alive_state["log_path"]),
                "measurements": {"target_log": _keep_alive_state["log_path"]},
            }
        log_path = make_target_log_path("TC-05_CAN_Controller_Keep_Alive_Start")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write("CAN Controller QTP action: keep_alive_start\n")
            log_file.write("Channel={} Bustype={} Bitrate={}\n".format(channel, config.CAN_BUSTYPE, bitrate))
            log_file.write("Keep alive interval: {} seconds\n".format(float(getattr(config, "CAN_KEEP_ALIVE_INTERVAL", 5.0))))
        print("CAN Controller QTP action: keep_alive_start")
        print("Channel={} Bustype={} Bitrate={}".format(channel, config.CAN_BUSTYPE, bitrate))
        controller = _open_controller(channel, bitrate)
        stop_event = threading.Event()
        thread = threading.Thread(target=_keep_alive_loop, args=(stop_event, controller), daemon=True)
        _keep_alive_state.update({
            "running": True,
            "stop_event": stop_event,
            "thread": thread,
            "controller": controller,
            "channel": channel,
            "bitrate": bitrate,
            "log_path": log_path,
        })
        thread.start()
    print("Target full log saved: {}".format(log_path))
    return {
        "status": "PASS",
        "message": "CAN keep alive started; target full log saved: {}".format(log_path),
        "measurements": {"target_log": log_path},
    }


def stop_keep_alive(params=None):
    with _keep_alive_lock:
        if not _keep_alive_state["running"]:
            return {
                "status": "PASS",
                "message": "CAN keep alive was not running",
            }
        stop_event = _keep_alive_state["stop_event"]
        thread = _keep_alive_state["thread"]
        controller = _keep_alive_state["controller"]
        channel = _keep_alive_state["channel"]
        bitrate = _keep_alive_state["bitrate"]
        log_path = _keep_alive_state["log_path"]
        stop_event.set()
    if thread is not None:
        thread.join(timeout=2.0)
    _close_controller(controller)
    _append_keep_alive_log("CAN keep alive stopped")
    with _keep_alive_lock:
        _keep_alive_state.update({
            "running": False,
            "stop_event": None,
            "thread": None,
            "controller": None,
            "channel": None,
            "bitrate": None,
            "log_path": None,
        })
    print("CAN Controller QTP action: keep_alive_stop")
    print("Target full log saved: {}".format(log_path))
    return {
        "status": "PASS",
        "message": "CAN keep alive stopped; target full log saved: {}".format(log_path),
        "measurements": {"target_log": log_path},
    }


def run_qtp_command(action, params=None):
    params = params or {}
    normalized = action.strip().lower()
    names = {
        "start_all": "TC-05_CAN_Controller_Node_Start_All",
        "stop_all": "TC-05_CAN_Controller_Node_Stop_All",
        "set_all": "TC-05_CAN_Controller_Node_Set_All",
        "start": "TC-05_CAN_Controller_Node_Start",
        "stop": "TC-05_CAN_Controller_Node_Stop",
    }
    if normalized not in names:
        return {"status": "ERROR", "message": "Unsupported CAN controller action: " + action}

    channel = params.get("channel", config.CAN_CHANNEL)
    bitrate = int(params.get("bitrate", config.CAN_BITRATE))
    log_path = make_target_log_path(names[normalized])
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(Tee(sys.stdout, log_file)):
            print("CAN Controller QTP action: {}".format(normalized))
            print("Channel={} Bustype={} Bitrate={}".format(
                channel, config.CAN_BUSTYPE, bitrate))
            controller = _open_controller(channel, bitrate)
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

    table = _format_table(normalized, command_params, log_path, channel, bitrate)
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
