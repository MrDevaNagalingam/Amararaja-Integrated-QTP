"""Target entry point: python3 main.py"""
import argparse
import config
from tcp_server import serve


def main():
    parser = argparse.ArgumentParser(description="Amararaja Integrated QTP Target")
    parser.add_argument("--host", default=config.QTP_BIND_ADDRESS)
    parser.add_argument("--port", type=int, default=config.QTP_TCP_PORT)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535")
    try:
        serve(args.host, args.port)
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        print("[QTP] Target error: " + str(exc), flush=True)
        return 1
    finally:
        print("[QTP] Target stopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
