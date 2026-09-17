"""
Tool: get_customer_ledger
Fetches customer balance and transaction history.
"""

def get_customer_ledger(customer_name: str) -> dict:
    """Fetch customer balance and transaction history."""
    normalized_name = customer_name.strip().title()
    
    # Mock data for Day 2 testing
    mock_ledgers = {
        "Ramesh": {
            "customer": "Ramesh",
            "found": True,
            "net_balance": 1500.0,
            "transactions": [
                {"id": "t-1", "amount": 2000.0, "type": "credit", "date": "2026-08-15", "due_date": "2026-09-01"},
                {"id": "t-2", "amount": 500.0, "type": "payment", "date": "2026-08-25", "due_date": None}
            ]
        },
        "Suresh": {
            "customer": "Suresh",
            "found": True,
            "net_balance": 12000.0,
            "transactions": [
                {"id": "t-3", "amount": 12000.0, "type": "credit", "date": "2026-06-10", "due_date": "2026-07-10"}
            ]
        },
        "Priya": {
            "customer": "Priya",
            "found": True,
            "net_balance": 0.0,
            "transactions": [
                {"id": "t-4", "amount": 1000.0, "type": "credit", "date": "2026-09-01", "due_date": "2026-09-15"},
                {"id": "t-5", "amount": 1000.0, "type": "payment", "date": "2026-09-10", "due_date": None}
            ]
        }
    }

    if normalized_name in mock_ledgers:
        return mock_ledgers[normalized_name]

    return {
        "customer": customer_name,
        "found": False,
        "net_balance": 0.0,
        "transactions": []
    }
