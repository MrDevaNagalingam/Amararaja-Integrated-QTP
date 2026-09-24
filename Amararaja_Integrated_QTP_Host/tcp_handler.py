import socket
import time
from qtp_protocol import Connection, REQUEST, STREAM, RESULT
import config


class TCPCommunicator:
    def __init__(self, ip, port):
        self.ip, self.port = ip, port
        self.sock = None
        self.request_id = 0

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), config.CONNECT_TIMEOUT)
        self.connection = Connection(self.sock)

    def execute(self, command, params, emit):
        self.request_id = self.request_id % 0xffffffff + 1
        self.sock.settimeout(config.RESPONSE_TIMEOUT)
        self.connection.send(REQUEST, self.request_id, {"command": command, "params": params})
        deadline = time.monotonic() + config.RESPONSE_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Target response timed out")
            self.sock.settimeout(remaining)
            kind, request_id, value = self.connection.receive()
            if request_id != self.request_id:
                raise ValueError("Unexpected response request ID")
            if kind == STREAM:
                emit("[TARGET] " + str(value.get("message", "")))
            elif kind == RESULT:
                if value.get("status") not in {"PASS", "FAIL", "ERROR", "NOT_IMPLEMENTED"}:
                    raise ValueError("Invalid target result")
                return value
            else:
                raise ValueError("Unexpected response frame")

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None
