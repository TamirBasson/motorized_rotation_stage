from __future__ import annotations

import argparse
import sys

from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm import CommunicationError, auto_detect_controller_port
from pc_app.comm.remote_client import RemoteCommunicationClient
from pc_app.comm.remote_server import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, RemoteCommunicationServer
from pc_app.ui.main_window import MainWindow


def main() -> None:
    api: RotationStageAPI | None = None
    embedded_server: RemoteCommunicationServer | None = None
    resolved_controller_port: str | None = None
    try:
        args = _parse_args()
        api = _build_ui_client(args)
        try:
            print(f"Connecting dashboard to shared server at {args.server_host}:{args.server_port}...")
            api.start()
        except CommunicationError:
            if args.no_start_server:
                raise

            resolved_controller_port = args.port or auto_detect_controller_port()
            print(
                "Shared server was not running. "
                f"Starting embedded communication server for controller {resolved_controller_port}..."
            )
            embedded_server = RemoteCommunicationServer.from_serial_port(
                port=resolved_controller_port,
                baudrate=args.baudrate,
                read_timeout=args.read_timeout,
                write_timeout=args.write_timeout,
                host=args.server_host,
                server_port=args.server_port,
                connect_settle_seconds=args.connect_settle_seconds,
            )
            embedded_server.start()
            api = _build_ui_client(args)
            api.start()

        window = MainWindow(api)
        window.set_status(
            "Controller Connected",
            (
                f"Connected through the shared communication server at {args.server_host}:{args.server_port}. "
                "Telemetry and commands can now be shared with API clients."
            ),
            "success",
        )
        window.protocol("WM_DELETE_WINDOW", lambda: _close(window, api, embedded_server))
        window.mainloop()
    except CommunicationError as exc:
        print(f"Hardware UI startup failed: {exc}", file=sys.stderr)
        print(
            "If the Arduino is connected, verify that it appears as a USB serial port, "
            "the shared server can bind to localhost, and pass the controller port explicitly if auto-detection is ambiguous.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected hardware UI error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        if api is not None:
            api.stop()
        if embedded_server is not None:
            embedded_server.stop()

def _build_ui_client(args: argparse.Namespace) -> RotationStageAPI:
    return RotationStageAPI(
        RemoteCommunicationClient(
            host=args.server_host,
            port=args.server_port,
            client_type="ui",
            client_name="Dashboard UI",
            connect_timeout=args.connect_timeout,
        )
    )


def _close(
    window: MainWindow,
    api: RotationStageAPI,
    embedded_server: RemoteCommunicationServer | None,
) -> None:
    window.shutdown()
    api.stop()
    if embedded_server is not None:
        embedded_server.stop()
    window.destroy()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the Motion Control Dashboard using the real controller over USB serial.",
    )
    parser.add_argument(
        "port",
        nargs="?",
        help='Optional controller serial port, for example "COM3". Used only when this UI needs to start the shared server itself.',
    )
    parser.add_argument("--baudrate", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--read-timeout", type=float, default=0.1, help="Serial read timeout in seconds")
    parser.add_argument("--write-timeout", type=float, default=1.0, help="Serial write timeout in seconds")
    parser.add_argument("--server-host", default=DEFAULT_SERVER_HOST, help="Shared communication server host")
    parser.add_argument("--server-port", type=int, default=DEFAULT_SERVER_PORT, help="Shared communication server TCP port")
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=2.0,
        help="Timeout in seconds when connecting to the shared server",
    )
    parser.add_argument(
        "--connect-settle-seconds",
        type=float,
        default=2.5,
        help="Delay after opening the controller serial port before the embedded server accepts commands",
    )
    parser.add_argument(
        "--no-start-server",
        action="store_true",
        help="Only connect to an existing shared server; do not start one inside the UI process",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
