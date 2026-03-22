import { Panel } from "./Panel";
import type { CommandKind, CommandModel, Direction } from "../types";

interface CommandPanelProps {
  commands: CommandModel;
  activeCommand: CommandKind | null;
  availability: Record<CommandKind, boolean>;
  onCommandChange: <K extends keyof CommandModel>(key: K, value: CommandModel[K]) => void;
  onExecute: (kind: CommandKind) => void;
}

export function CommandPanel({
  commands,
  activeCommand,
  availability,
  onCommandChange,
  onExecute,
}: CommandPanelProps) {
  return (
    <Panel title="Command Panel" subtitle="Separated command zones reduce operator ambiguity during critical motion control.">
      <div className="command-group">
        <div className="command-group__header">
          <h3>Absolute Move</h3>
          <span className="command-group__caption">Target angle, speed, and commanded direction</span>
        </div>

        <RangeField
          label="Angle"
          min={0}
          max={360}
          step={0.1}
          value={commands.absoluteAngleDeg}
          unit="deg"
          onChange={(value) => onCommandChange("absoluteAngleDeg", value)}
        />
        <RangeField
          label="Speed"
          min={0.1}
          max={20}
          step={0.1}
          value={commands.absoluteSpeedDegPerSec}
          unit="deg/s"
          onChange={(value) => onCommandChange("absoluteSpeedDegPerSec", value)}
        />

        <div className="field">
          <label className="field__label">Direction</label>
          <div className="segmented">
            {(["CW", "CCW", "NULL"] as Direction[]).map((option) => (
              <button
                key={option}
                type="button"
                className={`segmented__button ${commands.absoluteDirection === option ? "segmented__button--active" : ""}`}
                onClick={() => onCommandChange("absoluteDirection", option)}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        <CommandButton
          label="Rotate Absolute"
          active={activeCommand === "rotateAbsolute"}
          disabled={!availability.rotateAbsolute}
          onClick={() => onExecute("rotateAbsolute")}
        />
      </div>

      <div className="command-group">
        <div className="command-group__header">
          <h3>Relative Move</h3>
          <span className="command-group__caption">Incremental correction for alignment and quick recovery</span>
        </div>

        <RangeField
          label="Relative Angle"
          min={-360}
          max={360}
          step={0.1}
          value={commands.relativeAngleDeg}
          unit="deg"
          onChange={(value) => onCommandChange("relativeAngleDeg", value)}
        />
        <RangeField
          label="Relative Speed"
          min={0.1}
          max={20}
          step={0.1}
          value={commands.relativeSpeedDegPerSec}
          unit="deg/s"
          onChange={(value) => onCommandChange("relativeSpeedDegPerSec", value)}
        />

        <CommandButton
          label="Rotate Relative"
          active={activeCommand === "rotateRelative"}
          disabled={!availability.rotateRelative}
          onClick={() => onExecute("rotateRelative")}
        />
      </div>

      <div className="command-grid command-grid--compact">
        <CommandButton
          label="Mechanical Zero"
          active={activeCommand === "rotateMechanicalZero"}
          disabled={!availability.rotateMechanicalZero}
          onClick={() => onExecute("rotateMechanicalZero")}
        />
        <CommandButton
          label="Virtual Zero"
          active={activeCommand === "rotateVirtualZero"}
          disabled={!availability.rotateVirtualZero}
          onClick={() => onExecute("rotateVirtualZero")}
        />
        <CommandButton
          label="Stop"
          tone="danger"
          active={activeCommand === "stop"}
          disabled={!availability.stop}
          onClick={() => onExecute("stop")}
        />
      </div>
    </Panel>
  );
}

interface RangeFieldProps {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  unit: string;
  onChange: (value: number) => void;
}

function RangeField({ label, min, max, step, value, unit, onChange }: RangeFieldProps) {
  return (
    <div className="field">
      <div className="field__header">
        <label className="field__label">{label}</label>
        <span className="field__value">
          {value.toFixed(2)} {unit}
        </span>
      </div>
      <div className="field__controls">
        <input
          className="slider"
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
        />
        <input
          className="number-input"
          type="number"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      </div>
    </div>
  );
}

interface CommandButtonProps {
  label: string;
  active?: boolean;
  disabled?: boolean;
  tone?: "primary" | "danger";
  onClick: () => void;
}

function CommandButton({
  label,
  active = false,
  disabled = false,
  tone = "primary",
  onClick,
}: CommandButtonProps) {
  return (
    <button
      type="button"
      className={`command-button command-button--${tone} ${active ? "command-button--active" : ""}`}
      disabled={disabled}
      onClick={onClick}
    >
      {active ? `${label}...` : label}
    </button>
  );
}
