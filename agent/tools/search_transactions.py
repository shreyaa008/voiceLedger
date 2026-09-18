"""
Tool: search_transactions
Performs aggregate business analytics across transactions.
"""

def search_transactions(filter_query: dict = None) -> dict:
    """Perform aggregate transaction queries (e.g., top borrower, monthly total)."""
    filter_query = filter_query or {}

    # Mock aggregate search responses for Day 2 testing
    return {
        "results": [
            {"customer": "Suresh", "net_balance": 12000.0, "status": "overdue_60_days"},
            {"customer": "Ramesh", "net_balance": 1500.0, "status": "overdue_16_days"},
            {"customer": "Priya", "net_balance": 0.0, "status": "cleared"}
        ],
        "summary_metric": 13500.0
    }
