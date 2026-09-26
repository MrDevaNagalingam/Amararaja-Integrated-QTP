import tests


COMMANDS = {
    "PING_TEST": lambda params=None: tests.ping(params or {}),
    "SELEC_EM4M_TEST": lambda params=None: tests.selec_em4m(params or {}),
    "EDC2150_TEST": lambda params=None: tests.edc2150_meter(params or {}),
    "IMD1_TEST": lambda params=None: tests.imd1(params or {}),
    "IMD2_TEST": lambda params=None: tests.imd2(params or {}),
    "CAN_CONTROLLER_START_ALL_TEST": lambda params=None: tests.can_controller_start_all(params or {}),
    "CAN_CONTROLLER_STOP_ALL_TEST": lambda params=None: tests.can_controller_stop_all(params or {}),
    "CAN_CONTROLLER_SET_ALL_TEST": lambda params=None: tests.can_controller_set_all(params or {}),
    "CAN_CONTROLLER_START_TEST": lambda params=None: tests.can_controller_start(params or {}),
    "CAN_CONTROLLER_STOP_TEST": lambda params=None: tests.can_controller_stop(params or {}),
    "CAN_KEEP_ALIVE_START_TEST": lambda params=None: tests.can_keep_alive_start(params or {}),
    "CAN_KEEP_ALIVE_STOP_TEST": lambda params=None: tests.can_keep_alive_stop(params or {}),
    "RFID_TEST": lambda params=None: tests.rfid(params or {}),
    "TEMPERATURE_SENSOR_TEST": lambda params=None: tests.temperature_sensor(params or {}),
    "NETWORK_4G_TEST": lambda params=None: tests.network_4g_test(params or {}),
    "RELAY_CONTROL_ALL_OFF_TEST": lambda params=None: tests.relay_control_on_all(params or {}),
    "RELAY_CONTROL_DC1_ON_TEST": lambda params=None: tests.relay_control_dc1_on(params or {}),
    "RELAY_CONTROL_DC2_ON_TEST": lambda params=None: tests.relay_control_dc2_on(params or {}),
    "RELAY_CONTROL_AC_ON_TEST": lambda params=None: tests.relay_control_ac_on(params or {}),
    "RELAY_CONTROL_MERGER_ON_TEST": lambda params=None: tests.relay_control_merger_on(params or {}),
    "FLASH_PHYTEC_MSP_DC_TEST": lambda params=None: tests.flash_phytec_msp_dc(params or {}),
    "FLASH_COIL_CONTROL_TEST": lambda params=None: tests.flash_coil_control(params or {}),
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
