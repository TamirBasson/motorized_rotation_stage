import { AppHeader } from "./components/AppHeader";
import { CommandPanel } from "./components/CommandPanel";
import { StatusBanner } from "./components/StatusBanner";
import { SystemConfigurationPanel } from "./components/SystemConfigurationPanel";
import { TelemetryPanel } from "./components/TelemetryPanel";
import { useStageDashboard } from "./hooks/useStageDashboard";

export default function App() {
  const {
    telemetry,
    configuration,
    commands,
    activeCommand,
    busy,
    notification,
    commandAvailability,
    executeCommand,
    updateCommand,
    updateConfiguration,
  } = useStageDashboard();

  return (
    <div className="app-shell">
      <AppHeader telemetry={telemetry} busy={busy} />

      <main className="dashboard-grid">
        <div className="dashboard-grid__main">
          <StatusBanner notification={notification} busy={busy} />
          <TelemetryPanel telemetry={telemetry} />
          <SystemConfigurationPanel
            configuration={configuration}
            busy={busy}
            onConfigurationChange={updateConfiguration}
          />
        </div>

        <aside className="dashboard-grid__side">
          <CommandPanel
            commands={commands}
            activeCommand={activeCommand}
            availability={commandAvailability}
            onCommandChange={updateCommand}
            onExecute={executeCommand}
          />
        </aside>
      </main>
    </div>
  );
}
