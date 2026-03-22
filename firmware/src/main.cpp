#include <Arduino.h>
#include <FastAccelStepper.h>

#include <math.h>
#include <stdlib.h>
#include <string.h>

// ================================
// Pin definitions and constants
// ================================

constexpr uint32_t kSerialBaud = 115200UL;

constexpr uint8_t kStepPin = 9;   // FastAccelStepper uses Nano timer-backed step pins.
constexpr uint8_t kDirPin = 5;
constexpr uint8_t kEnablePin = 6;
constexpr uint8_t kHomePin = 7;

constexpr bool kDirPinHighCountsUp = true;      // Positive steps = CW in protocol space.
constexpr bool kEnablePinIsActiveLow = true;
constexpr bool kHomeInputIsActiveLow = true;

constexpr size_t kSerialBufferLength = 96;
constexpr uint8_t kMaxCsvFields = 8;

constexpr float kMinSpeedDegPerSec = 0.1f;
constexpr float kMaxSpeedDegPerSec = 20.0f;
constexpr float kMinAbsoluteAngleDeg = 0.0f;
constexpr float kMaxAbsoluteAngleDeg = 360.0f;
constexpr float kMinRelativeAngleDeg = -360.0f;
constexpr float kMaxRelativeAngleDeg = 360.0f;
constexpr float kMinVirtualZeroOffsetDeg = -180.0f;
constexpr float kMaxVirtualZeroOffsetDeg = 180.0f;

constexpr float kMotorStepsPerRevolution = 3200.0f;  // Effective motor steps, including microstepping.
constexpr float kGearRatio = 3.0f;
constexpr float kStageStepsPerRevolution = kMotorStepsPerRevolution * kGearRatio;

constexpr float kDefaultAccelerationDegPerSec2 = 90.0f;
constexpr float kDefaultSeekSpeedDegPerSec = 5.0f;
constexpr uint32_t kMinAccelerationStepsPerSec2 = 400UL;
constexpr uint16_t kStepperEnableDelayUs = 50U;
constexpr uint16_t kStepperDisableDelayMs = 20U;

// ================================
// Enums and structs
// ================================

enum class ControllerState : uint8_t {
  IDLE,
  MOVING_ABSOLUTE,
  MOVING_RELATIVE,
  CONSTANT_ROTATE,
  HOMING_MECHANICAL_ZERO,
  MOVING_TO_VIRTUAL_ZERO,
  ERROR
};

enum class MotionDirection : uint8_t {
  NONE,
  CW,
  CCW
};

struct Config {
  float virtualZeroOffsetDeg = 0.0f;
};

struct RuntimeState {
  ControllerState state = ControllerState::IDLE;
  MotionDirection direction = MotionDirection::NONE;
  float commandedSpeedDegPerSec = 0.0f;
  int32_t targetPositionSteps = 0;
  int32_t homeSearchStartSteps = 0;
  uint16_t telemetryRateHz = 0;
  unsigned long lastTelemetryMs = 0;
};

// ================================
// Runtime state
// ================================

Config g_config;
RuntimeState g_runtime;

char g_rxBuffer[kSerialBufferLength];
size_t g_rxLength = 0;
bool g_rxOverflow = false;

// ================================
// FastAccelStepper objects
// ================================

FastAccelStepperEngine g_stepperEngine = FastAccelStepperEngine();
FastAccelStepper *g_stepper = nullptr;

// ================================
// Utility helpers
// ================================

float normalizeAngle360(float angleDeg) {
  float wrapped = fmodf(angleDeg, 360.0f);
  if (wrapped < 0.0f) {
    wrapped += 360.0f;
  }
  if (wrapped >= 360.0f) {
    wrapped -= 360.0f;
  }
  return wrapped;
}

float shortestSignedDeltaDeg(float currentDeg, float targetDeg) {
  float delta = normalizeAngle360(targetDeg - currentDeg);
  if (delta > 180.0f) {
    delta -= 360.0f;
  }
  return delta;
}

