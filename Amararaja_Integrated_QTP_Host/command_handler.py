from datetime import datetime
from pathlib import Path
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
        self.emit("[QTP] {}: {} - {}".format(command, result["status"], result.get("message", "")))
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

    def _run_test(self, target_command, params=None):
        return self.execute(target_command, params)

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
        self.emit("[EXECUTING] Running test: " + test_cmd)
        try:
            result = self.execute_command(test_cmd)
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
        self.emit("[RESULT] Status: " + status)
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
