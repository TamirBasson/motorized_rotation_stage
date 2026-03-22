# Motorized Rotation Stage Controller - Requirements Summary

## System Purpose

The system is intended for experiments, testing, data collection, and computer vision validation where an object must rotate and its angular position must be measured during motion.

The controller operates a motorized rotation stage and supports remote PC control over USB.

---

## General Requirements

- The controller shall provide precise, reliable, and repeatable angular motion control.
- The controller shall maintain an internal angular position counter based on step count and gear ratio configuration.
- The angular accuracy shall be 0.05 degrees.
- The controller shall support both:
  - manual operation through a UI
  - automated operation through external Python API / script
- Manual UI operation and automated API operation shall be available simultaneously.
- If a new command is received while another command is executing, the new command shall override the currently executing command.
- Motion control shall be based primarily on stepper pulse generation and step counting.

---

## Supported Commands

### 1. Rotate to Absolute Angle
Parameters:
- angle: 0 to 360 deg
- offset to virtual zero: -180 to +180 deg
- speed: 0.1 to 20 deg/sec, step 0.1
- direction: CW / CCW / NULL

Behavior:
- rotate to target angle
- target is calculated using the angle and virtual zero offset
- if direction is NULL, use the shortest path

---

### 2. Constant Rotate
Parameters:
- speed: 0.1 to 20 deg/sec, step 0.1
- direction: CW / CCW

Behavior:
- rotate continuously until a new command is received

---

### 3. Rotate to Relative Angle
Parameters:
- angle: -360 to +360 deg
- speed: 0.1 to 20 deg/sec, step 0.05

Behavior:
- rotate by delta angle from current position
- positive = CW
- negative = CCW

---

### 4. Rotate to Mechanical Zero
Parameters:
- none

Behavior:
- rotate until the hardware mechanical-zero signal is found
- reset the angle counter when zero is reached
- if not found after one full rotation, send an error

---

### 5. Rotate to Virtual Zero
Parameters:
- virtual zero offset

Behavior:
- rotate to calculated virtual zero
- use shortest path
- do not reset the angle counter

---

### 6. Stop
Parameters:
- none

Behavior:
- immediately stop the platform rotation

---

### 7. Telemetry Command
Parameters:
- -1 = send immediate telemetry
- 0 = stop cyclic telemetry
- 1 to 100 = send cyclic telemetry at requested Hz

---

## Command Responses

### ACK
For a valid decoded command:
- send acknowledgment with command and parameters

### ERR
For invalid or undecodable input:
- send an error response with the cause

### Mechanical Zero Not Found
If homing fails after one full rotation:
- send a dedicated error

---

## Telemetry Content

Each telemetry block shall include:
- mechanical angle
- virtual angle
- motor running status
- rotation speed
- rotation direction
- steps

Telemetry shall be supported:
- on demand
- cyclically up to 100 Hz

---

## UI Requirements

The UI shall:
- support all commands
- display all telemetry
- allow parameter configuration

Configurable parameters:
- motor steps per revolution
- gear ratio
- offset to virtual zero angle

UI display refresh rate:
- 2 Hz

---

## Python API Requirements

A Python API shall be provided for scripts.

The API shall support:
- sending commands
- receiving telemetry
- working simultaneously with the UI through the same communication architecture