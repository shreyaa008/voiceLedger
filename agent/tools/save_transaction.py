"""
Tool: save_transaction
Saves a confirmed transaction to the ledger.
"""

def save_transaction(customer_name: str, amount: float, type: str, date: str = None) -> dict:
    """Save a confirmed transaction into the ledger."""
    normalized_name = customer_name.strip().title()

    # Mock save response for Day 2 testing
    return {
        "status": "success",
        "transaction_id": "tx_mock_12345",
        "customer": normalized_name,
        "amount": amount,
        "type": type,
        "date": date or "2026-09-17"
    }