float clockwiseDeltaDeg(float currentDeg, float targetDeg) {
  return normalizeAngle360(targetDeg - currentDeg);
}

float counterClockwiseDeltaDeg(float currentDeg, float targetDeg) {
  return -normalizeAngle360(currentDeg - targetDeg);
}

int32_t roundToInt32(float value) {
  return static_cast<int32_t>(value >= 0.0f ? value + 0.5f : value - 0.5f);
}

int32_t degreesToSteps(float angleDeg) {
  return roundToInt32((angleDeg * kStageStepsPerRevolution) / 360.0f);
}

float stepsToDegrees(int32_t steps) {
  return (static_cast<float>(steps) * 360.0f) / kStageStepsPerRevolution;
}

float degreesPerSecondToStepHz(float speedDegPerSec) {
  return (speedDegPerSec * kStageStepsPerRevolution) / 360.0f;
}

bool valueInRange(float value, float minValue, float maxValue) {
  return value >= minValue && value <= maxValue;
}

bool homeSensorActive() {
  const bool rawState = digitalRead(kHomePin) == HIGH;
  return kHomeInputIsActiveLow ? !rawState : rawState;
}

const char *directionToText(MotionDirection direction) {
  switch (direction) {
    case MotionDirection::CW:
      return "CW";
    case MotionDirection::CCW:
      return "CCW";
    default:
      return "NONE";
  }
}

float getMechanicalAngleDeg() {
  if (g_stepper == nullptr) {
    return 0.0f;
  }
  return normalizeAngle360(stepsToDegrees(g_stepper->getCurrentPosition()));
}

float getVirtualAngleDeg() {
  return normalizeAngle360(getMechanicalAngleDeg() - g_config.virtualZeroOffsetDeg);
}

bool parseFloatStrict(const char *token, float &value) {
  if ((token == nullptr) || (*token == '\0')) {
    return false;
  }

  char *endPtr = nullptr;
  const double parsedValue = strtod(token, &endPtr);
  if ((endPtr == token) || (*endPtr != '\0') || !isfinite(parsedValue)) {
    return false;
  }

  value = static_cast<float>(parsedValue);
  return true;
}

bool parseIntStrict(const char *token, int32_t &value) {
  if ((token == nullptr) || (*token == '\0')) {
    return false;
  }

  char *endPtr = nullptr;
  const long parsedValue = strtol(token, &endPtr, 10);
  if ((endPtr == token) || (*endPtr != '\0')) {
    return false;
  }

  value = static_cast<int32_t>(parsedValue);
  return true;
}

uint8_t splitCsv(char *line, char *fields[], uint8_t maxFields) {
  uint8_t count = 0;
  char *savePtr = nullptr;
  char *token = strtok_r(line, ",", &savePtr);

  while ((token != nullptr) && (count < maxFields)) {
    fields[count++] = token;
    token = strtok_r(nullptr, ",", &savePtr);
  }

  return count;
}

// ================================
// Serial response helpers
// ================================

void sendErr(const char *code, const char *details) {
  Serial.print(F("ERR,"));
  Serial.print(code);
  Serial.print(F(","));
  Serial.println(details);
}

void sendAckRotAbs(float angleDeg, float offsetDeg, float speedDegPerSec, const char *direction) {
  Serial.print(F("ACK,ROT_ABS,"));
  Serial.print(angleDeg, 2);
  Serial.print(F(","));
  Serial.print(offsetDeg, 2);
  Serial.print(F(","));
  Serial.print(speedDegPerSec, 1);
  Serial.print(F(","));
  Serial.println(direction);
}

void sendAckRotConst(float speedDegPerSec, const char *direction) {
  Serial.print(F("ACK,ROT_CONST,"));
  Serial.print(speedDegPerSec, 1);
  Serial.print(F(","));
  Serial.println(direction);
}

