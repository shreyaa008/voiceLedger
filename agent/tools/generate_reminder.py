"""
Tool: generate_reminder
Produces personalized debt reminder messages in Hindi or English with polite, standard, or firm tone.
"""

def generate_reminder(customer_name: str, tone: str = "polite", language: str = "hi") -> dict:
    """Generate a personalized debt reminder message."""
    normalized_name = customer_name.strip().title()
    tone = tone.lower()
    language = language.lower()

    # Mock customer balances for Day 2 testing
    mock_balances = {
        "Ramesh": {"amount": 1500.0, "days_overdue": 16},
        "Suresh": {"amount": 12000.0, "days_overdue": 68},
        "Priya": {"amount": 0.0, "days_overdue": 0}
    }

    cust_info = mock_balances.get(normalized_name, {"amount": 1000.0, "days_overdue": 10})
    amount = cust_info["amount"]
    days = cust_info["days_overdue"]

    if language == "hi":
        if tone == "firm":
            text = f"Namaste {normalized_name} ji, aapka ₹{int(amount)} ka udhaar {days} din se pending hai. Kripya turant bhugtan karein taaki aage udhaar jari rakha ja sake."
        elif tone == "standard":
            text = f"Namaste {normalized_name} ji, aapka kul baaki balance ₹{int(amount)} hai. Kripya samay par chukta karein."
        else:  # polite
            text = f"Namaste {normalized_name} ji, aasha hai aap theek hain. Ek chota reminder ki aapka ₹{int(amount)} ka balance baaki hai. Suvidhanusaar bhej dijiye."
    else:
        if tone == "firm":
            text = f"Dear {normalized_name}, your balance of ₹{int(amount)} is overdue by {days} days. Please settle this immediately to continue credit services."
        elif tone == "standard":
            text = f"Dear {normalized_name}, this is a reminder that your outstanding balance is ₹{int(amount)}. Please arrange for payment."
        else:  # polite
            text = f"Hello {normalized_name}, hope you are doing well! Just a gentle reminder regarding your pending balance of ₹{int(amount)}. Thank you."

    return {
        "customer": normalized_name,
        "amount_due": amount,
        "days_overdue": days,
        "reminder_text": text
    }
