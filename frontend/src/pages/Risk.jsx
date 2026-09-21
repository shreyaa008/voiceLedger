import { useState } from "react";
import useDashboard from "../hooks/useDashboard";
import RiskDashboard from "../components/RiskDashboard.jsx";
import ReminderGenerator from "../components/ReminderGenerator.jsx";
import Spinner from "../components/Spinner.jsx";
import "../styles/ledger-risk.css";

export default function Risk() {
  const { loading, error, data, reload } = useDashboard();
  const [reminderFor, setReminderFor] = useState(null);

  return (
    <div className="page">
      <div className="page-header">
        <h2>Risk Dashboard</h2>
        <p className="page-subtitle">Green, yellow, or red — at a glance.</p>
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

      {data && <RiskDashboard customers={data.customers} onRemind={setReminderFor} />}

      {reminderFor && <ReminderGenerator customer={reminderFor} onClose={() => setReminderFor(null)} />}
    </div>
  );
}