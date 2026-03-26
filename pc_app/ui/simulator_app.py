from __future__ import annotations

import argparse
import sys

from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm import CommunicationError
from pc_app.ui.main_window import MainWindow


def main() -> None:
    api: RotationStageAPI | None = None
    try:
        args = _parse_args()
        api = RotationStageAPI.from_simulator(read_timeout=args.read_timeout)
        print("Connecting dashboard to simulated controller...")
        api.start()

        window = MainWindow(api)
        window.set_status(
            "Simulator Connected",
            "The dashboard is talking to the simulated controller through the Communication Manager.",
            "success",
        )
        window.protocol("WM_DELETE_WINDOW", lambda: _close(window, api))
        window.mainloop()
    except CommunicationError as exc:
        print(f"Simulator UI startup failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected simulator UI error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        if api is not None:
            api.stop()


def _close(window: MainWindow, api: RotationStageAPI) -> None:
    api.stop()
    window.destroy()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the Motion Control Dashboard against the simulated controller backend.",
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=0.05,
        help="Simulator serial read timeout in seconds",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
