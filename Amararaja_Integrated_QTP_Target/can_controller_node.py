"""
Master controller simulator (protocol-level only, no physics).
Run this on the 7th system:

    python3 controller_node.py --channel can0

Provides an interactive shell to issue commands and inspect the last known
state of every module, plus a background thread sending the periodic
timing command and listening for all incoming module traffic.

No f-strings are used anywhere in this file, so it also runs on older
Python 3 interpreters (pre-3.6) sometimes found on embedded/rugged boards.
"""

import cmd
import threading
import time

import can_setup


STATE_LABELS = {0: "Normal OFF", 1: "ON", 17: "Fault OFF"}  # 0x00, 0x01, 0x11


def _now_str():
    t = time.time()
    return time.strftime("%H:%M:%S", time.localtime(t)) + ".{:03d}".format(int((t % 1) * 1000))


class Controller:
    def __init__(self, db, bus, verbose=True):
        self.db = db
        self.bus = bus
        self.verbose = verbose
        self.show_tx = True     # independent of `verbose`: which direction(s) to log
        self.show_rx = True
        self.module_states = {}   # address -> dict of last known signals
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        # ---------- load-sharing state ----------
        self.mode = None  # None, "gun", "dual_gun"

        self.gun_voltage = 0.0
        self.gun_current = 0.0

        self.gun1_voltage = 0.0
        self.gun1_current = 0.0

        self.gun2_voltage = 0.0
        self.gun2_current = 0.0

        self.last_seen = {}
        self.active_modules_cache = set()

    # ---------- logging ----------
    def _log(self, direction, tag, msg_name, signals):
        if not self.verbose:
            return
        if direction == "TX" and not self.show_tx:
            return
        if direction == "RX" and not self.show_rx:
            return
        print("{} [Controller] {}-{:<8} {}: {}".format(
            _now_str(), direction, tag, msg_name, signals))

    def _send(self, msg_name, signals, tag):
        can_setup.send_message(self.bus, self.db, msg_name, signals)
        self._log("TX", tag, msg_name, signals)

    # ---------- inbound ----------
    def rx_loop(self):
        while not self.stop_event.is_set():
            frame = self.bus.recv(timeout=0.2)
            if frame is None:
                continue
            name, sig = can_setup.decode_frame(self.db, frame)
            if name is None:
                continue

            if name.startswith(("M_C_1_Mod", "M_C_3_Mod", "M_C_4_Mod")):
                addr = int(name.rsplit("Mod", 1)[1])
                with self.lock:
                    self.module_states.setdefault(addr, {}).update(sig)
                    self.last_seen[addr] = time.time()
                self._log("RX", "CYCLIC", name, sig)
                current_alive = set(self.get_alive_modules())

                if current_alive != self.active_modules_cache:
                    self.active_modules_cache = current_alive

                    if self.mode is not None:
                        print(
                            "[Controller] module availability changed, "
                            "rebalancing"
                        )
                        self.rebalance()

            elif name.startswith("M_C_2_Mod"):
                addr = int(name.rsplit("Mod", 1)[1])
                with self.lock:
                    self.last_seen[addr] = time.time()
                print("[Controller] module {} confirmed command: {}".format(addr, sig))
                self._log("RX", "TRIGGER", name, sig)

    # ---------- periodic timing command ----------
    def timing_loop(self):
        while not self.stop_event.is_set():
            self._send("C_M_3", {"Reserved_Standby": 0}, "CYCLIC")
            time.sleep(5)

    # ---------- outbound commands ----------
    def start_all(self, group=1):
        self._send("C_M_1_Broadcast", {
            "ModuleProcessingFlag": 0xFFFFFF, "ModuleStartStop": 0xAA,
            "AddressMultiple": 0, "ModuleGroupNumber": group, "Reserved_Standby": 0,
        }, "COMMAND")

    def stop_all(self, group=1):
        self._send("C_M_1_Broadcast", {
            "ModuleProcessingFlag": 0xFFFFFF, "ModuleStartStop": 0x55,
            "AddressMultiple": 0, "ModuleGroupNumber": group, "Reserved_Standby": 0,
        }, "COMMAND")

    def set_all_params(self, voltage, current, group=1):
        self._send("C_M_2_Broadcast", {
            "ModuleProcessingFlag": 0xFFFFFF, "AddressMultiple": 0,
            "ModuleGroupNumber": group, "ChargingVoltage": voltage, "ChargingCurrent": current,
        }, "COMMAND")

    def start_module(self, addr, voltage, current):
        msg_name = "C_M_24_Mod{}".format(addr)
        self._send(msg_name, {
            "ModuleStartStop": 0xAA, "ChargingMode": 0x00,
            "ChargingVoltage": voltage, "ChargingCurrent": current, "Reserved_Standby": 0,
        }, "COMMAND")

    def stop_module(self, addr):
        msg_name = "C_M_24_Mod{}".format(addr)
        self._send(msg_name, {
            "ModuleStartStop": 0x55, "ChargingMode": 0x00,
            "ChargingVoltage": 0, "ChargingCurrent": 0, "Reserved_Standby": 0,
        }, "COMMAND")

    def set_module_address(self, target_addr, new_addr):
        msg_name = "C_M_23_Mod{}".format(target_addr)
        self._send(msg_name, {
            "NewModuleAddress": new_addr, "Reserved_Standby": 0,
        }, "COMMAND")

    def gun(self, voltage, current):
        self.mode = "gun"

        self.gun_voltage = voltage
        self.gun_current = current

        self.rebalance()

    def dual_gun(
        self,
        gun1_voltage,
        gun1_current,
        gun2_voltage,
        gun2_current
    ):
        self.mode = "dual_gun"

        self.gun1_voltage = gun1_voltage
        self.gun1_current = gun1_current

        self.gun2_voltage = gun2_voltage
        self.gun2_current = gun2_current

        self.rebalance()

    def stop_load_share(self):
        self.mode = None

    def set_input_mode(self, mode):
        # mode: "ac" or "dc". Only accepted by a module while it's powered off.
        value = 1 if mode == "ac" else 0
        self._send("C_M_4", {
            "InputModeConfig": value, "Reserved_Standby": 0,
        }, "COMMAND")

    def set_address_mode(self, mode):
        # mode: "auto" or "manual". Only accepted by a module while it's powered off.
        value = 1 if mode == "manual" else 0
        self._send("C_M_12", {
            "AddressSettingMode": value, "Reserved": 0,
        }, "COMMAND")

    def print_status(self):
        with self.lock:
            if not self.module_states:
                print("No module data received yet.")
                return
            for addr in sorted(self.module_states):
                print("Module {}:".format(addr))
                sig = self.module_states[addr]
                for key in sorted(sig):
                    value = sig[key]
                    if key == "ChargingModuleState":
                        label = STATE_LABELS.get(int(value), "?")
                        print("    {}: {} ({})".format(key, value, label))
                    else:
                        print("    {}: {}".format(key, value))

    def get_alive_modules(self):
        now = time.time()

        alive = []

        with self.lock:
            for addr in self.module_states:
                last = self.last_seen.get(addr)

                if last is None:
                    continue

                if now - last <= 2.0:
                    alive.append(addr)

        return sorted(alive)

    def get_alive_group(self, addresses):
        alive = self.get_alive_modules()
        return [m for m in alive if m in addresses]

    def rebalance(self):
        if self.mode == "gun":
            active = self.get_alive_modules()

            if not active:
                print("[Controller] no active modules available")
                return

            current_per_module = (
                self.gun_current / float(len(active))
            )

            print(
                "[Controller] gun rebalance: {} modules, "
                "{} V, {} A total => {} A/module".format(
                    len(active),
                    self.gun_voltage,
                    self.gun_current,
                    current_per_module
                )
            )

            for addr in active:
                self.start_module(
                    addr,
                    self.gun_voltage,
                    current_per_module
                )

        elif self.mode == "dual_gun":

            group1 = self.get_alive_group([1, 2, 3])
            group2 = self.get_alive_group([4, 5, 6])

            if group1:
                current_per_module = (
                    self.gun1_current / float(len(group1))
                )

                print(
                    "[Controller] gun1 rebalance: {} modules "
                    "=> {} A/module".format(
                        len(group1),
                        current_per_module
                    )
                )

                for addr in group1:
                    self.start_module(
                        addr,
                        self.gun1_voltage,
                        current_per_module
                    )

            if group2:
                current_per_module = (
                    self.gun2_current / float(len(group2))
                )

                print(
                    "[Controller] gun2 rebalance: {} modules "
                    "=> {} A/module".format(
                        len(group2),
                        current_per_module
                    )
                )

                for addr in group2:
                    self.start_module(
                        addr,
                        self.gun2_voltage,
                        current_per_module
                    )


