"""
Tool: get_customer_ledger  (READ-ONLY)

Fetch one customer's balance and full transaction history — scoped to the
shopkeeper asking, using the exact same data access and balance math as
the Ledger screen (app.services.ledger_data + app.services.risk.summarize),
so ASK's numbers can never disagree with what's on screen.

Never creates a customer. If none is found for this shopkeeper, returns
found=False — the caller (system prompt) is instructed to say so plainly,
not invent a record.
"""
from app.services.ledger_data import fetch_transactions, find_customer
from app.services.risk import summarize


def get_customer_ledger(customer_name: str, shopkeeper_id: str = None) -> dict:
    if not shopkeeper_id:
        return {
            "customer": customer_name,
            "found": False,
            "net_balance": 0.0,
            "transactions": [],
            "error": "No shopkeeper session — cannot look up data.",
        }

    customer = find_customer(shopkeeper_id, customer_name)
    if customer is None:
        return {
            "customer": customer_name,
            "found": False,
            "net_balance": 0.0,
            "transactions": [],
        }

    transactions = fetch_transactions([customer["id"]])
    info = summarize(transactions)

    return {
        "customer": customer["name"],
        "found": True,
        "net_balance": info["balance"],
        "credit_total": info["credit_total"],
        "payment_total": info["payment_total"],
        "entry_count": info["entry_count"],
        "last_activity": info["last_activity"],
        "transactions": transactions,
    }