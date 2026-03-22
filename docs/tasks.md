# Motorized Rotation Stage Controller - Tasks

## Current Development Plan

### Phase 1 - System Foundation
- [ ] create repository folder structure
- [ ] create docs folder and add core markdown files
- [ ] select microcontroller and define hardware pin mapping
- [ ] choose motor driver interface details

---

## Phase 2 - Embedded Firmware Skeleton
- [ ] create firmware project structure
- [ ] add serial interface module
- [ ] add protocol parser skeleton
- [ ] add command dispatcher skeleton
- [ ] integrate FastAccelStepper
- [ ] define motion state machine
- [ ] add stop override behavior

---

## Phase 3 - Position and Homing
- [ ] implement step-based position tracking
- [ ] implement mechanical angle calculation
- [ ] implement virtual angle calculation
- [ ] implement mechanical zero detection
- [ ] implement homing failure after one full rotation

---

## Phase 4 - Telemetry
- [ ] define telemetry struct
- [ ] implement immediate telemetry command
- [ ] implement cyclic telemetry scheduler
- [ ] include steps in telemetry
- [ ] verify telemetry does not block motion

---

## Phase 5 - PC Communication Layer
- [ ] create Communication Manager
- [ ] implement serial open / close / reconnect
- [ ] implement message parser for ACK / ERR / TLM
- [ ] implement telemetry fan-out
- [ ] ensure only one serial owner exists

---

## Phase 6 - Python API
- [ ] implement high-level command wrappers
- [ ] implement telemetry subscription interface
- [ ] support simultaneous UI + API usage

Expected API methods:
- [ ] `rotate_absolute(...)`
- [ ] `constant_rotate(...)`
- [ ] `rotate_relative(...)`
- [ ] `rotate_mechanical_zero()`
- [ ] `rotate_virtual_zero(...)`
- [ ] `stop()`
- [ ] `set_telemetry_rate(...)`
- [ ] `get_latest_telemetry()`
- [ ] `subscribe_telemetry(...)`

---

## Phase 7 - UI
- [ ] build basic control panel
- [ ] add command buttons / inputs
- [ ] add telemetry display
- [ ] add parameter configuration
- [ ] enforce 2 Hz UI refresh

---

## Validation Tasks
- [ ] verify command override works during motion
- [ ] verify telemetry continues during motion
- [ ] verify FastAccelStepper motion is not disturbed by communication
- [ ] verify homing behavior
- [ ] verify out-of-range parameters return ERR
- [ ] verify simultaneous UI + API behavior through Communication Manager

---

## Open Decisions
- [ ] choose MCU: Nano / Uno / ESP32 / other
- [ ] choose UI framework
- [ ] choose PC communication implementation: single process / socket server / other
- [ ] decide whether to add command-complete notifications later