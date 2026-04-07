from __future__ import annotations

import argparse
import sys
import time

from pc_app.comm import CommunicationError, auto_detect_controller_port
from pc_app.comm.remote_server import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, RemoteCommunicationServer


def main() -> None:
    server: RemoteCommunicationServer | None = None
    try:
        args = _parse_args()
        controller_port = args.port or auto_detect_controller_port()
        server = RemoteCommunicationServer.from_serial_port(
            port=controller_port,
            baudrate=args.baudrate,
            read_timeout=args.read_timeout,
            write_timeout=args.write_timeout,
            host=args.host,
            server_port=args.server_port,
            connect_settle_seconds=args.connect_settle_seconds,
        )
        server.start()
        print(
            f"Shared communication server is running on {server.host}:{server.port} "
            f"for controller {controller_port}."
        )
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Stopping shared communication server...")
    except CommunicationError as exc:
        print(f"Shared communication server failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected shared communication server error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        if server is not None:
            server.stop()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the shared communication server that owns the hardware serial connection.",
    )
    parser.add_argument(
        "port",
        nargs="?",
        help='Optional controller serial port, for example "COM3". If omitted, the port is auto-detected.',
    )
    parser.add_argument("--baudrate", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--read-timeout", type=float, default=0.1, help="Serial read timeout in seconds")
    parser.add_argument("--write-timeout", type=float, default=1.0, help="Serial write timeout in seconds")
    parser.add_argument("--host", default=DEFAULT_SERVER_HOST, help="Shared communication server bind host")
    parser.add_argument("--server-port", type=int, default=DEFAULT_SERVER_PORT, help="Shared communication server TCP port")
    parser.add_argument(
        "--connect-settle-seconds",
        type=float,
        default=2.5,
        help="Delay after opening the controller serial port before serving client requests",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
