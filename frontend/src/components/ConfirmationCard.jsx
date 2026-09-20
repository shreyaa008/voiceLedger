export default function ConfirmationCard({ text, onConfirm, onCancel }) {
  if (!text) return null;

  const { name, amount, type } = parseTransaction(text);

  return (
    <div className="confirmation-card">
      <h3>Let's make sure</h3>

      <div className="confirmation-row">
        <span className="confirmation-label">Customer</span>
        <span className="confirmation-value">{name}</span>
      </div>
      <div className="confirmation-row">
        <span className="confirmation-label">Amount</span>
        <span className="confirmation-amount">₹{amount}</span>
      </div>
      <div className="confirmation-row">
        <span className="confirmation-label">Type</span>
        <span className="badge">{type}</span>
      </div>

      <p className="confirmation-quote">"{text}"</p>

      <div className="confirmation-actions">
        <button className="btn btn-primary" onClick={onConfirm}>Confirm Transaction</button>
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function parseTransaction(text) {
  const amountMatch = text.match(/\d+/);
  const nameMatch = text.match(/[A-Z][a-z]+/);
  const isCredit = /udhaar|credit/i.test(text);

  return {
    name: nameMatch ? nameMatch[0] : "Unknown",
    amount: amountMatch ? amountMatch[0] : "0",
    type: isCredit ? "Udhaar (Credit)" : "Sale",
  };
}