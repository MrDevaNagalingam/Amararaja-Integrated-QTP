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
            "TEST_IMD1": self.test_imd1,
            "TEST_IMD2": self.test_imd2,
            "TEST_CAN_CONTROLLER_START_ALL": self.test_can_controller_start_all,
            "TEST_CAN_CONTROLLER_STOP_ALL": self.test_can_controller_stop_all,
            "TEST_CAN_CONTROLLER_SET_ALL": self.test_can_controller_set_all,
            "TEST_CAN_CONTROLLER_START": self.test_can_controller_start,
            "TEST_CAN_CONTROLLER_STOP": self.test_can_controller_stop,
            "TEST_CAN_KEEP_ALIVE_START": self.test_can_keep_alive_start,
            "TEST_CAN_KEEP_ALIVE_STOP": self.test_can_keep_alive_stop,
            "TEST_RFID": self.test_rfid,
            "TEST_TEMPERATURE_SENSOR": self.test_temperature_sensor,
            "TEST_NETWORK_4G": self.test_network_4g,
            "TEST_RELAY_CONTROL_ALL_OFF": self.test_relay_control_all_off,
            "TEST_RELAY_CONTROL_DC1_ON": self.test_relay_control_dc1_on,
            "TEST_RELAY_CONTROL_DC2_ON": self.test_relay_control_dc2_on,
            "TEST_RELAY_CONTROL_AC_ON": self.test_relay_control_ac_on,
            "TEST_RELAY_CONTROL_MERGER_ON": self.test_relay_control_merger_on,
            "TEST_FLASH_PHYTEC_MSP_DC": self.test_flash_phytec_msp_dc,
            "TEST_FLASH_COIL_CONTROL": self.test_flash_coil_control,
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
        if message.startswith("[TARGET] Received command: "):
            self.emit_blank()

    def emit_blank(self):
        print("", flush=True)
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write("\n")

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

    def test_imd1(self, params=None):
        return self._run_test("IMD1_TEST", params)

    def test_imd2(self, params=None):
        return self._run_test("IMD2_TEST", params)

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

    def test_can_keep_alive_start(self, params=None):
        return self._run_test("CAN_KEEP_ALIVE_START_TEST", params)

    def test_can_keep_alive_stop(self, params=None):
        return self._run_test("CAN_KEEP_ALIVE_STOP_TEST", params)

    def test_rfid(self, params=None):
        return self._run_test("RFID_TEST", params)

    def test_temperature_sensor(self, params=None):
        return self._run_test("TEMPERATURE_SENSOR_TEST", params)

    def test_network_4g(self, params=None):
        return self._run_test("NETWORK_4G_TEST", params)

    def test_relay_control_all_off(self, params=None):
        return self._run_test("RELAY_CONTROL_ALL_OFF_TEST", params)

    def test_relay_control_dc1_on(self, params=None):
        return self._run_test("RELAY_CONTROL_DC1_ON_TEST", params)

    def test_relay_control_dc2_on(self, params=None):
        return self._run_test("RELAY_CONTROL_DC2_ON_TEST", params)

    def test_relay_control_ac_on(self, params=None):
        return self._run_test("RELAY_CONTROL_AC_ON_TEST", params)

    def test_relay_control_merger_on(self, params=None):
        return self._run_test("RELAY_CONTROL_MERGER_ON_TEST", params)

    def test_flash_phytec_msp_dc(self, params=None):
        return self._run_test("FLASH_PHYTEC_MSP_DC_TEST", params)

    def test_flash_coil_control(self, params=None):
        return self._run_test("FLASH_COIL_CONTROL_TEST", params)

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

    def collect_imd_params(self, port, baudrate, parity, slave_id):
        print("\n" + "-" * 80)
        choice = input(
            "Run in default {} @ {} 8{}1, slave ID {}? (Y/n): ".format(
                port, baudrate, parity, slave_id)
        ).strip().lower()
        if choice in ("", "y", "yes"):
            return {
                "port": port,
                "baudrate": baudrate,
                "parity": parity,
                "slave_id": slave_id,
            }
        custom_port = input("Enter port [example: {}]: ".format(port)).strip() or port
        baud_text = input("Enter baud rate [example: {}]: ".format(baudrate)).strip() or str(baudrate)
        parity_text = input("Enter parity [example: N/E/O]: ").strip().upper() or parity
        if parity_text not in {"N", "E", "O"}:
            parity_text = parity
        slave_text = input("Enter slave ID [example: {}]: ".format(slave_id)).strip() or str(slave_id)
        return {
            "port": custom_port,
            "baudrate": int(baud_text),
            "parity": parity_text,
            "slave_id": int(slave_text),
        }

    def collect_can_base_params(self):
        print("\n" + "-" * 80)
        choice = input(
            "Run in default {} @ {} bit/s? (Y/n): ".format(config.CAN_CHANNEL, config.CAN_BITRATE)
        ).strip().lower()
        if choice in ("", "y", "yes"):
            return {"channel": config.CAN_CHANNEL, "bitrate": config.CAN_BITRATE}
        channel = input("Enter CAN channel [example: {}]: ".format(config.CAN_CHANNEL)).strip() or config.CAN_CHANNEL
        bitrate_text = input("Enter bitrate [example: {}]: ".format(config.CAN_BITRATE)).strip() or str(config.CAN_BITRATE)
        return {"channel": channel, "bitrate": int(bitrate_text)}

    def collect_can_set_all_params(self):
        params = self.collect_can_base_params()
        group_text = input("Enter group [example: {}]: ".format(config.CAN_DEFAULT_GROUP)).strip() or str(config.CAN_DEFAULT_GROUP)
        voltage_text = input("Enter voltage [example: {}]: ".format(config.CAN_DEFAULT_VOLTAGE)).strip() or str(config.CAN_DEFAULT_VOLTAGE)
        current_text = input("Enter current [example: {}]: ".format(config.CAN_DEFAULT_CURRENT)).strip() or str(config.CAN_DEFAULT_CURRENT)
        params.update({"group": int(group_text), "voltage": float(voltage_text), "current": float(current_text)})
        return params

    def collect_can_start_params(self):
        params = self.collect_can_base_params()
        address_text = input("Enter module address [example: {}]: ".format(config.CAN_DEFAULT_MODULE_ADDRESS)).strip() or str(config.CAN_DEFAULT_MODULE_ADDRESS)
        voltage_text = input("Enter voltage [example: {}]: ".format(config.CAN_DEFAULT_VOLTAGE)).strip() or str(config.CAN_DEFAULT_VOLTAGE)
        current_text = input("Enter current [example: {}]: ".format(config.CAN_DEFAULT_CURRENT)).strip() or str(config.CAN_DEFAULT_CURRENT)
        params.update({"address": int(address_text), "voltage": float(voltage_text), "current": float(current_text)})
        return params

    def collect_can_stop_params(self):
        params = self.collect_can_base_params()
        address_text = input("Enter module address [example: {}]: ".format(config.CAN_DEFAULT_MODULE_ADDRESS)).strip() or str(config.CAN_DEFAULT_MODULE_ADDRESS)
        params.update({"address": int(address_text)})
        return params

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

    def relay_control_params(self):
        return {
            "serial_port": config.RELAY_MCU_SERIAL_PORT,
            "baudrate": config.RELAY_MCU_BAUDRATE,
        }

    def temperature_sensor_params(self):
        return {
            "serial_port": config.TEMP_SENSOR_SERIAL_PORT,
        }

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
        elif test_cmd == "TEST_IMD1":
            params = self.collect_imd_params(
                config.IMD1_PORT, config.IMD1_BAUDRATE, config.IMD1_PARITY, config.IMD1_SLAVE_ID)
        elif test_cmd == "TEST_IMD2":
            params = self.collect_imd_params(
                config.IMD2_PORT, config.IMD2_BAUDRATE, config.IMD2_PARITY, config.IMD2_SLAVE_ID)
        elif test_cmd in {"TEST_CAN_CONTROLLER_START_ALL", "TEST_CAN_CONTROLLER_STOP_ALL", "TEST_CAN_KEEP_ALIVE_START"}:
            params = self.collect_can_base_params()
        elif test_cmd == "TEST_CAN_CONTROLLER_SET_ALL":
            params = self.collect_can_set_all_params()
        elif test_cmd == "TEST_CAN_CONTROLLER_START":
            params = self.collect_can_start_params()
        elif test_cmd == "TEST_CAN_CONTROLLER_STOP":
            params = self.collect_can_stop_params()
        elif test_cmd == "TEST_RFID":
            params = self.collect_rfid_params()
        elif test_cmd == "TEST_TEMPERATURE_SENSOR":
            params = self.temperature_sensor_params()
        elif test_cmd.startswith("TEST_RELAY_CONTROL_"):
            params = self.relay_control_params()
        elif test_cmd in {"TEST_FLASH_PHYTEC_MSP_DC", "TEST_FLASH_COIL_CONTROL"}:
            params = self.relay_control_params()
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
        self.emit_blank()
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
