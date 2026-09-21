import { useEffect, useState } from "react";
import { getCustomerLedger } from "../services/api";
import { formatINR } from "../utils/format";
import LedgerList from "./LedgerList.jsx";
import RiskBadge from "./RiskBadge.jsx";
import Spinner from "./Spinner.jsx";

// Slide-up sheet with one customer's full history.
export default function CustomerLedgerSheet({ customer, onClose, onRemind }) {
  const [transactions, setTransactions] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setTransactions(null);
    setError(null);
    getCustomerLedger(customer.id)
      .then((res) => !cancelled && setTransactions(res.transactions))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [customer.id]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const owes = customer.balance > 0;
  const advance = customer.balance < 0;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-label={`${customer.name} ledger`} onClick={(e) => e.stopPropagation()}>
        <div className="sheet-handle" />
        <div className="modal-header">
          <div>
            <h3>{customer.name}</h3>
            {owes && (
              <div className="sheet-risk">
                <RiskBadge level={customer.risk_level} />
              </div>
            )}
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="sheet-balance">
          <div className="sheet-balance-label">
            {owes ? "You'll get" : advance ? "You'll give (advance)" : "All settled"}
          </div>
          <div className={`sheet-balance-amount ${owes ? "amt-owe" : advance ? "amt-give" : "amt-paid"}`}>
            {formatINR(customer.balance)}
          </div>
        </div>

        {owes && (
          <button className="btn btn-primary sheet-remind" onClick={() => onRemind(customer)}>
            Send reminder
          </button>
        )}

        <div className="sheet-title">Entries</div>
        <div className="sheet-scroll">
          {error && <p className="inline-error">{error}</p>}
          {!error && transactions === null && (
            <div className="center-spinner">
              <Spinner />
            </div>
          )}
          {transactions && <LedgerList transactions={transactions} />}
        </div>
      </div>
    </div>
  );
}