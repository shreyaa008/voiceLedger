"""
Tool: get_business_summary  (READ-ONLY)

Deterministic, database-computed totals for the shopkeeper asking:
  - total_transaction_count, total_credit_amount, total_payment_amount
  - total_receivable  ("mujhe kitne paise lene hain" — customers who owe money)
  - total_payable     ("mujhe kitne paise dene hain" — advance/overpaid customers)
  - customer_balances (every customer's balance, for "kis kis se paise lene hain")

This REPLACES the old search_transactions tool, which had two bugs that
caused ASK to report wrong totals (e.g. "₹86,400" out of nowhere):
  1. It queried the "transactions" table with no shopkeeper filter at
     all, so its totals were summed across EVERY shopkeeper in the
     database, not just the one asking.
  2. It queried without pagination, so on a shop with more than 1000
     transactions the total would have been silently incomplete too.

All numbers here are computed by app.services.risk.summarize() over data
fetched via app.services.ledger_data (the same, paginated, shopkeeper-
scoped functions the Ledger/Risk screens use) — the LLM only explains
these numbers, it never calculates or invents them.
"""
from app.services.ledger_data import fetch_customers, fetch_transactions
from app.services.risk import summarize


def get_business_summary(shopkeeper_id: str = None) -> dict:
    if not shopkeeper_id:
        return {
            "error": "No shopkeeper session — cannot look up data.",
            "customer_count": 0,
            "total_transaction_count": 0,
            "total_credit_amount": 0.0,
            "total_payment_amount": 0.0,
            "total_receivable": 0.0,
            "total_payable": 0.0,
            "customer_balances": [],
        }

    customers = fetch_customers(shopkeeper_id)
    if not customers:
        return {
            "customer_count": 0,
            "total_transaction_count": 0,
            "total_credit_amount": 0.0,
            "total_payment_amount": 0.0,
            "total_receivable": 0.0,
            "total_payable": 0.0,
            "customer_balances": [],
        }

    by_customer: dict[str, list[dict]] = {c["id"]: [] for c in customers}
    for t in fetch_transactions(list(by_customer)):
        by_customer[t["customer_id"]].append(t)

    total_credit = 0.0
    total_payment = 0.0
    total_tx_count = 0
    total_receivable = 0.0
    total_payable = 0.0
    balances = []

    for c in customers:
        info = summarize(by_customer[c["id"]])
        total_credit += info["credit_total"]
        total_payment += info["payment_total"]
        total_tx_count += info["entry_count"]

        if info["balance"] > 0:
            total_receivable += info["balance"]
            status = "receivable"  # this customer owes the shopkeeper
        elif info["balance"] < 0:
            total_payable += -info["balance"]
            status = "payable"  # the shopkeeper owes this customer (advance/overpaid)
        else:
            status = "settled"

        balances.append({
            "customer": c["name"],
            "balance": info["balance"],
            "status": status,
        })

    # Biggest amount owed to the shopkeeper first.
    balances.sort(key=lambda b: b["balance"], reverse=True)

    return {
        "customer_count": len(customers),
        "total_transaction_count": total_tx_count,
        "total_credit_amount": round(total_credit, 2),
        "total_payment_amount": round(total_payment, 2),
        "total_amount": round(total_credit + total_payment, 2),
        "total_receivable": round(total_receivable, 2),
        "total_payable": round(total_payable, 2),
        "customer_balances": balances,
    }