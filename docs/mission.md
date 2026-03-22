# Motorized Rotation Stage Controller - Mission

## Purpose

Build a complete control system for a motorized rotation stage used in experiments, testing, data collection, and computer vision validation.

The system must rotate an object precisely while continuously tracking and reporting its angular position.

The controller shall be operated from a PC over USB and support both:
- manual control through a UI
- automated control through a Python API / script

These two operation modes must be available simultaneously.

---

## Primary Engineering Goal

Build a robust, non-blocking control system in which:

- stepper motion remains accurate and deterministic
- command handling remains responsive
- telemetry continues while motion is running
- new commands can override the current command immediately
- the architecture stays modular and maintainable

This project must behave like a real control system, not a blocking sequential script.

---

## Core Principles

### 1. Non-Blocking by Design
The firmware and PC software must avoid blocking behavior.

Never rely on:
- delay-based flow
- waiting loops for motion completion
- blocking serial reads as the main control mechanism

---

### 2. Concurrent Operation
The following must run together without interfering with each other:
- stepper motion
- command reception
- telemetry transmission
- UI updates
- Python automation

---

### 3. Deterministic Motion
Use FastAccelStepper as the low-level motion engine so that pulse generation is handled independently from communication and high-level logic.

---

### 4. Immediate Override
If a new command arrives while another is executing, the new command must override the currently running command.

---

### 5. Single Serial Owner
Only one process on the PC is allowed to own the USB serial connection to the controller.

All PC-side clients must communicate through that single communication owner.

---

## Mission Outcome

The final system must:
- control the motorized rotation stage accurately
- track position from step count and configuration
- support UI and Python API simultaneously
- provide reliable ACK / ERR / telemetry behavior
- remain responsive during motion
- be easy to extend and debug