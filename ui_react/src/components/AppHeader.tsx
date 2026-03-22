import type { TelemetryState } from "../types";

interface AppHeaderProps {
  telemetry: TelemetryState;
  busy: boolean;
}

export function AppHeader({ telemetry, busy }: AppHeaderProps) {
  return (
    <header className="app-header">
      <div>
        <p className="app-header__eyebrow">Motorized Rotation Stage Controller</p>
        <h1 className="app-header__title">Lab Motion Dashboard</h1>
        <p className="app-header__subtitle">
          Operator-focused control surface with clear command isolation, live telemetry, and configuration visibility.
        </p>
      </div>

      <div className="app-header__status-grid">
        <div className={`header-pill ${telemetry.connected ? "header-pill--online" : "header-pill--offline"}`}>
          {telemetry.connected ? "Controller Online" : "Controller Offline"}
        </div>
        <div className={`header-pill ${telemetry.running ? "header-pill--motion" : "header-pill--idle"}`}>
          {telemetry.running ? "Motor Running" : "Motor Idle"}
        </div>
        <div className={`header-pill ${busy ? "header-pill--motion" : "header-pill--idle"}`}>
          {busy ? "Command Executing" : "No Pending Command"}
        </div>
      </div>
    </header>
  );
}
