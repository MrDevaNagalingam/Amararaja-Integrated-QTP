"""Test report format matching the BOSCH reference project."""
from datetime import datetime
import os
import re


class TestLogger:
    _ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

    def __init__(self, log_dir="test_log"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.log_file = os.path.join(log_dir, "test_log_{}.txt".format(timestamp))
        self.summary_file = os.path.join(log_dir, "test_summary_{}.txt".format(timestamp))
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self.aborted_tests = 0
        self.test_results = []
        self._write_header()

    def _write_header(self):
        header = """
{0}
QTP TEST EXECUTION LOG
{0}
Session Started: {1}
{0}

""".format("=" * 80, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        with open(self.log_file, "w", encoding="utf-8") as stream:
            stream.write(header)

    def log_test_start(self, test_num, test_desc, test_cmd):
        log_entry = """
{0}
TEST #{1}: {2}
Command: {3}
Started: {4}
{0}
""".format("-" * 80, test_num, test_desc, test_cmd,
           datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        with open(self.log_file, "a", encoding="utf-8") as stream:
            stream.write(log_entry)
        print(log_entry)

    def log_test_result(self, test_num, test_desc, status, details, working_as_expected):
        self.total_tests += 1
        if status == "PASS":
            self.passed_tests += 1
        elif status == "FAIL":
            self.failed_tests += 1
        elif status == "SKIPPED":
            self.skipped_tests += 1
        else:
            self.aborted_tests += 1

        acknowledgment = "YES" if working_as_expected else "NO"
        cleaned_details = self.sanitize(details)
        completed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = """
Result: {0}
Details: {1}
Working as Expected: {2}
Completed: {3}
{4}

""".format(status, cleaned_details, acknowledgment,
           completed, "=" * 80)
        with open(self.log_file, "a", encoding="utf-8") as stream:
            stream.write(log_entry)
        if len(cleaned_details) > 1200 or cleaned_details.count("\n") > 25:
            print("\nResult: {}\nDetails: [large output saved in {}]\n"
                  "Working as Expected: {}\nCompleted: {}\n{}\n".format(
                      status, self.log_file, acknowledgment, completed, "=" * 80))
        else:
            print(log_entry)
        self.test_results.append({
            "num": test_num,
            "desc": test_desc,
            "status": status,
            "expected": acknowledgment,
        })

    def sanitize(self, details):
        text = "" if details is None else str(details)
        text = text.replace("\x00", "")
        text = self._ANSI_RE.sub("", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return re.sub(r"\n{3,}", "\n\n", text).rstrip("\n")

    def write_summary(self):
        pass_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests else 0
        summary = """
{0}
TEST EXECUTION SUMMARY
{0}
Session Completed: {1}

STATISTICS:
-----------
Total Tests Executed: {2}
Passed: {3}
Failed: {4}
Skipped: {5}
Aborted: {6}

Pass Rate: {7:.2f}%

DETAILED RESULTS:
-----------------
""".format("=" * 80, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           self.total_tests, self.passed_tests, self.failed_tests,
           self.skipped_tests, self.aborted_tests, pass_rate)
        for result in self.test_results:
            summary += "Test #{}: {}\n".format(result["num"], result["desc"])
            summary += "  Status: {} | Expected: {}\n\n".format(
                result["status"], result["expected"])
        summary += "{}\n".format("=" * 80)
        with open(self.summary_file, "w", encoding="utf-8") as stream:
            stream.write(summary)
        with open(self.log_file, "a", encoding="utf-8") as stream:
            stream.write(summary)
        print(summary)
        print("\nLog files saved:")
        print("  - Detailed Log: {}".format(self.log_file))
        print("  - Summary: {}".format(self.summary_file))