class ControllerShell(cmd.Cmd):
    intro = "Tonhe controller simulator. Type help or ? to list commands.\n"
    prompt = "(controller) "

    def __init__(self, controller):
        cmd.Cmd.__init__(self)
        self.controller = controller

    def do_start_all(self, arg):
        "start_all -- start all modules (group 1, address multiple 0 => addr 1-24)"
        self.controller.start_all()

    def do_stop_all(self, arg):
        "stop_all -- stop all modules"
        self.controller.stop_all()

    def do_set_all(self, arg):
        "set_all <voltage> <current> -- set charging voltage/current for all modules"
        v, i = map(float, arg.split())
        self.controller.set_all_params(v, i)

    def do_start(self, arg):
        "start <addr> <voltage> <current> -- start one specific module"
        addr, v, i = arg.split()
        self.controller.start_module(int(addr), float(v), float(i))

    def do_stop(self, arg):
        "stop <addr> -- stop one specific module"
        self.controller.stop_module(int(arg))

    def do_set_address(self, arg):
        "set_address <current_addr> <new_addr> -- reassign a module's address"
        cur, new = arg.split()
        self.controller.set_module_address(int(cur), int(new))

    def do_gun(self, arg):
        """
        gun <voltage> <current>

        Example:
            gun 750 300
        """

        try:
            voltage, current = map(float, arg.split())
        except ValueError:
            print("Usage: gun <voltage> <current>")
            return

        self.controller.gun(
            voltage,
            current
        )

    def do_dual_gun(self, arg):
        """
        dual_gun 1 <v1> <i1> 2 <v2> <i2>

        Example:
            dual_gun 1 750 300 2 400 180
        """

        parts = arg.split()

        if len(parts) != 6:
            print("Usage: dual_gun 1 <v1> <i1> 2 <v2> <i2>")
            return

        try:
            id1, v1, i1, id2, v2, i2 = parts
            id1, id2 = int(id1), int(id2)
            v1, i1, v2, i2 = float(v1), float(i1), float(v2), float(i2)
        except ValueError:
            print("Usage: dual_gun 1 <v1> <i1> 2 <v2> <i2>  "
                  "(ids must be integers, voltage/current must be numbers)")
            return

        if sorted((id1, id2)) != [1, 2]:
            print("Gun ids must be 1 and 2 (in either order).")
            return

        # Map by id rather than position, so "dual_gun 2 ... 1 ..." still
        # sends gun 1's values to gun1 (modules 1-3) and gun 2's to gun2
        # (modules 4-6), regardless of which order they were typed in.
        values = {id1: (v1, i1), id2: (v2, i2)}
        gun1_voltage, gun1_current = values[1]
        gun2_voltage, gun2_current = values[2]

        self.controller.dual_gun(
            gun1_voltage, gun1_current,
            gun2_voltage, gun2_current
        )

    def do_disable_gun(self, arg):
        """
        disable_gun -- disable automatic load sharing
        """

        self.controller.stop_load_share()

        print("Load sharing disabled")

    def do_set_input_mode(self, arg):
        "set_input_mode <ac|dc> -- broadcast input mode config (only accepted if a module is powered off)"
        mode = arg.strip().lower()
        if mode not in ("ac", "dc"):
            print("Usage: set_input_mode <ac|dc>")
            return
        self.controller.set_input_mode(mode)

    def do_set_address_mode(self, arg):
        "set_address_mode <auto|manual> -- broadcast address mode selection (only accepted if a module is powered off)"
        mode = arg.strip().lower()
        if mode not in ("auto", "manual"):
            print("Usage: set_address_mode <auto|manual>")
            return
        self.controller.set_address_mode(mode)

    def do_status(self, arg):
        "status -- print last known state of every module"
        self.controller.print_status()

    def do_quiet(self, arg):
        "quiet -- suppress TX/RX frame logging"
        self.controller.verbose = False
        print("TX/RX logging disabled.")

    def do_verbose(self, arg):
        "verbose -- show TX/RX frame logging"
        self.controller.verbose = True
        print("TX/RX logging enabled.")

    def do_only_tx(self, arg):
        "only_tx -- only log outbound (TX) frames"
        self.controller.show_tx = True
        self.controller.show_rx = False
        print("Now showing TX only.")

    def do_only_rx(self, arg):
        "only_rx -- only log inbound (RX) frames"
        self.controller.show_tx = False
        self.controller.show_rx = True
        print("Now showing RX only.")

    def do_show_both(self, arg):
        "show_both -- log both TX and RX frames"
        self.controller.show_tx = True
        self.controller.show_rx = True
        print("Now showing both TX and RX.")

    def do_exit(self, arg):
        "exit -- quit the shell"
        return True

    def do_EOF(self, arg):
        return True

