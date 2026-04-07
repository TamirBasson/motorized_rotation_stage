# Shared Communication Server

## Purpose

The shared communication server is the single serial owner for the real controller.

It allows:

- the dashboard UI to stay open
- one or more Python API clients to connect at the same time
- one serial connection to the Arduino
- one telemetry stream fan-out to multiple PC-side clients

## Default Topology

On real hardware, the normal flow is:

1. Start `python -m pc_app.ui.hardware_app`
2. The UI connects to an existing localhost server, or starts an embedded one if needed
3. Run `python example_api_usage.py`
4. The API connects to the same localhost server instead of opening the serial port directly

Default server endpoint:

- host: `127.0.0.1`
- port: `8765`

## API Priority

The shared server supports an API control lease.

Current policy:

- API clients may acquire control
- while API control is active, UI motion commands are queued
- UI `STOP` bypasses the queue for safety
- telemetry continues to update for both UI and API clients

The example API script acquires API control by default.

## Standalone Server

If you want the server without opening the UI, run:

```powershell
python -m pc_app.comm.server_app COM5
```

Then connect the UI and API separately:

```powershell
python -m pc_app.ui.hardware_app --no-start-server
python example_api_usage.py
```

Replace `COM5` with the actual controller port when auto-detection is not desired.

## Direct Mode

For troubleshooting only, the example API script can still bypass the shared server:

```powershell
python example_api_usage.py COM5 --direct
```

Do not use direct mode while the shared UI/server is active, because that would create a second serial owner.
