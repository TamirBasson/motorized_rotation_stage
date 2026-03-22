import { Panel } from "./Panel";
import { ValueCard } from "./ValueCard";
import type { TelemetryState } from "../types";

interface TelemetryPanelProps {
  telemetry: TelemetryState;
}

export function TelemetryPanel({ telemetry }: TelemetryPanelProps) {
  return (
    <Panel title="Telemetry Panel" subtitle="Live engineering readout for immediate operator awareness.">
      <div className="value-grid">
        <ValueCard label="Mechanical Angle" value={telemetry.mechanicalAngleDeg.toFixed(2)} unit="deg" emphasis="primary" />
        <ValueCard label="Virtual Angle" value={telemetry.virtualAngleDeg.toFixed(2)} unit="deg" emphasis="primary" />
        <ValueCard label="Speed" value={telemetry.speedDegPerSec.toFixed(2)} unit="deg/s" />
        <ValueCard label="Direction" value={telemetry.direction} />
      </div>

      <div className="telemetry-strip">
        <div className="telemetry-strip__item">
          <span className="telemetry-strip__label">Motor State</span>
          <strong className={telemetry.running ? "text-accent" : "text-muted"}>
            {telemetry.running ? "RUNNING" : "IDLE"}
          </strong>
        </div>
        <div className="telemetry-strip__item">
          <span className="telemetry-strip__label">Controller Link</span>
          <strong className={telemetry.connected ? "text-accent" : "text-danger"}>
            {telemetry.connected ? "HEALTHY" : "DISCONNECTED"}
          </strong>
        </div>
        <div className="telemetry-strip__item">
          <span className="telemetry-strip__label">Steps</span>
          <strong>{telemetry.steps.toLocaleString()}</strong>
        </div>
      </div>
    </Panel>
  );
}