void sendAckRotRel(float deltaAngleDeg, float speedDegPerSec) {
  Serial.print(F("ACK,ROT_REL,"));
  Serial.print(deltaAngleDeg, 2);
  Serial.print(F(","));
  Serial.println(speedDegPerSec, 1);
}

void sendAckSimple(const char *commandName) {
  Serial.print(F("ACK,"));
  Serial.println(commandName);
}

void sendAckRotVZero(float offsetDeg) {
  Serial.print(F("ACK,ROT_VZERO,"));
  Serial.println(offsetDeg, 2);
}

void sendAckTelemetry(int32_t rate) {
  Serial.print(F("ACK,TLM,"));
  Serial.println(rate);
}

void sendTelemetry() {
  const bool isRunning = (g_stepper != nullptr) && g_stepper->isRunning();
  const float reportedSpeed = isRunning ? g_runtime.commandedSpeedDegPerSec : 0.0f;
  const MotionDirection reportedDirection = isRunning ? g_runtime.direction : MotionDirection::NONE;
  const int32_t steps = (g_stepper != nullptr) ? g_stepper->getCurrentPosition() : 0;

  Serial.print(F("TLM,"));
  Serial.print(getMechanicalAngleDeg(), 2);
  Serial.print(F(","));
  Serial.print(getVirtualAngleDeg(), 2);
  Serial.print(F(","));
  Serial.print(isRunning ? 1 : 0);
  Serial.print(F(","));
  Serial.print(reportedSpeed, 2);
  Serial.print(F(","));
  Serial.print(directionToText(reportedDirection));
  Serial.print(F(","));
  Serial.println(steps);
}

// ================================
// Motion helpers
// ================================

void clearMotionState(ControllerState nextState = ControllerState::IDLE) {
  g_runtime.state = nextState;
  g_runtime.direction = MotionDirection::NONE;
  g_runtime.commandedSpeedDegPerSec = 0.0f;
  g_runtime.targetPositionSteps = (g_stepper != nullptr) ? g_stepper->getCurrentPosition() : 0;
  g_runtime.homeSearchStartSteps = g_runtime.targetPositionSteps;
}

void preemptCurrentMotion() {
  if (g_stepper == nullptr) {
    clearMotionState(ControllerState::ERROR);
    return;
  }

  if (g_stepper->isRunning()) {
    g_stepper->forceStop();
  }
  clearMotionState(ControllerState::IDLE);
}

void configureMotionProfile(float speedDegPerSec) {
  if (g_stepper == nullptr) {
    return;
  }

  uint32_t speedHz = static_cast<uint32_t>(degreesPerSecondToStepHz(speedDegPerSec) + 0.5f);
  if (speedHz < 1UL) {
    speedHz = 1UL;
  }

  uint32_t accelHzPerSec = static_cast<uint32_t>(degreesPerSecondToStepHz(kDefaultAccelerationDegPerSec2) + 0.5f);
  if (accelHzPerSec < kMinAccelerationStepsPerSec2) {
    accelHzPerSec = kMinAccelerationStepsPerSec2;
  }

  g_stepper->setSpeedInHz(speedHz);
  g_stepper->setAcceleration(static_cast<int32_t>(accelHzPerSec));
}

bool startMoveByDelta(float deltaAngleDeg, float speedDegPerSec, ControllerState moveState) {
  if (g_stepper == nullptr) {
    clearMotionState(ControllerState::ERROR);
    sendErr("BAD_FORMAT", "STEPPER_INIT");
    return false;
  }

  preemptCurrentMotion();
  const int32_t deltaSteps = degreesToSteps(deltaAngleDeg);
  const int32_t currentSteps = g_stepper->getCurrentPosition();
  const int32_t targetSteps = currentSteps + deltaSteps;
  configureMotionProfile(speedDegPerSec);

  g_runtime.state = moveState;
  g_runtime.direction = (deltaSteps > 0) ? MotionDirection::CW : (deltaSteps < 0) ? MotionDirection::CCW : MotionDirection::NONE;
  g_runtime.commandedSpeedDegPerSec = speedDegPerSec;
  g_runtime.targetPositionSteps = targetSteps;
  g_runtime.homeSearchStartSteps = currentSteps;

  if (deltaSteps == 0) {
    clearMotionState(ControllerState::IDLE);
    return true;
  }

  g_stepper->moveTo(targetSteps);
  return true;
}

