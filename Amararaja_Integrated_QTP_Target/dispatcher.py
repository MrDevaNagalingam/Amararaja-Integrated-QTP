import tests


COMMANDS = {
    "PING_TEST": lambda params=None: tests.ping(params or {}),
    "SELEC_EM4M_TEST": lambda params=None: tests.selec_em4m(params or {}),
    "EDC2150_TEST": lambda params=None: tests.edc2150_meter(params or {}),
    "CAN_CONTROLLER_START_ALL_TEST": lambda params=None: tests.can_controller_start_all(params or {}),
    "CAN_CONTROLLER_STOP_ALL_TEST": lambda params=None: tests.can_controller_stop_all(params or {}),
    "CAN_CONTROLLER_SET_ALL_TEST": lambda params=None: tests.can_controller_set_all(params or {}),
    "CAN_CONTROLLER_START_TEST": lambda params=None: tests.can_controller_start(params or {}),
    "CAN_CONTROLLER_STOP_TEST": lambda params=None: tests.can_controller_stop(params or {}),
    "RFID_TEST": lambda params=None: tests.rfid(params or {}),
    "ECHO": lambda params=None: tests.echo(params or {}),
    "PING": lambda params=None: tests.ping(params or {}),
}


def dispatch(request):
    command = request.get("command")
    params = request.get("params", {})
    if not isinstance(command, str) or not isinstance(params, dict):
        return {"status": "ERROR", "message": "Expected command string and params object"}, False
    if command == "STOP_QTP":
        return {"status": "PASS", "message": "Stop acknowledged; target shutting down"}, True
    function = COMMANDS.get(command)
    if function is None:
        return {"status": "NOT_IMPLEMENTED", "message": "Unsupported command: " + command}, False
    try:
        return function(params), False
    except Exception as exc:
        return {"status": "ERROR", "message": str(exc)}, False
