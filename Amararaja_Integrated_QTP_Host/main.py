"""PC entry point: python main.py 192.168.11.69"""
import argparse
import config
from tcp_handler import TCPCommunicator
from command_handler import CommandHandler
from interactive_menu import interactive_mode


def main():
    parser = argparse.ArgumentParser(description="Amararaja Integrated QTP Host")
    parser.add_argument("ip", nargs="?", default=config.TARGET_IP)
    parser.add_argument("--port", type=int, default=config.QTP_TCP_PORT)
    parser.add_argument("--report-dir", default=config.LOG_DIRECTORY)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    tcp = TCPCommunicator(args.ip, args.port)
    handler = None
    try:
        handler = CommandHandler(tcp, args.report_dir)
        handler.emit("[QTP] Connecting to {}:{}...".format(args.ip, args.port))
        tcp.connect()
        handler.emit("[QTP] Connected to target")
        handler.execute("PING")
        interactive_mode(handler)
    except (OSError, ValueError) as exc:
        (handler.emit if handler else print)("[QTP] Error: " + str(exc))
        return 1
    except KeyboardInterrupt:
        print("\n[QTP] Host interrupted; target shutdown is not confirmed")
        return 1
    finally:
        tcp.disconnect()
        if handler:
            handler.emit("[QTP] Shutdown complete")
            handler.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
