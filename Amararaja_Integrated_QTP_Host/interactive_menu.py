TESTS = {
    "1": ("TC-01 Ping test", "TEST_PING"),
    "2": ("TC-02 Selec EM4M AC Energy Meter", "TEST_SELEC_EM4M"),
    "3": ("TC-03 EDC 2150 DC Energy Meter", "TEST_EDC2150"),
    "4": ("TC-04 CAN Controller Node Start all", "TEST_CAN_CONTROLLER_START_ALL"),
    "5": ("TC-04 CAN Controller Node Stop All", "TEST_CAN_CONTROLLER_STOP_ALL"),
    "6": ("TC-04 CAN Controller Node Set All", "TEST_CAN_CONTROLLER_SET_ALL"),
    "7": ("TC-04 CAN Controller Node Start", "TEST_CAN_CONTROLLER_START"),
    "8": ("TC-04 CAN Controller Node Stop", "TEST_CAN_CONTROLLER_STOP"),
    "9": ("TC-05 RFID Verification", "TEST_RFID"),
}

TEST_MESSAGES = {}


def display_main_menu():
    print("\n" + "=" * 80)
    print(" QTP INTERACTIVE TEST MENU ".center(80))
    print("=" * 80)
    for number, (title, command) in sorted(TESTS.items(), key=lambda item: int(item[0])):
        print("{:2d}. {}".format(int(number), title))
    print("\n" + "=" * 80)
    print(" OPTIONS ".center(80))
    print("=" * 80)
    print("  Enter test number (1-{})".format(len(TESTS)))
    print("  Enter 'ping' to run TC-01")
    print("  Enter 'echo <text>' to send text")
    print("  Enter 'q' to stop target and quit")
    print("=" * 80)


def run_single_test(handler, test_num):
    key = str(test_num)
    if key not in TESTS:
        print("[ERROR] Test #{} not found!".format(test_num))
        return True
    test_desc, test_cmd = TESTS[key]
    handler.run_test(test_num, test_desc, test_cmd, TEST_MESSAGES.get(test_cmd))
    return True


def interactive_mode(handler):
    while True:
        display_main_menu()
        try:
            text = input("\nEnter your choice: ").strip()
        except (EOFError, KeyboardInterrupt):
            text = "q"
        if not text:
            continue
        if text.lower() in {"q", "quit", "exit", "0", "stop_qtp"}:
            handler.emit("[INFO] Sending stop command to target...")
            result = handler.execute_command("STOP_TARGET")
            if result["status"] != "PASS":
                raise ValueError("Target did not acknowledge shutdown")
            handler.emit("[QTP] Target stopped.")
            handler.emit("[INFO] Exiting test mode...")
            return
        if text.lower() == "ping":
            run_single_test(handler, 1)
        elif text.isdigit() and text in TESTS:
            run_single_test(handler, int(text))
        elif text.lower().startswith("echo "):
            handler.execute_command("ECHO", {"text": text[5:]})
        else:
            handler.execute_command(text.upper())