bool startAbsoluteMove(float targetVirtualAngleDeg, float offsetDeg, float speedDegPerSec, MotionDirection preferredDirection) {
  g_config.virtualZeroOffsetDeg = offsetDeg;
  preemptCurrentMotion();

  const float currentMechanicalDeg = getMechanicalAngleDeg();
  const float targetMechanicalDeg = normalizeAngle360(targetVirtualAngleDeg + g_config.virtualZeroOffsetDeg);

  float deltaDeg = 0.0f;
  switch (preferredDirection) {
    case MotionDirection::CW:
      deltaDeg = clockwiseDeltaDeg(currentMechanicalDeg, targetMechanicalDeg);
      break;
    case MotionDirection::CCW:
      deltaDeg = counterClockwiseDeltaDeg(currentMechanicalDeg, targetMechanicalDeg);
      break;
    default:
      deltaDeg = shortestSignedDeltaDeg(currentMechanicalDeg, targetMechanicalDeg);
      break;
  }

  return startMoveByDelta(deltaDeg, speedDegPerSec, ControllerState::MOVING_ABSOLUTE);
}

bool startRotateToVirtualZero(float offsetDeg) {
  g_config.virtualZeroOffsetDeg = offsetDeg;
  preemptCurrentMotion();

  const float currentMechanicalDeg = getMechanicalAngleDeg();
  const float targetMechanicalDeg = normalizeAngle360(g_config.virtualZeroOffsetDeg);
  const float deltaDeg = shortestSignedDeltaDeg(currentMechanicalDeg, targetMechanicalDeg);

  return startMoveByDelta(deltaDeg, kDefaultSeekSpeedDegPerSec, ControllerState::MOVING_TO_VIRTUAL_ZERO);
}

bool startConstantRotate(float speedDegPerSec, MotionDirection direction) {
  if (g_stepper == nullptr) {
    clearMotionState(ControllerState::ERROR);
    sendErr("BAD_FORMAT", "STEPPER_INIT");
    return false;
  }

  preemptCurrentMotion();
  configureMotionProfile(speedDegPerSec);

  g_runtime.state = ControllerState::CONSTANT_ROTATE;
  g_runtime.direction = direction;
  g_runtime.commandedSpeedDegPerSec = speedDegPerSec;
  g_runtime.targetPositionSteps = g_stepper->getCurrentPosition();
  g_runtime.homeSearchStartSteps = g_runtime.targetPositionSteps;

  if (direction == MotionDirection::CW) {
    g_stepper->runForward();
  } else {
    g_stepper->runBackward();
  }

  return true;
}

bool startMechanicalHoming(float speedDegPerSec) {
  if (g_stepper == nullptr) {
    clearMotionState(ControllerState::ERROR);
    sendErr("BAD_FORMAT", "STEPPER_INIT");
    return false;
  }

  preemptCurrentMotion();

  if (homeSensorActive()) {
    g_stepper->setCurrentPosition(0);
    clearMotionState(ControllerState::IDLE);
    return true;
  }

  configureMotionProfile(speedDegPerSec);

  g_runtime.state = ControllerState::HOMING_MECHANICAL_ZERO;
  g_runtime.direction = MotionDirection::CCW;
  g_runtime.commandedSpeedDegPerSec = speedDegPerSec;
  g_runtime.homeSearchStartSteps = g_stepper->getCurrentPosition();
  g_runtime.targetPositionSteps = g_runtime.homeSearchStartSteps - degreesToSteps(360.0f);

  g_stepper->runBackward();
  return true;
}

void stopNow() {
  preemptCurrentMotion();
}

