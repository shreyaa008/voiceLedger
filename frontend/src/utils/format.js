// Small helpers to show money and dates the way shopkeepers expect.

// 12500 -> "₹12,500"   (Indian digit grouping: ₹1,25,000)
export function formatINR(n) {
  return "₹" + Math.abs(Math.round(Number(n) || 0)).toLocaleString("en-IN");
}

// "2026-09-21" -> "21 Sep 2026"
export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(String(iso).slice(0, 10) + "T00:00:00");
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

// "2026-09-21" -> "today" / "yesterday" / "5 days ago" / "3 Jun 2026"
export function timeAgo(iso) {
  if (!iso) return "no entries yet";
  const then = new Date(String(iso).slice(0, 10) + "T00:00:00");
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((today - then) / 86400000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return formatDate(iso);
}