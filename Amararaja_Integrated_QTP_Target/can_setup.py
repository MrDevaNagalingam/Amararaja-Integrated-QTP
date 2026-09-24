"""
Shared CAN codec helper for the Tonhe charging-module protocol simulation.

Preferred path: cantools (DBC parsing) + python-can (bus I/O), if installed.

Fallback path (used automatically if either package is missing -- e.g. no
internet access to pip install): a pure standard-library implementation that
- parses the message/signal layout straight from the CSV we generated
  (tonhe_can_messages_6modules.csv), instead of the .dbc file, and
- talks to the CAN bus via Python's built-in socket.AF_CAN support
  (Linux SocketCAN only -- no external packages required at all).

module_node.py and controller_node.py do not need to change: they call
load_db() / open_bus() / send_message() / decode_frame() exactly the same
way regardless of which path is active.

IMPORTANT if you're on the fallback path: copy
tonhe_can_messages_6modules.csv (the original CSV, not just the .dbc) to
this system too -- it's what gets parsed instead of the DBC.

IMPORTANT if you're on Windows/PCAN without internet access: the raw-socket
fallback below is Linux/SocketCAN only. Let me know and I'll write a ctypes
based PCAN-Basic variant instead (also zero pip installs, calls the vendor
DLL directly).
"""

import csv
import socket
import struct
import subprocess
import time

try:
    import cantools
    import can as python_can
    _HAVE_CANTOOLS = True
except ImportError:
    _HAVE_CANTOOLS = False


# ============================================================
#  Pure-stdlib message database (fallback for cantools)
# ============================================================

class _Signal:
    __slots__ = ("name", "start", "length", "factor", "offset")

    def __init__(self, name, start, length, factor, offset):
        self.name = name
        self.start = start
        self.length = length
        self.factor = factor
        self.offset = offset


class _Message:
    __slots__ = ("name", "can_id", "dlc", "signals")

    def __init__(self, name, can_id, dlc, signals):
        self.name = name
        self.can_id = can_id
        self.dlc = dlc
        self.signals = signals  # list[_Signal]

    def encode(self, values):
        raw = 0
        for sig in self.signals:
            phys = values.get(sig.name, 0)
            ival = round((phys - sig.offset) / sig.factor)
            mask = (1 << sig.length) - 1
            raw |= (ival & mask) << sig.start
        return raw.to_bytes(8, "little")[: self.dlc]

    def decode(self, data):
        raw = int.from_bytes(data.ljust(8, b"\x00"), "little")
        out = {}
        for sig in self.signals:
            mask = (1 << sig.length) - 1
            ival = (raw >> sig.start) & mask
            value = ival * sig.factor + sig.offset
            # Bitmask/enum/state signals (factor=1, offset=0) should come back
            # as plain int, not float -- floats can't be used in bit-shifts
            # and comparisons like `== 0xAA` are safer as int-to-int too.
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            out[sig.name] = value
        return out


class CsvDatabase:
    """Pure-stdlib stand-in for cantools.database.Database, built from our CSV."""

    def __init__(self, csv_path):
        by_name = {}
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                name = row["MessageName"]
                if name not in by_name:
                    by_name[name] = {
                        "can_id": int(row["CAN_ID"], 16),
                        "dlc": int(row["DLC"]),
                        "signals": [],
                    }
                by_name[name]["signals"].append(_Signal(
                    row["SignalName"],
                    int(row["StartBit"]),
                    int(row["BitLength"]),
                    float(row["Factor"]),
                    float(row["Offset"]),
                ))
        self._by_name = {n: _Message(n, v["can_id"], v["dlc"], v["signals"])
                          for n, v in by_name.items()}
        self._by_id = {m.can_id: m for m in self._by_name.values()}

    def get_message_by_name(self, name):
        return self._by_name[name]

    def get_message_by_frame_id(self, frame_id):
        if frame_id not in self._by_id:
            raise KeyError(frame_id)
        return self._by_id[frame_id]


# ============================================================
#  Pure-stdlib bus I/O (fallback for python-can)
# ============================================================

class _Frame:
    """Minimal stand-in for can.Message -- just what our codec/nodes touch."""
    __slots__ = ("arbitration_id", "data")

    def __init__(self, arbitration_id, data):
        self.arbitration_id = arbitration_id
        self.data = data


_CAN_FRAME_FMT = "=IB3x8s"   # matches struct can_frame from linux/can.h
_CAN_EFF_FLAG = 0x80000000   # extended (29-bit) frame flag
_CAN_EFF_MASK = 0x1FFFFFFF


