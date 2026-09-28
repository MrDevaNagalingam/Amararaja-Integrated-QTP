import pathlib
import socket
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qtp_protocol import Connection, encode, HEADER, REQUEST, RESULT


class FramingTests(unittest.TestCase):
    def test_bundled_protocol_matches_canonical(self):
        expected = (ROOT / "qtp_protocol.py").read_bytes()
        for side in ("Host", "Target"):
            self.assertEqual(expected, (ROOT / ("Amararaja_Integrated_QTP_" + side) / "qtp_protocol.py").read_bytes())

    def test_fragmented_and_coalesced_frames(self):
        frame = encode(REQUEST, 1, {"command": "PING"})
        second = encode(REQUEST, 2, {"command": "STOP_QTP"})
        class FakeSocket:
            chunks = iter([frame[:2], frame[2:9], frame[9:] + second])
            def recv(self, size):
                return next(self.chunks, b"")
        connection = Connection(FakeSocket())
        self.assertEqual(connection.receive(), (REQUEST, 1, {"command": "PING"}))
        self.assertEqual(connection.receive(), (REQUEST, 2, {"command": "STOP_QTP"}))

    def test_oversize_header_rejected(self):
        class FakeSocket:
            def recv(self, size):
                return HEADER.pack(b"AQTP", 1, 1, 65537)
        with self.assertRaises(ValueError):
            Connection(FakeSocket()).receive()

    def test_disconnect_mid_frame(self):
        class FakeSocket:
            chunks = iter([b"AQ", b""])
            def recv(self, size):
                return next(self.chunks)
        with self.assertRaises(ConnectionError):
            Connection(FakeSocket()).receive()


class IntegrationTests(unittest.TestCase):
    def test_reconnect_commands_and_remote_shutdown(self):
        deployment = tempfile.TemporaryDirectory()
        self.addCleanup(deployment.cleanup)
        standalone = pathlib.Path(deployment.name)
        for side in ("Host", "Target"):
            shutil.copytree(ROOT / ("Amararaja_Integrated_QTP_" + side), standalone / side,
                            ignore=shutil.ignore_patterns("__pycache__", "test_log"))
        server = subprocess.Popen(
            [sys.executable, str(standalone / "Target/main.py"),
             "--host", "127.0.0.1", "--port", "0"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            line = server.stdout.readline()
            self.assertIn("Listening", line)
            port = int(line.split(":")[-1].split("...")[0])
            # Invalid frames must not kill the listening server.
            with socket.create_connection(("127.0.0.1", port), timeout=3) as client:
                client.sendall(HEADER.pack(b"BAD!", 1, 1, 5))
                self.assertEqual(client.recv(1), b"")
            with socket.create_connection(("127.0.0.1", port), timeout=3) as client:
                connection = Connection(client)
                connection.send(REQUEST, 7, {"command": "PING"})
                connection.receive()
                kind, rid, result = connection.receive()
                self.assertEqual((kind, rid, result["status"]), (RESULT, 7, "PASS"))
            with tempfile.TemporaryDirectory() as report_dir:
                host = subprocess.run(
                    [sys.executable, str(standalone / "Host/main.py"),
                     "127.0.0.1", "--port", str(port), "--report-dir", report_dir],
                    input="1\ny\nping\ny\nUNKNOWN\nq\n", capture_output=True,
                    text=True, timeout=15)
                self.assertEqual(host.returncode, 0, host.stdout + host.stderr)
                self.assertIn("[ERROR] Invalid choice: UNKNOWN", host.stdout)
                self.assertNotIn("NOT_IMPLEMENTED", host.stdout)
                self.assertIn("STOP_QTP: PASS", host.stdout)
                summaries = list(pathlib.Path(report_dir).glob("test_summary_*.txt"))
                self.assertEqual(len(summaries), 1)
                summary = summaries[0].read_text()
                self.assertIn("Total Tests Executed: 2", summary)
                self.assertIn("Passed: 2", summary)
                self.assertIn("Pass Rate: 100.00%", summary)
                self.assertEqual(summary.count("Test #1: TC-01 Ping test"), 2)
                self.assertNotIn("STOP_QTP", summary)
                self.assertIn("[EXECUTING] Running test: TEST_PING", host.stdout)
                self.assertIn("[HOST] PC -> TARGET: PING_TEST", host.stdout)
                self.assertIn("Is this test working as expected? (y/n):", host.stdout)
                self.assertIn("Working as Expected: YES", host.stdout)
                log = next(pathlib.Path(report_dir).glob("test_log_*.txt")).read_text()
                self.assertIn("QTP TEST EXECUTION LOG", log)
                self.assertIn("TEST #1: TC-01 Ping test", log)
                self.assertIn("STOP_QTP", log)
            output = server.communicate(timeout=5)[0]
            self.assertEqual(server.returncode, 0, output)
            self.assertIn("Target stopped", output)
            self.assertIn("STOP_QTP", output)
        finally:
            if server.poll() is None:
                server.kill()
                server.communicate()
            server.stdout.close()


if __name__ == "__main__":
    unittest.main()
