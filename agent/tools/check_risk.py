"""
Tool: check_risk
Calculates credit risk level (GREEN/YELLOW/RED) and risk score for a customer.
"""

def check_risk(customer_name: str) -> dict:
    """Calculate credit risk level and score for a customer."""
    normalized_name = customer_name.strip().title()

    # Mock risk assessments for Day 2 testing
    mock_risk = {
        "Ramesh": {
            "customer": "Ramesh",
            "risk_level": "YELLOW",
            "score": 45,
            "reasons": ["Balance overdue by 16 days", "Outstanding amount is ₹1,500"]
        },
        "Suresh": {
            "customer": "Suresh",
            "risk_level": "RED",
            "score": 80,
            "reasons": ["Outstanding amount > ₹10,000", "Balance overdue > 60 days"]
        },
        "Priya": {
            "customer": "Priya",
            "risk_level": "GREEN",
            "score": 10,
            "reasons": ["All past credits paid on time", "Current balance is ₹0"]
        }
    }

    if normalized_name in mock_risk:
        return mock_risk[normalized_name]

    return {
        "customer": customer_name,
        "risk_level": "UNKNOWN",
        "score": 0,
        "reasons": ["Customer record not found"]
    }
