import { useState } from "react";
import { formatDate, formatINR } from "../utils/format";

// A customer's entries, newest first, each with the running balance after it.
// Shows what happened, in order — like a page of a paper khata.
//
// onEdit(transaction, { amount, type }) and onDelete(transaction) are
// optional — pass them to let the shopkeeper fix a misheard entry.
export default function LedgerList({ transactions, onEdit, onDelete }) {
  const [editingId, setEditingId] = useState(null);

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
      {rows.map((t) =>
        editingId === t.id ? (
          <EditRow
            key={t.id}
            transaction={t}
            onCancel={() => setEditingId(null)}
            onSave={(updates) => {
              setEditingId(null);
              onEdit?.(t, updates);
            }}
          />
        ) : (
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
              {(onEdit || onDelete) && (
                <div className="ledger-entry-actions">
                  {onEdit && (
                    <button className="ledger-entry-action-btn" onClick={() => setEditingId(t.id)}>
                      Edit
                    </button>
                  )}
                  {onDelete && (
                    <button
                      className="ledger-entry-action-btn danger"
                      onClick={() => onDelete(t)}
                    >
                      Delete
                    </button>
                  )}
                </div>
              )}
            </div>
          </li>
        )
      )}
    </ul>
  );
}

function EditRow({ transaction, onSave, onCancel }) {
  const [amount, setAmount] = useState(String(transaction.amount));
  const [type, setType] = useState(transaction.type);
  const parsedAmount = parseFloat(amount);
  const valid = !Number.isNaN(parsedAmount) && parsedAmount > 0;

  return (
    <li className="ledger-entry ledger-entry-editing">
      <div className="ledger-edit-form">
        <div className="ledger-edit-type-toggle">
          <button
            className={type === "credit" ? "active" : ""}
            onClick={() => setType("credit")}
            type="button"
          >
            Udhaar
          </button>
          <button
            className={type === "payment" ? "active" : ""}
            onClick={() => setType("payment")}
            type="button"
          >
            Payment
          </button>
        </div>
        <input
          className="ledger-edit-amount-input"
          type="number"
          min="0.01"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          autoFocus
        />
        <div className="ledger-edit-actions">
          <button className="ledger-entry-action-btn" onClick={onCancel} type="button">
            Cancel
          </button>
          <button
            className="ledger-entry-action-btn primary"
            disabled={!valid}
            onClick={() => onSave({ amount: parsedAmount, type })}
            type="button"
          >
            Save
          </button>
        </div>
      </div>
    </li>
  );
}