interface ValueCardProps {
  label: string;
  value: string;
  unit?: string;
  emphasis?: "primary" | "secondary";
}

export function ValueCard({ label, value, unit, emphasis = "secondary" }: ValueCardProps) {
  return (
    <div className={`value-card value-card--${emphasis}`}>
      <span className="value-card__label">{label}</span>
      <div className="value-card__value-row">
        <span className="value-card__value">{value}</span>
        {unit ? <span className="value-card__unit">{unit}</span> : null}
      </div>
    </div>
  );
}
