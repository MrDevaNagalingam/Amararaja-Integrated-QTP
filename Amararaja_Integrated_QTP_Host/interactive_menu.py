TESTS = {
    "1": ("TC-01 Ping test", "TEST_PING"),
    "2": ("TC-02 Selec EM4M AC Energy Meter", "TEST_SELEC_EM4M"),
    "3": ("TC-03 EDC 2150 DC Energy Meter", "TEST_EDC2150"),
    "4": ("TC-04 Read IMD 1", "TEST_IMD1"),
    "5": ("TC-04 Read IMD 2", "TEST_IMD2"),
    "6": ("TC-05 CAN Controller Node Keep Alive Start", "TEST_CAN_KEEP_ALIVE_START"),
    "7": ("TC-05 CAN Controller Node Keep Alive Stop", "TEST_CAN_KEEP_ALIVE_STOP"),
    "8": ("TC-05 CAN Controller Node Start all", "TEST_CAN_CONTROLLER_START_ALL"),
    "9": ("TC-05 CAN Controller Node Stop All", "TEST_CAN_CONTROLLER_STOP_ALL"),
    "10": ("TC-05 CAN Controller Node Set All", "TEST_CAN_CONTROLLER_SET_ALL"),
    "11": ("TC-05 CAN Controller Node Start", "TEST_CAN_CONTROLLER_START"),
    "12": ("TC-05 CAN Controller Node Stop", "TEST_CAN_CONTROLLER_STOP"),
    "13": ("TC-06 RFID Verification", "TEST_RFID"),
    "14": ("TC-08 4G network verification", "TEST_NETWORK_4G"),
    "15": ("TC-07 PT1000/Thermistor-10k Temperature Sensor", "TEST_TEMPERATURE_SENSOR"),
    "16": ("TC-12 Relay Control All OFF", "TEST_RELAY_CONTROL_ALL_OFF"),
    "17": ("TC-12 Relay Control DC1 ON", "TEST_RELAY_CONTROL_DC1_ON"),
    "18": ("TC-12 Relay Control DC2 ON", "TEST_RELAY_CONTROL_DC2_ON"),
    "19": ("TC-12 Relay Control AC ON", "TEST_RELAY_CONTROL_AC_ON"),
    "20": ("TC-12 Relay Control MERGER ON", "TEST_RELAY_CONTROL_MERGER_ON"),
    "21": ("Flash Phytec_MSP_DC.bin binary", "TEST_FLASH_PHYTEC_MSP_DC"),
    "22": ("Flash Coil_Control.bin binary", "TEST_FLASH_COIL_CONTROL"),
}
MENU_GROUPS = [
    ("QTP INTERACTIVE TEST MENU", range(1, 15)),
    ("MCU INTERACTIVE TEST MENU", range(15, 21)),
    ("MCU FLASH BINARY MENU", range(21, 23)),
]

TEST_MESSAGES = {}


def display_main_menu():
    print("\n" + "=" * 80)
    for heading, numbers in MENU_GROUPS:
        print(" {} ".format(heading).center(80))
        print("=" * 80)
        for number in numbers:
            key = str(number)
            if key in TESTS:
                title, command = TESTS[key]
                print("{:2d}. {}".format(number, title))
        print("=" * 80)
    print("\n" + "=" * 80)
    print(" OPTIONS ".center(80))
    print("=" * 80)
    print("  Enter test number (1-22)")
    print("  Enter 'ping' to run TC-01")
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
        else:
            print("[ERROR] Invalid choice: {}".format(text))

