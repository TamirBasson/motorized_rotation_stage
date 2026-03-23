# Motorized Rotation Stage Controller - Serial Protocol

## Protocol Goals

The protocol must be:
- human-readable during development
- easy to parse on embedded and PC sides
- robust against malformed input
- easy to debug over serial terminal
- easy to extend later

Recommended format:
- line-based ASCII text
- one message per line
- comma-separated fields

Message families:
- `CMD`
- `ACK`
- `ERR`
- `TLM`

---

## General Message Rules

- each message is one line
- fields are comma-separated
- first field defines message family
- second field defines message type
- message parsing must validate field count and parameter ranges
- invalid messages must return `ERR`

Example line ending:
- `\n`
- or `\r\n`

---

## Command Messages

### 1. Rotate Absolute
Format:
`CMD,ROT_ABS,<angle_deg>,<virt_zero_offset_deg>,<speed_deg_per_sec>,<direction>`

Example:
`CMD,ROT_ABS,120.00,-15.00,5.0,CW`

Notes:
- direction must be `CW` or `CCW`

---

### 2. Constant Rotate
Format:
`CMD,ROT_CONST,<speed_deg_per_sec>,<direction>`

Example:
`CMD,ROT_CONST,2.5,CCW`

---

### 3. Rotate Relative
Format:
`CMD,ROT_REL,<delta_angle_deg>,<speed_deg_per_sec>`

Example:
`CMD,ROT_REL,-45.00,3.0`

---

### 4. Rotate Mechanical Zero
Format:
`CMD,ROT_HOME`

Example:
`CMD,ROT_HOME`

---

### 5. Rotate Virtual Zero
Format:
`CMD,ROT_VZERO,<virt_zero_offset_deg>`

Example:
`CMD,ROT_VZERO,-12.50`

---

### 6. Stop
Format:
`CMD,STOP`

Example:
`CMD,STOP`

---

### 7. Telemetry Control
Format:
`CMD,TLM,<rate>`

Examples:
- `CMD,TLM,-1`
- `CMD,TLM,0`
- `CMD,TLM,10`

Meaning:
- `-1` immediate telemetry
- `0` stop cyclic telemetry
- `1..100` cyclic telemetry rate in Hz

---

## ACK Messages

ACK confirms that a command was received and decoded successfully.

General format:
`ACK,<command_type>,<echoed_parameters...>`

Examples:
- `ACK,ROT_ABS,120.00,-15.00,5.0,CW`
- `ACK,ROT_CONST,2.5,CCW`
- `ACK,ROT_REL,-45.00,3.0`
- `ACK,ROT_HOME`
- `ACK,ROT_VZERO,-12.50`
- `ACK,STOP`
- `ACK,TLM,10`

---

## ERR Messages

ERR is returned when:
- command is unknown
- field count is wrong
- parameter is out of range
- parsing fails
- homing fails

General format:
`ERR,<error_code>,<details>`

Recommended error codes:
- `UNKNOWN_COMMAND`
- `BAD_FIELD_COUNT`
- `BAD_FORMAT`
- `PARAM_OUT_OF_RANGE`
- `ZERO_NOT_FOUND`

Examples:
- `ERR,UNKNOWN_COMMAND,CMD_XYZ`
- `ERR,BAD_FIELD_COUNT,ROT_ABS`
- `ERR,PARAM_OUT_OF_RANGE,SPEED`
- `ERR,ZERO_NOT_FOUND,ROT_HOME`

---

## Telemetry Messages

Telemetry format:
`TLM,<mechanical_angle>,<virtual_angle>,<running>,<speed>,<direction>,<steps>`

Field definitions:
1. mechanical angle in degrees
2. virtual angle in degrees
3. running status: `0` or `1`
4. current speed in deg/sec
5. direction: `CW` or `CCW` (when not running, repeats the last motion direction, default `CW`)
6. current steps count

Example:
`TLM,123.45,110.95,1,5.00,CW,9876`

---

## Validation Rules

### Rotate Absolute
- angle: 0 to 360
- virtual zero offset: -180 to +180
- speed: 0.1 to 20
- direction: `CW`, `CCW`

### Constant Rotate
- speed: 0.1 to 20
- direction: `CW`, `CCW`

### Rotate Relative
- delta angle: -360 to +360
- speed: 0.1 to 20

### Telemetry
- rate:
  - `-1`
  - `0`
  - `1..100`

---

## Protocol Design Rules

- embedded side must parse non-blockingly
- malformed input must never crash the firmware
- ACK only means "received and decoded"
- completion reporting can be added later if needed
- protocol changes must be reflected here first before code changes