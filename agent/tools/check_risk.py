"""
Tool: check_risk  (READ-ONLY)

Credit risk level and score for a customer — scoped to the shopkeeper
asking, computed by app.services.risk.summarize(), the SAME risk formula
that powers the Risk screen. (Previously this tool had its own separate,
slightly different risk formula from the Risk page's — that inconsistency
is part of why ASK could contradict the app. Now there's one formula.)
"""
from app.services.ledger_data import fetch_transactions, find_customer
from app.services.risk import summarize


def check_risk(customer_name: str, shopkeeper_id: str = None) -> dict:
    if not shopkeeper_id:
        return {
            "customer": customer_name,
            "found": False,
            "risk_level": "UNKNOWN",
            "score": 0,
            "reasons": ["No shopkeeper session — cannot look up data."],
        }

    customer = find_customer(shopkeeper_id, customer_name)
    if customer is None:
        return {
            "customer": customer_name,
            "found": False,
            "risk_level": "UNKNOWN",
            "score": 0,
            "reasons": ["Customer record not found"],
        }

    info = summarize(fetch_transactions([customer["id"]]))

    return {
        "customer": customer["name"],
        "found": True,
        "risk_level": info["risk_level"],
        "score": info["score"],
        "net_balance": info["balance"],
        "days_overdue": info["days_overdue"],
        "reasons": info["reasons"],
    }