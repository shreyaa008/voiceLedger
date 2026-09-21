// Green / Yellow / Red pill, in plain words.
export const RISK_META = {
  RED: { label: "High risk", cls: "risk-red" },
  YELLOW: { label: "Watch", cls: "risk-yellow" },
  GREEN: { label: "Safe", cls: "risk-green" },
};

export default function RiskBadge({ level }) {
  const meta = RISK_META[level] || RISK_META.GREEN;
  return (
    <span className={`risk-badge ${meta.cls}`}>
      <span className="risk-dot" />
      {meta.label}
    </span>
  );
}