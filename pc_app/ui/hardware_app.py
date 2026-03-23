from __future__ import annotations

import argparse
import sys

from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm import CommunicationError, auto_detect_controller_port
from pc_app.ui.main_window import MainWindow


def main() -> None:
    api: RotationStageAPI | None = None
    try:
        args = _parse_args()
        port = args.port or auto_detect_controller_port()
        api = RotationStageAPI.from_serial_port(
            port=port,
            baudrate=args.baudrate,
            read_timeout=args.read_timeout,
            write_timeout=args.write_timeout,
        )

        print(f"Connecting dashboard to controller on {port}...")
        api.start()
        window = MainWindow(api)
        window.set_status(
            "Controller Connected",
            f"Connected to controller on {port}. Telemetry is managed through the shared Communication Manager.",
            "success",
        )
        window.protocol("WM_DELETE_WINDOW", lambda: _close(window, api))
        window.mainloop()
    except CommunicationError as exc:
        print(f"Hardware UI startup failed: {exc}", file=sys.stderr)
        print(
            "If the Arduino is connected, verify that it appears as a USB serial port "
            "and pass the port explicitly if auto-detection is ambiguous.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected hardware UI error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        if api is not None:
            api.stop()


def _close(window: MainWindow, api: RotationStageAPI) -> None:
    api.stop()
    window.destroy()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the Motion Control Dashboard using the real controller over USB serial.",
    )
    parser.add_argument(
        "port",
        nargs="?",
        help='Optional serial port for the controller, for example "COM3". If omitted, the port is auto-detected.',
    )
    parser.add_argument("--baudrate", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--read-timeout", type=float, default=0.1, help="Serial read timeout in seconds")
    parser.add_argument("--write-timeout", type=float, default=1.0, help="Serial write timeout in seconds")
    return parser.parse_args()


if __name__ == "__main__":
    main()
