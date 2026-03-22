import { Panel } from "./Panel";
import type { SystemConfiguration } from "../types";

interface SystemConfigurationPanelProps {
  configuration: SystemConfiguration;
  busy: boolean;
  onConfigurationChange: <K extends keyof SystemConfiguration>(key: K, value: SystemConfiguration[K]) => void;
}

export function SystemConfigurationPanel({
  configuration,
  busy,
  onConfigurationChange,
}: SystemConfigurationPanelProps) {
  return (
    <Panel
      title="System Configuration Panel"
      subtitle="Visible system constants reduce setup error during remote lab operation."
    >
      <div className="configuration-grid">
        <ConfigurationField
          label="Steps per Revolution"
          hint="Motor native resolution"
          value={configuration.stepsPerRevolution}
          step={1}
          disabled={busy}
          onChange={(value) => onConfigurationChange("stepsPerRevolution", value)}
        />
        <ConfigurationField
          label="Gear Ratio"
          hint="Mechanical transmission ratio"
          value={configuration.gearRatio}
          step={0.1}
          disabled={busy}
          onChange={(value) => onConfigurationChange("gearRatio", value)}
        />
        <ConfigurationField
          label="Virtual Zero Offset"
          hint="Software reference offset"
          value={configuration.virtualZeroOffsetDeg}
          step={0.1}
          disabled={busy}
          onChange={(value) => onConfigurationChange("virtualZeroOffsetDeg", value)}
        />
      </div>

      <div className="configuration-note">
        {busy
          ? "Configuration is locked while a command is executing."
          : "Configuration edits are enabled. In production, these values should be committed through the shared communication layer."}
      </div>
    </Panel>
  );
}

interface ConfigurationFieldProps {
  label: string;
  hint: string;
  value: number;
  step: number;
  disabled: boolean;
  onChange: (value: number) => void;
}

function ConfigurationField({ label, hint, value, step, disabled, onChange }: ConfigurationFieldProps) {
  return (
    <label className="config-card">
      <span className="config-card__label">{label}</span>
      <span className="config-card__hint">{hint}</span>
      <input
        className="number-input number-input--large"
        type="number"
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
