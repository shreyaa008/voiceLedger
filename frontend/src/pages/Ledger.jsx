import { useMemo, useState } from "react";
import useDashboard from "../hooks/useDashboard";
import CustomerLedgerSheet from "../components/CustomerLedgerSheet.jsx";
import ReminderGenerator from "../components/ReminderGenerator.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import Spinner from "../components/Spinner.jsx";
import { formatINR, timeAgo } from "../utils/format";
import "../styles/ledger-risk.css";

export default function Ledger() {
  const { loading, error, data, reload } = useDashboard();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null); // customer whose entries are open
  const [reminderFor, setReminderFor] = useState(null); // customer being reminded

  const customers = data?.customers ?? [];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? customers.filter((c) => c.name.toLowerCase().includes(q)) : customers;
  }, [customers, query]);

  return (
    <div className="page">
      <div className="page-header">
        <h2>Customer Ledger</h2>
        <p className="page-subtitle">See what each customer owes.</p>
      </div>

      {loading && !data && (
        <div className="center-spinner">
          <Spinner />
        </div>
      )}

      {error && (
        <div className="error-card">
          <p>{error}</p>
          <button className="btn btn-secondary" onClick={reload}>
            Try again
          </button>
        </div>
      )}

      {data && (
        <>
          <div className="summary-cards">
            <div className="summary-card summary-get">
              <div className="summary-label">You'll get</div>
              <div className="summary-amount">{formatINR(data.totals.you_will_get)}</div>
            </div>
            <div className="summary-card summary-give">
              <div className="summary-label">You'll give</div>
              <div className="summary-amount">{formatINR(data.totals.you_will_give)}</div>
            </div>
          </div>

          {customers.length === 0 ? (
            <div className="empty-state">No transactions yet — record one to get started.</div>
          ) : (
            <>
              <input
                className="search-input"
                type="search"
                placeholder="Search customer"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search customer"
              />

              {filtered.length === 0 ? (
                <div className="empty-state">No customer named “{query}”.</div>
              ) : (
                <ul className="customer-list">
                  {filtered.map((c) => (
                    <li key={c.id}>
                      <button className="customer-row" onClick={() => setSelected(c)}>
                        <span className="customer-avatar">{c.name.charAt(0).toUpperCase()}</span>
                        <span className="customer-info">
                          <span className="customer-name">{c.name}</span>
                          <span className="customer-meta">
                            {c.entry_count} {c.entry_count === 1 ? "entry" : "entries"} · {timeAgo(c.last_activity)}
                          </span>
                        </span>
                        <span className="customer-balance">
                          <span
                            className={`customer-amount ${
                              c.balance > 0 ? "amt-owe" : c.balance < 0 ? "amt-give" : "amt-paid"
                            }`}
                          >
                            {formatINR(c.balance)}
                          </span>
                          {c.balance > 0 ? (
                            <RiskBadge level={c.risk_level} />
                          ) : (
                            <span className="customer-note">{c.balance < 0 ? "you'll give" : "settled"}</span>
                          )}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </>
      )}

      {selected && (
        <CustomerLedgerSheet
          customer={selected}
          onClose={() => setSelected(null)}
          onRemind={(c) => setReminderFor(c)}
        />
      )}

      {reminderFor && <ReminderGenerator customer={reminderFor} onClose={() => setReminderFor(null)} />}
    </div>
  );
}