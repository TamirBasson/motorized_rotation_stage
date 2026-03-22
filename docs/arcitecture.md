# Motorized Rotation Stage Controller - Architecture

## High-Level Architecture

The system consists of four logical layers:

1. Hardware Layer
2. Embedded Controller Layer
3. PC Communication Layer
4. PC Client Layer

---

## 1. Hardware Layer

Includes:
- motorized rotation stage
- stepper motor
- motor driver
- mechanical zero sensor / home signal
- microcontroller / controller board

Responsibilities:
- execute physical motion
- expose mechanical zero signal
- receive step / direction control from the controller

---

## 2. Embedded Controller Layer

This is the firmware running on the microcontroller.

Main responsibilities:
- receive commands over USB serial
- parse and validate commands
- control motion through FastAccelStepper
- maintain internal position tracking
- handle homing logic
- generate ACK / ERR / telemetry responses
- support immediate command override

Recommended internal modules:
- `serial_interface`
- `protocol_parser`
- `command_dispatcher`
- `motion_controller`
- `position_tracker`
- `homing_manager`
- `telemetry_manager`
- `config_manager`
- `safety_manager`

---

## 3. PC Communication Layer

This is a single communication owner process on the PC.

### Critical Rule
Only ONE PC process may open the serial port connected to the controller.

This process is the:
- Communication Manager
- or Communication Server

Responsibilities:
- open and manage the serial connection
- send commands to the controller
- receive all incoming messages
- parse ACK / ERR / TLM messages
- distribute telemetry and responses internally to multiple PC clients

This is required because UI and Python API must operate simultaneously, but serial is a single hardware resource.

---

## 4. PC Client Layer

Includes:
- UI application
- Python API / automation scripts

### UI Application
Responsibilities:
- manual operator control
- parameter configuration
- telemetry display

### Python API / Automation Scripts
Responsibilities:
- programmatic command sending
- telemetry subscription
- automation logic

### Rule
Neither the UI nor the Python API may access the serial port directly.
Both must communicate through the Communication Manager.

---

## Telemetry Fan-Out Model

The communication architecture must work as follows:

1. The controller sends telemetry once over serial
2. The Communication Manager reads it once
3. The Communication Manager distributes the parsed telemetry to:
   - UI
   - Python API / automation clients

This ensures:
- no serial conflicts
- consistent data for all clients
- simultaneous UI + API operation
- clean scalability

---

## Motion Architecture

The embedded side should use a high-level non-blocking state machine.

Suggested states:
- `IDLE`
- `MOVING_ABSOLUTE`
- `CONSTANT_ROTATE`
- `MOVING_RELATIVE`
- `HOMING_MECHANICAL_ZERO`
- `MOVING_TO_VIRTUAL_ZERO`
- `STOPPING`
- `ERROR`

Rules:
- every command maps to a state transition
- a new valid command may preempt the current state
- no state may block the firmware loop

---

## Position Architecture

Internal position tracking is based on:
- step count
- steps per revolution
- gear ratio
- virtual zero offset

Derived outputs:
- mechanical angle
- virtual angle
- steps

The position tracker is the internal source of truth for telemetry and motion logic.

---

## Firmware Main Loop Concept

The firmware main loop should repeatedly:
1. read serial non-blockingly
2. assemble full messages
3. parse commands
4. send ACK / ERR
5. update state machine
6. issue motion commands to FastAccelStepper
7. update position state
8. check homing events
9. send telemetry if due

The loop must never wait in place for motion completion.

---

## Key Architectural Rules

- never allow multiple serial owners on the PC
- never couple UI logic directly to protocol parsing
- never couple serial parsing directly to motion timing
- never block the firmware while motion is active
- always separate motion, communication, telemetry, and presentation concerns