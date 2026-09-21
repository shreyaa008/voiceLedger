import { useState } from "react";
import { formatINR, timeAgo } from "../utils/format";
import RiskBadge, { RISK_META } from "./RiskBadge.jsx";

const ORDER = ["RED", "YELLOW", "GREEN"];

// Who should you chase first? Shows only customers who still owe you money,
// riskiest at the top. Tap a colour tile to filter.
export default function RiskDashboard({ customers, onRemind }) {
  const [filter, setFilter] = useState("ALL");

  const owing = customers
    .filter((c) => c.balance > 0)
    .sort((a, b) => b.score - a.score || b.balance - a.balance);

  const settledCount = customers.length - owing.length;

  const stats = ORDER.map((level) => {
    const group = owing.filter((c) => c.risk_level === level);
    return { level, count: group.length, amount: group.reduce((sum, c) => sum + c.balance, 0) };
  });

  const visible = filter === "ALL" ? owing : owing.filter((c) => c.risk_level === filter);

  if (owing.length === 0) {
    return (
      <div className="empty-state">
        Nobody owes you anything right now. 🎉
        {settledCount > 0 && <div className="empty-sub">{settledCount} customer(s) fully settled.</div>}
      </div>
    );
  }

  return (
    <>
      <div className="risk-tiles">
        {stats.map((s) => (
          <button
            key={s.level}
            className={`risk-tile ${RISK_META[s.level].cls} ${filter === s.level ? "risk-tile-active" : ""}`}
            onClick={() => setFilter(filter === s.level ? "ALL" : s.level)}
            aria-pressed={filter === s.level}
          >
            <span className="risk-tile-count">{s.count}</span>
            <span className="risk-tile-label">{RISK_META[s.level].label}</span>
            <span className="risk-tile-amount">{formatINR(s.amount)}</span>
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <div className="empty-state">No customers in this group.</div>
      ) : (
        <ul className="risk-list">
          {visible.map((c) => (
            <li className="risk-card" key={c.id}>
              <div className="risk-card-top">
                <div>
                  <div className="risk-card-name">{c.name}</div>
                  <div className="risk-card-meta">Last entry {timeAgo(c.last_activity)}</div>
                </div>
                <div className="risk-card-right">
                  <div className="risk-card-amount">{formatINR(c.balance)}</div>
                  <RiskBadge level={c.risk_level} />
                </div>
              </div>

              <div className="risk-bar" aria-label={`Risk score ${c.score} out of 100`}>
                <div className={`risk-bar-fill ${RISK_META[c.risk_level].cls}`} style={{ width: `${Math.max(c.score, 4)}%` }} />
              </div>

              <ul className="risk-reasons">
                {c.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>

              <button className="btn btn-secondary risk-remind" onClick={() => onRemind(c)}>
                Send reminder
              </button>
            </li>
          ))}
        </ul>
      )}

      {settledCount > 0 && <p className="risk-footnote">{settledCount} customer(s) with nothing pending are not shown.</p>}
    </>
  );
}