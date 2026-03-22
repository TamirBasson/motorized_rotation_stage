# Motorized Rotation Stage Controller

## Overview

Motorized Rotation Stage Controller is a combined embedded and PC software project for driving a stepper-based rotation stage from a computer over USB serial.

The system is intended for:

- experiments and lab automation
- repeatable positioning and rotation
- data collection workflows
- computer vision validation setups

The controller must rotate to commanded angles, support continuous rotation, track angular position from step count, expose telemetry during motion, and allow both manual control and Python automation at the same time.

## Engineering Goals

This project is designed as a real control system, not a blocking script.

The most important engineering goals are:

- deterministic stepper motion
- fully non-blocking firmware behavior
- responsive command handling while the motor is moving
- continuous telemetry during motion
- immediate override of the currently active command
- one shared PC communication layer for both UI and Python clients

## System Architecture

The system has two major runtime parts.

### Embedded controller

The embedded side runs on an Arduino Nano and is responsible for:

- receiving and parsing serial commands
- validating command parameters
- controlling the motor with `FastAccelStepper`
- maintaining position state from step count
- handling homing to mechanical zero
- sending `ACK`, `ERR`, and `TLM` messages

### PC software

The PC side is responsible for:

- owning the USB serial connection
- sending commands to the controller
- receiving and parsing controller responses
- storing and distributing telemetry
- serving both manual UI control and Python automation

The critical architectural rule is that only one PC-side component may own the serial port. In this repository that role belongs to the Communication Manager. The UI and the Python API must communicate through that layer rather than opening the serial port directly.

## Repository Layout

```text
docs/       Project requirements, protocol, architecture, firmware, PC app, and tasks
firmware/   Arduino Nano firmware
pc_app/     Communication layer, API, and UI code
tests/      Unit and UI-preview tests
```

## Current Implementation Status

The repository already contains:

- embedded firmware in `firmware/src/main.cpp`
- a PC-side `CommunicationManager` that owns the serial port
- a Python API wrapper in `pc_app/api/rotation_stage_api.py`
- protocol parsing and message models
- a preview UI that can run without hardware
- tests for protocol parsing and telemetry fan-out

The repository does not yet provide a single packaged production launcher for the full hardware-backed PC application, so the README below shows the current bring-up commands that are available today.

## Basic Bring-Up Commands

### 1. Create and activate a Python environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install pyserial
```

### 2. Run the automated tests

```powershell
python -m unittest discover -s tests -v
```

### 3. Launch the UI preview without hardware

This starts the local preview controller and UI so engineers can inspect the current desktop workflow without connecting an Arduino.

```powershell
python -m pc_app.ui.preview_app
```

### 4. Use the hardware communication layer from Python

There is not yet a dedicated CLI launcher for the real device, but the communication stack can already be activated from a Python session.

```powershell
python
```

```python
from pc_app.api.rotation_stage_api import RotationStageAPI

api = RotationStageAPI.from_serial_port("COM3")
api.start()

api.set_telemetry_rate(2)
print(api.get_latest_telemetry())

api.stop()
```

Replace `COM3` with the actual Arduino serial port on your machine.

## Command Model

The controller uses a line-based ASCII serial protocol. Each message is one line and begins with a message family:

- `CMD` for commands sent to the controller
- `ACK` for successfully decoded commands
- `ERR` for invalid commands or runtime failures
- `TLM` for telemetry updates

Examples:

```text
CMD,ROT_ABS,120.00,-15.00,5.0,CW
CMD,ROT_CONST,2.5,CCW
CMD,ROT_REL,-45.00,3.0
CMD,ROT_HOME
CMD,STOP
CMD,TLM,10
```

Important protocol rule: `ACK` only means the command was received and decoded successfully. It does not mean the motion is complete.

## Non-Negotiable Design Rules

These rules should be preserved as the codebase evolves:

- firmware must remain fully non-blocking
- stepper motion must be driven by `FastAccelStepper`
- telemetry and command handling must not interfere with motion timing
- new valid commands must override the current command
- the initial firmware implementation stays in a single `main.cpp`
- UI and Python API must share one Communication Manager
- malformed serial input must never crash the firmware

## Main References

For project intent and constraints, start with:

- `docs/mission.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/protocol.md`
- `docs/firmware.md`
- `docs/pc_app.md`
- `docs/tasks.md`