// ================================
// Command parsing and execution
// ================================

bool parseDirectionToken(const char *token, bool allowNull, MotionDirection &direction) {
  if (strcmp(token, "CW") == 0) {
    direction = MotionDirection::CW;
    return true;
  }
  if (strcmp(token, "CCW") == 0) {
    direction = MotionDirection::CCW;
    return true;
  }
  if (allowNull && (strcmp(token, "NULL") == 0)) {
    direction = MotionDirection::NONE;
    return true;
  }
  return false;
}

void handleRotateAbsolute(char *fields[], uint8_t fieldCount) {
  if (fieldCount != 6) {
    sendErr("BAD_FIELD_COUNT", "ROT_ABS");
    return;
  }

  float angleDeg = 0.0f;
  float offsetDeg = 0.0f;
  float speedDegPerSec = 0.0f;
  MotionDirection direction = MotionDirection::NONE;

  if (!parseFloatStrict(fields[2], angleDeg) || !parseFloatStrict(fields[3], offsetDeg) ||
      !parseFloatStrict(fields[4], speedDegPerSec) || !parseDirectionToken(fields[5], true, direction)) {
    sendErr("BAD_FORMAT", "ROT_ABS");
    return;
  }

  if (!valueInRange(angleDeg, kMinAbsoluteAngleDeg, kMaxAbsoluteAngleDeg) ||
      !valueInRange(offsetDeg, kMinVirtualZeroOffsetDeg, kMaxVirtualZeroOffsetDeg) ||
      !valueInRange(speedDegPerSec, kMinSpeedDegPerSec, kMaxSpeedDegPerSec)) {
    sendErr("PARAM_OUT_OF_RANGE", "ROT_ABS");
    return;
  }

  if (startAbsoluteMove(angleDeg, offsetDeg, speedDegPerSec, direction)) {
    sendAckRotAbs(angleDeg, offsetDeg, speedDegPerSec, fields[5]);
  }
}

void handleRotateConstant(char *fields[], uint8_t fieldCount) {
  if (fieldCount != 4) {
    sendErr("BAD_FIELD_COUNT", "ROT_CONST");
    return;
  }

  float speedDegPerSec = 0.0f;
  MotionDirection direction = MotionDirection::NONE;

  if (!parseFloatStrict(fields[2], speedDegPerSec) || !parseDirectionToken(fields[3], false, direction)) {
    sendErr("BAD_FORMAT", "ROT_CONST");
    return;
  }

  if (!valueInRange(speedDegPerSec, kMinSpeedDegPerSec, kMaxSpeedDegPerSec)) {
    sendErr("PARAM_OUT_OF_RANGE", "ROT_CONST");
    return;
  }

  if (startConstantRotate(speedDegPerSec, direction)) {
    sendAckRotConst(speedDegPerSec, fields[3]);
  }
}

void handleRotateRelative(char *fields[], uint8_t fieldCount) {
  if (fieldCount != 4) {
    sendErr("BAD_FIELD_COUNT", "ROT_REL");
    return;
  }

  float deltaDeg = 0.0f;
  float speedDegPerSec = 0.0f;

  if (!parseFloatStrict(fields[2], deltaDeg) || !parseFloatStrict(fields[3], speedDegPerSec)) {
    sendErr("BAD_FORMAT", "ROT_REL");
    return;
  }

  if (!valueInRange(deltaDeg, kMinRelativeAngleDeg, kMaxRelativeAngleDeg) ||
      !valueInRange(speedDegPerSec, kMinSpeedDegPerSec, kMaxSpeedDegPerSec)) {
    sendErr("PARAM_OUT_OF_RANGE", "ROT_REL");
    return;
  }

  if (startMoveByDelta(deltaDeg, speedDegPerSec, ControllerState::MOVING_RELATIVE)) {
    sendAckRotRel(deltaDeg, speedDegPerSec);
  }
}

