"""Shared, bounded TCP framing. All integers use network byte order."""
import json
import struct

MAGIC = b"AQTP"
VERSION = 1
MAX_PAYLOAD = 65536
HEADER = struct.Struct("!4sBII")
TLV = struct.Struct("!BI")
REQUEST, STREAM, RESULT = 1, 2, 3


def encode(kind, request_id, value):
    if kind not in (REQUEST, STREAM, RESULT) or not 1 <= request_id <= 0xffffffff:
        raise ValueError("Invalid frame type or request ID")
    data = json.dumps(value, ensure_ascii=False).encode("utf-8")
    payload = TLV.pack(kind, len(data)) + data
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("Payload too large")
    return HEADER.pack(MAGIC, VERSION, request_id, len(payload)) + payload


class Connection:
    def __init__(self, sock):
        self.sock = sock
        self.buffer = bytearray()

    def send(self, kind, request_id, value):
        self.sock.sendall(encode(kind, request_id, value))

    def _fill(self, size):
        while len(self.buffer) < size:
            data = self.sock.recv(4096)
            if not data:
                raise ConnectionError("Peer disconnected")
            self.buffer.extend(data)

    def receive(self):
        self._fill(HEADER.size)
        magic, version, request_id, size = HEADER.unpack_from(self.buffer)
        if magic != MAGIC or version != VERSION or not request_id:
            raise ValueError("Invalid QTP header")
        if not TLV.size <= size <= MAX_PAYLOAD:
            raise ValueError("Invalid payload size")
        self._fill(HEADER.size + size)
        payload = bytes(self.buffer[HEADER.size:HEADER.size + size])
        del self.buffer[:HEADER.size + size]
        kind, length = TLV.unpack_from(payload)
        if kind not in (REQUEST, STREAM, RESULT) or length != size - TLV.size:
            raise ValueError("Invalid TLV")
        value = json.loads(payload[TLV.size:].decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("TLV value must be a JSON object")
        return kind, request_id, value
