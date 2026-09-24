from datetime import datetime
from pathlib import Path
import config
from test_logger import TestLogger


class CommandHandler:
    def __init__(self, tcp, report_dir):
        self.tcp = tcp
        self.logger = TestLogger(str(report_dir))
        self.log_path = Path(self.logger.log_file)
        self.summary_path = Path(self.logger.summary_file)
        self.commands = {
            "TEST_PING": self.test_ping,
            "TEST_SELEC_EM4M": self.test_selec_em4m,
            "TEST_EDC2150": self.test_edc2150,
            "TEST_CAN_CONTROLLER_START_ALL": self.test_can_controller_start_all,
            "TEST_CAN_CONTROLLER_STOP_ALL": self.test_can_controller_stop_all,
            "TEST_CAN_CONTROLLER_SET_ALL": self.test_can_controller_set_all,
            "TEST_CAN_CONTROLLER_START": self.test_can_controller_start,
            "TEST_CAN_CONTROLLER_STOP": self.test_can_controller_stop,
            "TEST_RFID": self.test_rfid,
            "STOP_TARGET": self.stop_target,
            "PING": self.ping,
            "ECHO": self.echo,
            "STOP_QTP": self.stop_qtp,
        }

    def emit(self, message):
        message = self.logger.sanitize(message)
        print(message, flush=True)
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write("[{}] {}\n".format(datetime.now().isoformat(timespec="seconds"), message))

    def execute(self, command, params=None):
        self.emit("[HOST] PC -> TARGET: " + command)
        try:
            result = self.tcp.execute(command, params or {}, self.emit)
        except (OSError, ValueError) as exc:
            self.emit("[QTP] {}: ERROR - {}".format(command, exc))
            raise
        if command.endswith("_TEST"):
            return result
        message = result.get("message", "")
        if "\n" in message:
            self.emit("[QTP] {}: {}".format(command, result["status"]))
        else:
            self.emit("[QTP] {}: {} - {}".format(command, result["status"], message))
        return result

    def execute_command(self, command_id, params=None):
        if isinstance(command_id, str) and command_id in self.commands:
            return self.commands[command_id](params)
        return self.execute(command_id, params)

    def ping(self, params=None):
        return self._run_test("PING", params)

    def echo(self, params=None):
        return self._run_test("ECHO", params)

    def stop_qtp(self, params=None):
        return self._run_test("STOP_QTP", params)

    def stop_target(self, params=None):
        return self._run_test("STOP_QTP", params)

    def test_ping(self, params=None):
        return self._run_test("PING_TEST", params)

    def test_selec_em4m(self, params=None):
        return self._run_test("SELEC_EM4M_TEST", params)

    def test_edc2150(self, params=None):
        return self._run_test("EDC2150_TEST", params)

    def test_can_controller_start_all(self, params=None):
        return self._run_test("CAN_CONTROLLER_START_ALL_TEST", params)

    def test_can_controller_stop_all(self, params=None):
        return self._run_test("CAN_CONTROLLER_STOP_ALL_TEST", params)

    def test_can_controller_set_all(self, params=None):
        return self._run_test("CAN_CONTROLLER_SET_ALL_TEST", params)

    def test_can_controller_start(self, params=None):
        return self._run_test("CAN_CONTROLLER_START_TEST", params)

    def test_can_controller_stop(self, params=None):
        return self._run_test("CAN_CONTROLLER_STOP_TEST", params)

    def test_rfid(self, params=None):
        return self._run_test("RFID_TEST", params)

    def _run_test(self, target_command, params=None):
        return self.execute(target_command, params)

    def collect_selec_em4m_params(self):
        print("\n" + "-" * 80)
        choice = input(
            "Run in default {} @ {} 8N1, slave ID {}? (Y/n): ".format(
                config.SELEC_EM4M_PORT, config.SELEC_EM4M_BAUDRATE, config.SELEC_EM4M_SLAVE_ID)
        ).strip().lower()
        if choice in ("", "y", "yes"):
            return {
                "port": config.SELEC_EM4M_PORT,
                "baudrate": config.SELEC_EM4M_BAUDRATE,
                "slave_id": config.SELEC_EM4M_SLAVE_ID,
            }
        port = input("Enter port [example: {}]: ".format(config.SELEC_EM4M_PORT)).strip() or config.SELEC_EM4M_PORT
        baud_text = input("Enter baud rate [example: {}]: ".format(config.SELEC_EM4M_BAUDRATE)).strip() or str(config.SELEC_EM4M_BAUDRATE)
        slave_text = input("Enter slave ID [example: {}]: ".format(config.SELEC_EM4M_SLAVE_ID)).strip() or str(config.SELEC_EM4M_SLAVE_ID)
        return {
            "port": port,
            "baudrate": int(baud_text),
            "slave_id": int(slave_text),
        }

    def collect_edc2150_params(self):
        print("\n" + "-" * 80)
        choice = input(
            "Run in default {} @ {} 8N1, slave ID {}? (Y/n): ".format(
                config.EDC2150_PORT, config.EDC2150_BAUDRATE, config.EDC2150_SLAVE_ID)
        ).strip().lower()
        if choice in ("", "y", "yes"):
            return {
                "port": config.EDC2150_PORT,
                "baudrate": config.EDC2150_BAUDRATE,
                "slave_id": config.EDC2150_SLAVE_ID,
            }
        port = input("Enter port [example: {}]: ".format(config.EDC2150_PORT)).strip() or config.EDC2150_PORT
        baud_text = input("Enter baud rate [example: {}]: ".format(config.EDC2150_BAUDRATE)).strip() or str(config.EDC2150_BAUDRATE)
        slave_text = input("Enter slave ID [example: {}]: ".format(config.EDC2150_SLAVE_ID)).strip() or str(config.EDC2150_SLAVE_ID)
        return {
            "port": port,
            "baudrate": int(baud_text),
            "slave_id": int(slave_text),
        }

    def collect_can_set_all_params(self):
        print("\n" + "-" * 80)
        print("CAN default channel: {}".format(config.CAN_CHANNEL))
        group_text = input("Enter group [example: {}]: ".format(config.CAN_DEFAULT_GROUP)).strip() or str(config.CAN_DEFAULT_GROUP)
        voltage_text = input("Enter voltage [example: {}]: ".format(config.CAN_DEFAULT_VOLTAGE)).strip() or str(config.CAN_DEFAULT_VOLTAGE)
        current_text = input("Enter current [example: {}]: ".format(config.CAN_DEFAULT_CURRENT)).strip() or str(config.CAN_DEFAULT_CURRENT)
        return {"group": int(group_text), "voltage": float(voltage_text), "current": float(current_text)}

    def collect_can_start_params(self):
        print("\n" + "-" * 80)
        print("CAN default channel: {}".format(config.CAN_CHANNEL))
        address_text = input("Enter module address [example: {}]: ".format(config.CAN_DEFAULT_MODULE_ADDRESS)).strip() or str(config.CAN_DEFAULT_MODULE_ADDRESS)
        voltage_text = input("Enter voltage [example: {}]: ".format(config.CAN_DEFAULT_VOLTAGE)).strip() or str(config.CAN_DEFAULT_VOLTAGE)
        current_text = input("Enter current [example: {}]: ".format(config.CAN_DEFAULT_CURRENT)).strip() or str(config.CAN_DEFAULT_CURRENT)
        return {"address": int(address_text), "voltage": float(voltage_text), "current": float(current_text)}

    def collect_can_stop_params(self):
        print("\n" + "-" * 80)
        print("CAN default channel: {}".format(config.CAN_CHANNEL))
        address_text = input("Enter module address [example: {}]: ".format(config.CAN_DEFAULT_MODULE_ADDRESS)).strip() or str(config.CAN_DEFAULT_MODULE_ADDRESS)
        return {"address": int(address_text)}

    def collect_rfid_params(self):
        print("\n" + "-" * 80)
        choice = input(
            "Run in default {} @ {} 8N1? (Y/n): ".format(config.RFID_PORT, config.RFID_BAUDRATE)
        ).strip().lower()
        if choice in ("", "y", "yes"):
            return {
                "port": config.RFID_PORT,
                "baudrate": config.RFID_BAUDRATE,
            }
        port = input("Enter port [example: {}]: ".format(config.RFID_PORT)).strip() or config.RFID_PORT
        baud_text = input("Enter baud rate [example: {}]: ".format(config.RFID_BAUDRATE)).strip() or str(config.RFID_BAUDRATE)
        return {"port": port, "baudrate": int(baud_text)}

    def confirm_working_as_expected(self, prompt="Is this test working as expected? (y/n): "):
        while True:
            answer = input(prompt).strip().lower()
            if answer in ("y", "yes", "n", "no"):
                return answer in ("y", "yes")
            print("[ERROR] Enter YES or NO.")

    def run_test(self, test_num, title, test_cmd, info_message=None):
        expected = {
            "TEST_PING": "PONG - target received command",
        }
        self.logger.log_test_start(test_num, title, test_cmd)
        if info_message:
            self.emit("[INFO] " + info_message)
        params = None
        if test_cmd == "TEST_SELEC_EM4M":
            params = self.collect_selec_em4m_params()
        elif test_cmd == "TEST_EDC2150":
            params = self.collect_edc2150_params()
        elif test_cmd == "TEST_CAN_CONTROLLER_SET_ALL":
            params = self.collect_can_set_all_params()
        elif test_cmd == "TEST_CAN_CONTROLLER_START":
            params = self.collect_can_start_params()
        elif test_cmd == "TEST_CAN_CONTROLLER_STOP":
            params = self.collect_can_stop_params()
        elif test_cmd == "TEST_RFID":
            params = self.collect_rfid_params()
        self.emit("[EXECUTING] Running test: " + test_cmd)
        try:
            result = self.execute_command(test_cmd, params)
            status = result["status"]
            details = result.get("message", "")
            expected_message = expected.get(test_cmd)
            if status == "PASS" and expected_message is not None and details != expected_message:
                status = "FAIL"
                details = "Unexpected {} response: {}".format(test_cmd, details)
        except (OSError, ValueError) as exc:
            self.logger.log_test_result(test_num, title, "ABORTED", str(exc), False)
            raise
        except KeyboardInterrupt:
            self.logger.log_test_result(test_num, title, "ABORTED", "Interrupted by user", False)
            raise
        measurements = result.get("measurements", {}) if isinstance(result, dict) else {}
        table = measurements.get("table") if isinstance(measurements, dict) else None
        if table:
            self.emit(table)
        self.emit("[RESULT] Status: " + status)
        if "\n" in details:
            self.emit("[RESULT] Details:\n" + details)
        else:
            self.emit("[RESULT] Details: " + details)
        print("\n" + "-" * 80)
        working_as_expected = self.confirm_working_as_expected()
        if status == "PASS" and not working_as_expected:
            status = "FAIL"
            details = details + "\nOperator reported test is not working as expected."
        self.logger.log_test_result(test_num, title, status, details, working_as_expected)
        return {"status": status, "message": details}

    def close(self):
        print("\n" + "=" * 80)
        print(" GENERATING TEST SUMMARY ".center(80))
        print("=" * 80)
        self.logger.write_summary()