void handleRotateHome(char *fields[], uint8_t fieldCount) {
  if (fieldCount != 2) {
    sendErr("BAD_FIELD_COUNT", "ROT_HOME");
    return;
  }

  if (startMechanicalHoming(kDefaultSeekSpeedDegPerSec)) {
    sendAckSimple("ROT_HOME");
  }
}

void handleRotateVirtualZero(char *fields[], uint8_t fieldCount) {
  if (fieldCount != 3) {
    sendErr("BAD_FIELD_COUNT", "ROT_VZERO");
    return;
  }

  float offsetDeg = 0.0f;
  if (!parseFloatStrict(fields[2], offsetDeg)) {
    sendErr("BAD_FORMAT", "ROT_VZERO");
    return;
  }

  if (!valueInRange(offsetDeg, kMinVirtualZeroOffsetDeg, kMaxVirtualZeroOffsetDeg)) {
    sendErr("PARAM_OUT_OF_RANGE", "ROT_VZERO");
    return;
  }

  if (startRotateToVirtualZero(offsetDeg)) {
    sendAckRotVZero(offsetDeg);
  }
}

void handleStop(char *fields[], uint8_t fieldCount) {
  if (fieldCount != 2) {
    sendErr("BAD_FIELD_COUNT", "STOP");
    return;
  }

  stopNow();
  sendAckSimple("STOP");
}

void handleTelemetryCommand(char *fields[], uint8_t fieldCount) {
  if (fieldCount != 3) {
    sendErr("BAD_FIELD_COUNT", "TLM");
    return;
  }

  int32_t rate = 0;
  if (!parseIntStrict(fields[2], rate)) {
    sendErr("BAD_FORMAT", "TLM");
    return;
  }

  if ((rate != -1) && (rate != 0) && ((rate < 1) || (rate > 100))) {
    sendErr("PARAM_OUT_OF_RANGE", "TLM");
    return;
  }

  if (rate == -1) {
    sendAckTelemetry(rate);
    sendTelemetry();
    return;
  }

  g_runtime.telemetryRateHz = static_cast<uint16_t>(rate);
  g_runtime.lastTelemetryMs = millis();
  sendAckTelemetry(rate);
}

void processCommandLine(const char *line) {
  if ((line == nullptr) || (*line == '\0')) {
    return;
  }

  char workingCopy[kSerialBufferLength];
  strncpy(workingCopy, line, sizeof(workingCopy) - 1);
  workingCopy[sizeof(workingCopy) - 1] = '\0';

  char *fields[kMaxCsvFields] = {nullptr};
  const uint8_t fieldCount = splitCsv(workingCopy, fields, kMaxCsvFields);
  if (fieldCount < 2) {
    sendErr("BAD_FORMAT", "MESSAGE");
    return;
  }

  if (strcmp(fields[0], "CMD") != 0) {
    sendErr("UNKNOWN_COMMAND", fields[0]);
    return;
  }

  if (strcmp(fields[1], "ROT_ABS") == 0) {
    handleRotateAbsolute(fields, fieldCount);
    return;
  }
  if (strcmp(fields[1], "ROT_CONST") == 0) {
    handleRotateConstant(fields, fieldCount);
    return;
  }
  if (strcmp(fields[1], "ROT_REL") == 0) {
    handleRotateRelative(fields, fieldCount);
    return;
  }
  if (strcmp(fields[1], "ROT_HOME") == 0) {
    handleRotateHome(fields, fieldCount);
    return;
  }
  if (strcmp(fields[1], "ROT_VZERO") == 0) {
    handleRotateVirtualZero(fields, fieldCount);
    return;
  }
  if (strcmp(fields[1], "STOP") == 0) {
    handleStop(fields, fieldCount);
    return;
  }
  if (strcmp(fields[1], "TLM") == 0) {
    handleTelemetryCommand(fields, fieldCount);
    return;
  }

  sendErr("UNKNOWN_COMMAND", fields[1]);
}

// ================================
// Non-blocking services
// ================================

