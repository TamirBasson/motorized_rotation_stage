import { useEffect, useMemo, useRef, useState } from "react";

import type {
  CommandKind,
  CommandModel,
  Direction,
  NotificationState,
  SystemConfiguration,
  TelemetryState,
} from "../types";

const EXECUTION_DELAY_MS = 900;
const TELEMETRY_TICK_MS = 250;

export function useStageDashboard() {
  const [telemetry, setTelemetry] = useState<TelemetryState>({
    mechanicalAngleDeg: 123.45,
    virtualAngleDeg: 110.95,
    running: false,
    speedDegPerSec: 0,
    direction: "NONE",
    steps: 9876,
    connected: true,
  });

  const [configuration, setConfiguration] = useState<SystemConfiguration>({
    stepsPerRevolution: 200,
    gearRatio: 36,
    virtualZeroOffsetDeg: -12.5,
  });

  const [commands, setCommands] = useState<CommandModel>({
    absoluteAngleDeg: 120,
    absoluteSpeedDegPerSec: 5,
    absoluteDirection: "CW",
    relativeAngleDeg: -45,
    relativeSpeedDegPerSec: 3,
  });

  const [activeCommand, setActiveCommand] = useState<CommandKind | null>(null);
  const executionVersion = useRef(0);
  const [notification, setNotification] = useState<NotificationState>({
    level: "info",
    title: "System Ready",
    message: "Preview mode is active. Commands are simulated without hardware.",
  });

  useEffect(() => {
    const timer = window.setInterval(() => {
      setTelemetry((current) => {
        if (!current.running) {
          return current;
        }

        const directionSign = current.direction === "CCW" ? -1 : 1;
        const nextMechanical = normalizeAngle(current.mechanicalAngleDeg + directionSign * 0.35);
        const nextVirtual = normalizeAngle(current.virtualAngleDeg + directionSign * 0.35);

        return {
          ...current,
          mechanicalAngleDeg: nextMechanical,
          virtualAngleDeg: nextVirtual,
          steps: current.steps + Math.max(1, Math.round(current.speedDegPerSec * 3)),
        };
      });
    }, TELEMETRY_TICK_MS);

    return () => window.clearInterval(timer);
  }, []);

  const busy = activeCommand !== null;

  const commandAvailability = useMemo(
    () => ({
      rotateAbsolute: !busy,
      rotateRelative: !busy,
      rotateMechanicalZero: !busy,
      rotateVirtualZero: !busy,
      stop: telemetry.running || busy,
    }),
    [busy, telemetry.running],
  );

  async function executeCommand(kind: CommandKind) {
    if (busy && kind !== "stop") {
      setNotification({
        level: "warning",
        title: "Command Locked",
        message: "Another command is already executing. Wait for completion or use Stop.",
      });
      return;
    }

    const requestVersion = ++executionVersion.current;
    setActiveCommand(kind);
    setNotification({
      level: "info",
      title: "Command In Progress",
      message: describeCommand(kind),
    });

    await delay(kind === "stop" ? 250 : EXECUTION_DELAY_MS);

    if (requestVersion !== executionVersion.current) {
      return;
    }

    setTelemetry((current) => applyCommand(kind, current, commands, configuration));
    setActiveCommand(null);
    setNotification({
      level: "success",
      title: "Command Accepted",
      message: `${describeCommand(kind)} completed in preview mode.`,
    });
  }

  function updateConfiguration<K extends keyof SystemConfiguration>(key: K, value: SystemConfiguration[K]) {
    setConfiguration((current) => {
      const next = { ...current, [key]: value };
      setTelemetry((telemetryCurrent) => ({
        ...telemetryCurrent,
        virtualAngleDeg: normalizeAngle(telemetryCurrent.mechanicalAngleDeg + next.virtualZeroOffsetDeg),
      }));
      return next;
    });
  }

  function updateCommand<K extends keyof CommandModel>(key: K, value: CommandModel[K]) {
    setCommands((current) => ({ ...current, [key]: value }));
  }

  return {
    telemetry,
    configuration,
    commands,
    activeCommand,
    busy,
    notification,
    commandAvailability,
    executeCommand,
    updateConfiguration,
    updateCommand,
  };
}

function applyCommand(
  kind: CommandKind,
  telemetry: TelemetryState,
  commands: CommandModel,
  configuration: SystemConfiguration,
): TelemetryState {
  switch (kind) {
    case "rotateAbsolute":
      return {
        ...telemetry,
        mechanicalAngleDeg: normalizeAngle(commands.absoluteAngleDeg),
        virtualAngleDeg: normalizeAngle(commands.absoluteAngleDeg + configuration.virtualZeroOffsetDeg),
        running: true,
        speedDegPerSec: commands.absoluteSpeedDegPerSec,
        direction: commands.absoluteDirection === "NULL" ? "NONE" : commands.absoluteDirection,
        steps: telemetry.steps + 240,
      };
    case "rotateRelative": {
      const direction: Direction = commands.relativeAngleDeg >= 0 ? "CW" : "CCW";
      const nextMechanical = normalizeAngle(telemetry.mechanicalAngleDeg + commands.relativeAngleDeg);
      return {
        ...telemetry,
        mechanicalAngleDeg: nextMechanical,
        virtualAngleDeg: normalizeAngle(nextMechanical + configuration.virtualZeroOffsetDeg),
        running: true,
        speedDegPerSec: commands.relativeSpeedDegPerSec,
        direction,
        steps: telemetry.steps + Math.round(Math.abs(commands.relativeAngleDeg) * 14),
      };
    }
    case "rotateMechanicalZero":
      return {
        ...telemetry,
        mechanicalAngleDeg: 0,
        virtualAngleDeg: normalizeAngle(configuration.virtualZeroOffsetDeg),
        running: false,
        speedDegPerSec: 0,
        direction: "NONE",
        steps: 0,
      };
    case "rotateVirtualZero":
      return {
        ...telemetry,
        virtualAngleDeg: 0,
        running: true,
        speedDegPerSec: Math.max(1, telemetry.speedDegPerSec),
        direction: telemetry.direction === "NONE" ? "CW" : telemetry.direction,
        steps: telemetry.steps + 90,
      };
    case "stop":
      return {
        ...telemetry,
        running: false,
        speedDegPerSec: 0,
        direction: "NONE",
      };
    default:
      return telemetry;
  }
}

function delay(ms: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, ms));
}

function normalizeAngle(value: number) {
  const normalized = value % 360;
  return normalized < 0 ? normalized + 360 : normalized;
}

function describeCommand(kind: CommandKind) {
  switch (kind) {
    case "rotateAbsolute":
      return "Rotating to absolute angle";
    case "rotateRelative":
      return "Applying relative move";
    case "rotateMechanicalZero":
      return "Homing to mechanical zero";
    case "rotateVirtualZero":
      return "Moving to virtual zero";
    case "stop":
      return "Stopping motion";
  }
}