class RawSocketCanBus:
    """
    SocketCAN bus using Python's built-in socket.AF_CAN support.
    Linux only. No external packages required. Bring the interface up first:
        sudo ip link set can0 down
        sudo ip link set can0 type can bitrate 125000 restart-ms 100
        sudo ip link set can0 up
    ('restart-ms 100' tells the kernel to auto-recover from a bus-off
    condition instead of requiring the interface to be manually brought
    back up -- see the note on recv() below for why that matters here.)
    """

    def __init__(self, channel="can0"):
        self.channel = channel
        self.sock = self._open_socket()

    def _open_socket(self):
        sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        sock.bind((self.channel,))
        return sock

    def send(self, frame):
        can_id = frame.arbitration_id | _CAN_EFF_FLAG  # protocol always uses 29-bit IDs
        data = frame.data.ljust(8, b"\x00")
        packet = struct.pack(_CAN_FRAME_FMT, can_id, len(frame.data), data)
        self.sock.send(packet)

    def recv(self, timeout=None):
        self.sock.settimeout(timeout)
        try:
            packet = self.sock.recv(16)
        except socket.timeout:
            return None
        except OSError as e:
            # Typically errno 100 (ENETDOWN) or 105 (ENOBUFS) -- the interface
            # went admin-down or the CAN controller hit a bus-off condition
            # (usually a wiring/termination/ground fault, or another node on
            # the bus at the wrong bitrate). Don't crash: log it and try to
            # reopen the socket so we recover automatically once the
            # interface comes back (this requires 'restart-ms' to be set on
            # the interface, per the docstring above -- otherwise someone
            # has to manually `ip link set <chan> up` again).
            print("[can_codec] CAN bus error on {}: {} -- attempting to "
                  "reopen the socket".format(self.channel, e))
            try:
                self.sock.close()
            except OSError:
                pass
            time.sleep(1.0)
            try:
                self.sock = self._open_socket()
            except OSError as e2:
                print("[can_codec] reopen failed: {} -- will keep retrying".format(e2))
            return None
        can_id, dlc, data = struct.unpack(_CAN_FRAME_FMT, packet)
        can_id &= _CAN_EFF_MASK
        return _Frame(can_id, data[:dlc])


# ============================================================
#  Public API -- used by module_node.py / controller_node.py, unchanged
# ============================================================

def configure_can_interface(channel, bitrate, restart_ms=100):
    """
    Bring up (or reconfigure) a SocketCAN interface: down -> set bitrate +
    restart-ms -> up. Requires root (or CAP_NET_ADMIN). Mirrors the manual
    steps we previously had people type by hand on every board:
        ip link set <channel> down
        ip link set <channel> type can bitrate <bitrate> restart-ms <restart_ms>
        ip link set <channel> up
    'restart-ms' tells the kernel to auto-recover from a bus-off condition
    instead of needing the interface manually brought back up.

    On failure (no permission, interface doesn't exist, 'ip' not installed,
    etc.) this prints a warning and returns False rather than raising --
    the caller still attempts to open the socket afterward, which will fail
    with a clearer error if the interface genuinely isn't usable.
    """
    print("[can_codec] Configuring CAN interface {}".format(channel))
    commands = [
        ["ip", "link", "set", channel, "down"],
        ["ip", "link", "set", channel, "type", "can",
         "bitrate", str(bitrate), "restart-ms", str(restart_ms)],
        ["ip", "link", "set", channel, "up"],
    ]
    for cmd in commands:
        print("  $ " + " ".join(cmd))
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode().strip() if e.stderr else str(e)
            print("  [can_codec] WARNING: command failed ({}) -- continuing anyway. "
                  "You may need to configure {} manually, or run as root.".format(
                      stderr, channel))
            return False
        except FileNotFoundError:
            print("  [can_codec] WARNING: 'ip' command not found -- cannot auto-configure. "
                  "Install iproute2 or configure {} manually.".format(channel))
            return False
    print("[can_codec] {} is up at {} bit/s (restart-ms={})".format(
        channel, bitrate, restart_ms))
    return True


def load_db(dbc_path="tonhe_can_messages_6modules.dbc"):
    if dbc_path.lower().endswith(".csv"):
        return CsvDatabase(dbc_path)
    if _HAVE_CANTOOLS:
        return cantools.database.load_file(dbc_path, strict=False)
    csv_path = dbc_path.rsplit(".", 1)[0] + ".csv"
    print("[can_codec] cantools not installed -- loading {} instead (stdlib-only mode)".format(csv_path))
    return CsvDatabase(csv_path)


def open_bus(channel="can0", bustype="socketcan", bitrate=125000,
             auto_configure=True, restart_ms=100):
    if bustype == "socketcan" and auto_configure:
        configure_can_interface(channel, bitrate, restart_ms)

    if _HAVE_CANTOOLS:
        try:
            return python_can.interface.Bus(channel=channel, bustype=bustype, bitrate=bitrate)
        except Exception:
            pass  # fall through to the raw-socket path below
    if bustype != "socketcan":
        raise RuntimeError(
            "The stdlib-only fallback supports SocketCAN (Linux) only. "
            "If you're on PCAN/Windows without internet access, ask for the "
            "ctypes-based PCAN-Basic variant instead."
        )
    print("[can_codec] python-can not installed -- using raw SocketCAN socket on {}".format(channel))
    return RawSocketCanBus(channel)


def send_message(bus, db, message_name, signals):
    msg_def = db.get_message_by_name(message_name)
    data = msg_def.encode(signals)
    can_id = getattr(msg_def, "frame_id", None) or getattr(msg_def, "can_id", None)
    if _HAVE_CANTOOLS and isinstance(bus, python_can.BusABC):
        frame = python_can.Message(arbitration_id=can_id, data=data, is_extended_id=True)
    else:
        frame = _Frame(can_id, data)
    bus.send(frame)


def decode_frame(db, frame):
    try:
        msg_def = db.get_message_by_frame_id(frame.arbitration_id)
    except KeyError:
        return None, None
    try:
        sig = msg_def.decode(frame.data)
    except ValueError:
        return None, None
    return msg_def.name, sig
