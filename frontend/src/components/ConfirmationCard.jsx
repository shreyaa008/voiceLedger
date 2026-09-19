export default function ConfirmationCard({ text, onConfirm, onCancel }) {
  if (!text) return null;

  return (
    <div style={{ border: "1px solid #ccc", padding: "12px", marginTop: "12px" }}>
      <p>Did you say: <strong>{text}</strong>?</p>
      <button onClick={onConfirm}>Confirm</button>
      <button onClick={onCancel}>Cancel</button>
    </div>
  );
}