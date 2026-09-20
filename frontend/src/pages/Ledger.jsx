export default function Ledger() {
  return (
    <div className="page">
      <div className="page-header">
        <h2>Customer Ledger</h2>
        <p className="page-subtitle">See what each customer owes.</p>
      </div>
      <div className="empty-state">No transactions yet — record one to get started.</div>
    </div>
  );
}