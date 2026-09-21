import { formatDate, formatINR } from "../utils/format";

// A customer's entries, newest first, each with the running balance after it.
// Shows what happened, in order — like a page of a paper khata.
export default function LedgerList({ transactions }) {
  if (!transactions || transactions.length === 0) {
    return <div className="empty-state">No entries for this customer yet.</div>;
  }

  // Work oldest -> newest to compute the running balance, then flip for display.
  const oldestFirst = [...transactions].sort(
    (a, b) =>
      String(a.date).localeCompare(String(b.date)) ||
      String(a.created_at || "").localeCompare(String(b.created_at || ""))
  );

  let running = 0;
  const rows = oldestFirst.map((t) => {
    const amount = Number(t.amount) || 0;
    running += t.type === "credit" ? amount : -amount;
    return { ...t, amount, balanceAfter: running };
  });
  rows.reverse();

  return (
    <ul className="ledger-entries">
      {rows.map((t) => (
        <li className="ledger-entry" key={t.id}>
          <div className="ledger-entry-main">
            <div className="ledger-entry-top">
              <span className={`badge badge-${t.type}`}>
                {t.type === "credit" ? "Udhaar given" : "Payment received"}
              </span>
              <span className="ledger-entry-date">{formatDate(t.date)}</span>
            </div>
            {t.raw_text && <div className="ledger-entry-quote">“{t.raw_text}”</div>}
          </div>
          <div className="ledger-entry-amounts">
            <div className={`ledger-entry-amount ${t.type === "credit" ? "amt-owe" : "amt-paid"}`}>
              {t.type === "credit" ? "+" : "−"}
              {formatINR(t.amount)}
            </div>
            <div className="ledger-entry-balance">
              Balance {t.balanceAfter < 0 ? "−" : ""}
              {formatINR(t.balanceAfter)}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}