from __future__ import annotations

import argparse
from datetime import datetime
import sys
import time

from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm import CommunicationError, TelemetryState, auto_detect_controller_port


def main() -> None:
    # This example uses the high-level API only.
    # The script never opens the serial port directly; the CommunicationManager
    # inside RotationStageAPI is the single serial owner.
    api: RotationStageAPI | None = None
    subscription = None

    try:
        args = _parse_args()
        port = args.port
        if port is None:
            port = auto_detect_controller_port()
            print(f"Auto-detected controller serial port: {port}")

        api = RotationStageAPI.from_serial_port(port, baudrate=args.baudrate)
        print(f"Connecting to controller on {port} at {args.baudrate} baud...")
        api.start()

        # Subscribe once to live telemetry so every movement example prints the
        # current stage state as the controller reports it.
        subscription = api.subscribe_telemetry(_print_telemetry, replay_latest=False)

        # Enable periodic telemetry from the controller.
        # A higher value gives more updates per second.
        ack = api.set_telemetry_rate(args.telemetry_rate)
        print(f"Telemetry configured: {ack}")

        # ---------------------------------------------------------------------
        # Example 1: Absolute move
        # ---------------------------------------------------------------------
        # Goal:
        # Move to an absolute angular target in the controller coordinate system.
        #
        # Meaning of the parameters:
        # - angle_deg: requested destination angle
        # - virt_zero_offset_deg: Virtual Zero Reference (same parameter as protocol / firmware).
        #   Mechanical = Virtual + Reference, so Virtual = Mechanical − Reference.
        # - speed_deg_per_sec: commanded angular speed
        # - direction: preferred motion direction ("CW" or "CCW")
        #
        # Important:
        # ACK means the controller accepted and decoded the command.
        # It does NOT mean the stage has already reached the final position.
        print("\n=== Example 1: Absolute move ===")
        print(
            api.rotate_absolute(
                angle_deg=120.0,
                virt_zero_offset_deg=-12.5,
                speed_deg_per_sec=5.0,
                direction="CW",
            )
        )
        time.sleep(2.0)

        # ---------------------------------------------------------------------
        # Example 2: Relative move
        # ---------------------------------------------------------------------
        # Goal:
        # Move by a delta relative to the current position.
        #
        # The relative move command uses a positive magnitude plus an explicit
        # direction. This is useful for scan patterns and incremental adjustment.
        print("\n=== Example 2: Relative move ===")
        print(api.rotate_relative(delta_angle_deg=45.0, speed_deg_per_sec=3.0, direction="CCW"))
        time.sleep(2.0)

        # ---------------------------------------------------------------------
        # Example 3: Continuous rotation
        # ---------------------------------------------------------------------
        # Goal:
        # Start a continuous rotation that keeps running until another command
        # overrides it or an explicit stop command is sent.
        #
        # This mode is useful for endurance tests, scanning, or any experiment
        # where the stage should keep rotating instead of stopping at a target.
        print("\n=== Example 3: Continuous rotation ===")
        print(api.constant_rotate(speed_deg_per_sec=2.5, direction="CCW"))
        time.sleep(3.0)

        # Stop the stage after the continuous rotation example.
        print("\nStopping motion...")
        print(api.stop_rotation())

        # Read the latest telemetry snapshot stored by the CommunicationManager.
        # This is the most recent parsed telemetry message received from the controller.
        latest = api.get_latest_telemetry()
        print(f"Latest telemetry snapshot: {latest}")
    except CommunicationError as exc:
        print(f"API example failed: {exc}", file=sys.stderr)
        print(
            "If the Arduino is connected, verify that it appears as a USB serial port "
            "and pass the port explicitly if auto-detection is ambiguous.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected API example error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        if subscription is not None:
            subscription.unsubscribe()
        if api is not None:
            api.stop()
            print("Disconnected.")


def _print_telemetry(telemetry: TelemetryState) -> None:
    # This callback represents what an automation script or a UI would receive
    # from the shared CommunicationManager telemetry fan-out.
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(
        f"[{timestamp}] "
        f"mech={telemetry.mechanical_angle_deg:.2f} deg | "
        f"virt={telemetry.virtual_angle_deg:.2f} deg | "
        f"running={telemetry.running} | "
        f"speed={telemetry.speed_deg_per_sec:.2f} deg/s | "
        f"dir={telemetry.direction.value} | "
        f"steps={telemetry.steps}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Example script showing absolute, relative, and continuous motion API usage.",
    )
    parser.add_argument(
        "port",
        nargs="?",
        help='Optional serial port for the controller, for example "COM3". If omitted, the script auto-detects it.',
    )
    parser.add_argument("--baudrate", type=int, default=115200, help="Serial baud rate")
    parser.add_argument(
        "--telemetry-rate",
        type=int,
        default=5,
        help="Telemetry rate in Hz (-1 immediate, 0 off, 1..100 cyclic)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
