
---

# `docs/pc_software.md`

```markdown
# Motorized Rotation Stage Controller - PC Software Design

## Purpose

This document defines the PC-side software architecture for the Motorized Rotation Stage Controller.

The PC software is responsible for:
- communicating with the controller over USB serial
- exposing a manual control UI
- exposing a Python API for automation scripts
- receiving and distributing telemetry
- enforcing a single-owner communication architecture

The PC side must allow:
- UI operation
- API / automation operation
- simultaneous use of both

---

## Main Design Rule

## Single Serial Owner
Only one process on the PC is allowed to open and manage the serial port connected to the controller.

This process is called the:

- **Communication Manager**
- or **Communication Server**

### Why this is mandatory
Serial is a single hardware resource.

If both:
- the UI
- and the automation script

try to open the same serial port directly, the system will become unreliable or fail.

Therefore:
- the UI must not access serial directly
- the Python API must not access serial directly
- all serial communication must pass through the Communication Manager

---

## High-Level PC Architecture

The PC side consists of three logical layers:

1. Communication Manager
2. UI Application
3. Python API / Automation Client

---

## 1. Communication Manager

This is the core PC-side communication process.

### Responsibilities
- open and own the serial port
- send commands to the controller
- receive ACK / ERR / TLM messages
- parse incoming messages
- store latest telemetry state
- distribute telemetry to multiple clients
- provide a safe interface for UI and automation

### Communication Rule
Everything must pass through this layer.

This layer is the single source of truth for communication with the controller.

---

## 2. UI Application

The UI is the manual operator interface.

### Responsibilities
- present controls for all supported commands
- allow parameter input
- display telemetry
- refresh display at 2 Hz
- provide clear operator feedback

### Important Rule
The UI must never open the serial port directly.
It must communicate only through the Communication Manager.

---

## 3. Python API / Automation Client

The Python API provides programmatic access for scripts.

### Responsibilities
- expose high-level command functions
- expose telemetry access
- allow automation scripts to subscribe to telemetry or poll latest state
- coexist with the UI through the shared communication layer

### Important Rule
The Python API must never open the serial port directly.
It must communicate only through the Communication Manager.

---

## Telemetry Fan-Out Model

Telemetry must be handled as follows:

1. the controller sends telemetry once over serial
2. the Communication Manager reads it once
3. the Communication Manager parses it
4. the Communication Manager distributes it to:
   - UI
   - Python API / automation clients

### Benefits
- no serial conflicts
- consistent telemetry across all clients
- simple scaling to multiple consumers
- centralized parsing and validation

---

## Recommended Software Structure

Recommended PC-side structure:

```text
pc_app/
├── comm/
│   ├── serial_manager.py
│   ├── protocol_parser.py
│   ├── telemetry_bus.py
│   └── communication_server.py
├── api/
│   ├── rotation_stage_api.py
│   └── telemetry_models.py
├── ui/
│   ├── main_window.py
│   ├── control_panel.py
│   └── telemetry_view.py
└── main.py