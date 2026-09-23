"""
Tool: generate_reminder  (READ-ONLY)

Composes a reminder message using the customer's REAL balance for the
shopkeeper asking — text comes from app.services.risk.reminder_text(),
the exact same wording the Ledger page's "Remind" button uses.

This tool only returns text for the shopkeeper to read out or send
themselves. It does not send anything and does not write to the database.
"""
from app.services.ledger_data import fetch_transactions, find_customer
from app.services.risk import reminder_text, summarize


def generate_reminder(customer_name: str, tone: str = "polite", language: str = "hi", shopkeeper_id: str = None) -> dict:
    tone = (tone or "polite").lower().strip()
    language = (language or "hi").lower().strip()

    if not shopkeeper_id:
        return {
            "customer": customer_name,
            "found": False,
            "amount_due": 0.0,
            "days_overdue": 0,
            "reminder_text": "No shopkeeper session — cannot look up data.",
        }

    customer = find_customer(shopkeeper_id, customer_name)
    if customer is None:
        msg = (
            f"Is naam ({customer_name}) ka koi record nahi mila."
            if language == "hi"
            else f"No record found for {customer_name}."
        )
        return {
            "customer": customer_name,
            "found": False,
            "amount_due": 0.0,
            "days_overdue": 0,
            "reminder_text": msg,
        }

    info = summarize(fetch_transactions([customer["id"]]))

    if info["balance"] <= 0:
        msg = (
            f"{customer['name']} ji ka koi udhaar baaki nahi hai."
            if language == "hi"
            else f"{customer['name']} has zero outstanding balance."
        )
        return {
            "customer": customer["name"],
            "found": True,
            "amount_due": 0.0,
            "days_overdue": 0,
            "reminder_text": msg,
        }

    return {
        "customer": customer["name"],
        "found": True,
        "amount_due": info["balance"],
        "days_overdue": info["days_overdue"],
        "reminder_text": reminder_text(
            customer["name"], info["balance"], info["days_overdue"], tone, language
        ),
    }