void serviceSerialReceive() {
  while (Serial.available() > 0) {
    const char incoming = static_cast<char>(Serial.read());

    if (incoming == '\r') {
      continue;
    }

    if (incoming == '\n') {
      if (g_rxOverflow) {
        sendErr("BAD_FORMAT", "LINE_TOO_LONG");
      } else if (g_rxLength > 0) {
        g_rxBuffer[g_rxLength] = '\0';
        processCommandLine(g_rxBuffer);
      }

      g_rxLength = 0;
      g_rxOverflow = false;
      continue;
    }

    if (g_rxOverflow) {
      continue;
    }

    if (g_rxLength < (kSerialBufferLength - 1)) {
      g_rxBuffer[g_rxLength++] = incoming;
    } else {
      g_rxLength = 0;
      g_rxOverflow = true;
    }
  }
}

void updateMotionState() {
  if (g_stepper == nullptr) {
    g_runtime.state = ControllerState::ERROR;
    return;
  }

  if (g_runtime.state == ControllerState::HOMING_MECHANICAL_ZERO) {
    if (homeSensorActive()) {
      g_stepper->forceStopAndNewPosition(0);
      clearMotionState(ControllerState::IDLE);
      return;
    }

    const int32_t traveledDelta = g_stepper->getCurrentPosition() - g_runtime.homeSearchStartSteps;
    const int32_t traveledSteps = (traveledDelta >= 0) ? traveledDelta : -traveledDelta;
    if (traveledSteps >= degreesToSteps(360.0f)) {
      g_stepper->forceStop();
      clearMotionState(ControllerState::ERROR);
      sendErr("ZERO_NOT_FOUND", "ROT_HOME");
      return;
    }
  }

  switch (g_runtime.state) {
    case ControllerState::MOVING_ABSOLUTE:
    case ControllerState::MOVING_RELATIVE:
    case ControllerState::MOVING_TO_VIRTUAL_ZERO:
      if (!g_stepper->isRunning()) {
        clearMotionState(ControllerState::IDLE);
      }
      break;

    case ControllerState::CONSTANT_ROTATE:
      if (!g_stepper->isRunning()) {
        clearMotionState(ControllerState::IDLE);
      }
      break;

    case ControllerState::IDLE:
    case ControllerState::ERROR:
    case ControllerState::HOMING_MECHANICAL_ZERO:
    default:
      break;
  }
}

void serviceTelemetry() {
  if (g_runtime.telemetryRateHz == 0) {
    return;
  }

  const unsigned long nowMs = millis();
  const unsigned long intervalMs = 1000UL / g_runtime.telemetryRateHz;
  if ((nowMs - g_runtime.lastTelemetryMs) >= intervalMs) {
    g_runtime.lastTelemetryMs = nowMs;
    sendTelemetry();
  }
}

// ================================
// setup()
// ================================

void setup() {
  pinMode(kHomePin, kHomeInputIsActiveLow ? INPUT_PULLUP : INPUT);

  Serial.begin(kSerialBaud);

  g_stepperEngine.init();
  g_stepper = g_stepperEngine.stepperConnectToPin(kStepPin);

  if (g_stepper != nullptr) {
    g_stepper->setDirectionPin(kDirPin, kDirPinHighCountsUp);
    g_stepper->setEnablePin(kEnablePin, kEnablePinIsActiveLow);
    g_stepper->setAutoEnable(true);
    g_stepper->setDelayToEnable(kStepperEnableDelayUs);
    g_stepper->setDelayToDisable(kStepperDisableDelayMs);
    configureMotionProfile(kDefaultSeekSpeedDegPerSec);

    if (homeSensorActive()) {
      g_stepper->setCurrentPosition(0);
    }
  } else {
    g_runtime.state = ControllerState::ERROR;
    sendErr("BAD_FORMAT", "STEPPER_INIT");
  }
}

// ================================
// loop()
// ================================

void loop() {
  serviceSerialReceive();
  updateMotionState();
  serviceTelemetry();
}
