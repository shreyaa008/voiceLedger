"""
Balance + risk maths used by the Ledger and Risk screens.

Everything here is a plain function: give it a customer's transactions,
get back numbers. No database calls, so it is easy to test.

Rules (same thresholds as the check_risk voice tool):
  1. How much they owe:      > Rs 5,000  -> +30      > Rs 10,000 -> +50
  2. Age of oldest unpaid:   > 30 days   -> +30      > 60 days   -> +50
  3. Repayment habit:        paid back < 30% of entries (2+ entries) -> +20
Score is capped at 100.  70+ = RED, 40-69 = YELLOW, below 40 = GREEN.

One deliberate difference: customers who owe nothing are always GREEN
(you can't be "overdue" on a debt you have already cleared).
"""
from __future__ import annotations

from datetime import date, datetime


def inr(amount: float) -> str:
    """12345 -> '₹12,345' with Indian digit grouping (12,34,567)."""
    n = int(round(amount))
    digits = str(abs(n))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return ("-" if n < 0 else "") + "₹" + digits


def _to_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _oldest_unpaid_days(transactions: list[dict], balance: float, today: date) -> int:
    """
    Payments are assumed to clear the OLDEST udhaar first (like a real khata).
    Returns how many days old the first still-unpaid udhaar is
    (counted from its due date if it has one, otherwise from the day it was given).
    """
    if balance <= 0:
        return 0

    credits = []
    for t in transactions:
        if t.get("type") == "credit":
            given_on = _to_date(t.get("date"))
            counted_from = _to_date(t.get("due_date")) or given_on
            if given_on and counted_from:
                credits.append((given_on, float(t.get("amount") or 0), counted_from))
    credits.sort(key=lambda c: c[0])

    paid = sum(float(t.get("amount") or 0) for t in transactions if t.get("type") == "payment")
    for _given_on, amount, counted_from in credits:
        if paid >= amount:
            paid -= amount
            continue
        return max(0, (today - counted_from).days)
    return 0


def summarize(transactions: list[dict], today: date | None = None) -> dict:
    """Turn one customer's transactions into balance + risk info."""
    today = today or date.today()

    credit_total = sum(float(t.get("amount") or 0) for t in transactions if t.get("type") == "credit")
    payment_total = sum(float(t.get("amount") or 0) for t in transactions if t.get("type") == "payment")
    balance = credit_total - payment_total  # > 0 : customer owes you

    dates = [d for d in (_to_date(t.get("date")) for t in transactions) if d]
    last_activity = max(dates).isoformat() if dates else None

    days_overdue = _oldest_unpaid_days(transactions, balance, today)

    score = 0
    reasons: list[str] = []

    if balance > 0:
        if balance > 10_000:
            score += 50
            reasons.append(f"Owes {inr(balance)} (more than ₹10,000)")
        elif balance > 5_000:
            score += 30
            reasons.append(f"Owes {inr(balance)} (more than ₹5,000)")

        if days_overdue > 60:
            score += 50
            reasons.append(f"Oldest unpaid udhaar is {days_overdue} days old (over 60 days)")
        elif days_overdue > 30:
            score += 30
            reasons.append(f"Oldest unpaid udhaar is {days_overdue} days old (over 30 days)")

        total = len(transactions)
        payments = sum(1 for t in transactions if t.get("type") == "payment")
        if total >= 2 and payments / total < 0.3:
            score += 20
            reasons.append(f"Paid back only {payments} of {total} entries")

    score = min(score, 100)
    level = "RED" if score >= 70 else "YELLOW" if score >= 40 else "GREEN"

    if not reasons:
        reasons.append("Nothing pending" if balance <= 0 else "Small balance, no long delay so far")

    return {
        "credit_total": round(credit_total, 2),
        "payment_total": round(payment_total, 2),
        "balance": round(balance, 2),
        "entry_count": len(transactions),
        "last_activity": last_activity,
        "days_overdue": days_overdue,
        "score": score,
        "risk_level": level,
        "reasons": reasons,
    }


def reminder_text(name: str, amount: float, days: int, tone: str, language: str) -> str:
    """Same wording used by the Ledger page's reminder composer and the
    ASK generate_reminder tool — one implementation, so the message a
    shopkeeper gets by asking is identical to the one they'd get by
    tapping "Remind" in the app."""
    amt = inr(amount)
    if language == "hi":
        if tone == "firm":
            return (
                f"Namaste {name} ji, aapka {amt} ka udhaar {days} din se baaki hai. "
                "Kripya jaldi se jaldi bhugtan karein taaki aage bhi udhaar diya ja sake."
            )
        if tone == "standard":
            return f"Namaste {name} ji, aapka kul baaki balance {amt} hai. Kripya samay par chukta karein."
        return (
            f"Namaste {name} ji, aasha hai aap kushal hain. Ek chhota sa reminder — "
            f"aapka {amt} baaki hai. Suvidha anusaar bhej dijiye. Dhanyavaad!"
        )

    if tone == "firm":
        return (
            f"Dear {name}, your balance of {amt} has been pending for {days} days. "
            "Please clear it as soon as possible so we can continue giving credit."
        )
    if tone == "standard":
        return f"Dear {name}, this is a reminder that your outstanding balance is {amt}. Kindly arrange the payment."
    return f"Hello {name}, hope you're doing well! A gentle reminder about your pending balance of {amt}. Thank you!"