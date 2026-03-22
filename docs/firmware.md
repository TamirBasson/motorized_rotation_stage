# Motorized Rotation Stage Controller - Firmware Design

## Purpose

This document defines the embedded firmware design for the Motorized Rotation Stage Controller.

The firmware runs on an **Arduino Nano** and is responsible for:
- receiving commands from the PC over USB serial
- parsing and validating commands
- controlling the stepper motor
- tracking internal position based on step count
- handling homing / mechanical zero
- generating telemetry
- supporting immediate command override

The firmware must be fully non-blocking and remain responsive during motion.

---

## Hardware Platform

### Microcontroller
The firmware is designed for:

- **Arduino Nano**

### Why Arduino Nano
Arduino Nano was selected because:
- it is compact and easy to integrate near the driver and stage
- it provides enough I/O for:
  - step signal
  - direction signal
  - enable signal if needed
  - mechanical zero input
  - USB serial communication
- it is suitable for an initial embedded implementation of this controller

### Important Constraint
Arduino Nano is a resource-limited platform.

Therefore the firmware must be:
- lightweight
- modular in logic
- non-blocking
- efficient in RAM usage
- careful with string parsing and buffering

---

## Motion Engine

### FastAccelStepper
The firmware uses:

- **FastAccelStepper**

### Why FastAccelStepper
FastAccelStepper is used because:
- it provides reliable step pulse generation
- it avoids manual timing using blocking code
- it allows the firmware main loop to stay responsive
- it is more suitable than delay-based step generation for concurrent motion and communication

### Design Intent
FastAccelStepper is responsible for the timing-critical part of motion generation.

The firmware must be designed so that:
- pulse generation is handled by FastAccelStepper
- the main loop supervises high-level behavior
- serial communication and telemetry can continue while the motor is moving
- command override remains responsive

### Critical Rule
Do not implement motion using:
- `delay()`
- manual pulse loops
- blocking movement loops that wait for motion completion

FastAccelStepper must be treated as the low-level motion engine, while the firmware state machine manages what the system should do next.

---

## Initial Implementation Strategy

For the first implementation stage, the firmware will be implemented in a single:

- `main.cpp`

This is intentional, in order to:
- simplify development
- speed up debugging
- keep all control flow visible in one place
- reach a working prototype quickly

This is acceptable because the system is still relatively small.

However, even though the firmware is implemented in one file, it must still be written in a **logically modular** way.

The code must be organized into clearly separated sections and helper functions so that it can be split into multiple files later if needed, without changing the architecture.

---

## Single-File Design Rule

The firmware may live in one file physically, but it must still be modular logically.

That means:
- use clear sections
- use structs for data
- use enums for states
- use helper functions for behavior
- keep `setup()` and `loop()` short and readable
- avoid mixing unrelated logic in one code block

### Critical Rule
Do not turn `main.cpp` into one giant unreadable loop.

---

## Recommended `main.cpp` Structure

The single `main.cpp` file should be organized in this order:

1. includes
2. pin definitions and constants
3. enums and structs
4. configuration variables
5. runtime state variables
6. serial receive buffer and protocol helpers
7. command parsing functions
8. command execution functions
9. motion control functions
10. position tracking functions
11. homing functions
12. telemetry functions
13. setup
14. loop

---

## Suggested Internal Sections

A recommended layout inside `main.cpp` is:

```cpp
// ================================
// Includes
// ================================

// ================================
// Pin definitions and constants
// ================================

// ================================
// Enums and structs
// ================================

// ================================
// Configuration parameters
// ================================

// ================================
// Runtime state
// ================================

// ================================
// FastAccelStepper objects
// ================================

// ================================
// Serial protocol helpers
// ================================

// ================================
// Command parsing
// ================================

// ================================
// Command execution
// ================================

// ================================
// Motion control
// ================================

// ================================
// Position tracking
// ================================

// ================================
// Homing logic
// ================================

// ================================
// Telemetry generation
// ================================

// ================================
// setup()
// ================================

// ================================
// loop()
// ================================