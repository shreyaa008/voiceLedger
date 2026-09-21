export default function Toast({ message, actionLabel, onAction }) {
  if (!message) return null;
  return (
    <div className="toast">
      <span>{message}</span>
      {actionLabel && onAction && (
        <button className="toast-action" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}