export type Direction = "CW" | "CCW" | "NONE" | "NULL";

export type CommandKind =
  | "rotateAbsolute"
  | "rotateRelative"
  | "rotateMechanicalZero"
  | "rotateVirtualZero"
  | "stop";

export type NotificationLevel = "info" | "warning" | "error" | "success";

export interface TelemetryState {
  mechanicalAngleDeg: number;
  virtualAngleDeg: number;
  running: boolean;
  speedDegPerSec: number;
  direction: Direction;
  steps: number;
  connected: boolean;
}

export interface SystemConfiguration {
  stepsPerRevolution: number;
  gearRatio: number;
  virtualZeroOffsetDeg: number;
}

export interface CommandModel {
  absoluteAngleDeg: number;
  absoluteSpeedDegPerSec: number;
  absoluteDirection: Direction;
  relativeAngleDeg: number;
  relativeSpeedDegPerSec: number;
}

export interface NotificationState {
  level: NotificationLevel;
  title: string;
  message: string;
}
