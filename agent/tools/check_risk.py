"""
Tool: check_risk
Deterministic rule-based credit risk engine for VoiceLedger.
Calculates credit risk score (0-100) and badges (GREEN/YELLOW/RED) using live Supabase data.
Currency: Indian Rupees (₹).
"""

from datetime import datetime, date
from backend.app.services.supabase_client import supabase


def check_risk(customer_name: str) -> dict:
    """
    Calculate credit risk score and level for a customer based on 3 rules:
    1. Outstanding amount (> ₹5,000 => +30, > ₹10,000 => +50)
    2. Oldest overdue transaction (> 30 days => +30, > 60 days => +50)
    3. Payment ratio (Payments / Total tx < 0.3 => +20)
    """
    try:
        normalized_name = customer_name.strip().title()

        # 1. Query customer
        cust_res = supabase.table("customers").select("id, name").ilike("name", normalized_name).execute()
        if not cust_res.data or len(cust_res.data) == 0:
            return {
                "customer": customer_name,
                "found": False,
                "risk_level": "UNKNOWN",
                "score": 0,
                "reasons": ["Customer record not found"]
            }

        customer = cust_res.data[0]
        customer_id = customer["id"]

        # 2. Query transactions
        tx_res = supabase.table("transactions").select("*").eq("customer_id", customer_id).order("date", desc=True).execute()
        transactions = tx_res.data or []

        if not transactions:
            return {
                "customer": customer["name"],
                "found": True,
                "risk_level": "GREEN",
                "score": 0,
                "net_balance": 0.0,
                "reasons": ["No pending credit transactions"]
            }

        # Calculate Net Balance in Rupees
        credits = sum(float(t.get("amount", 0)) for t in transactions if t.get("type") == "credit")
        payments = sum(float(t.get("amount", 0)) for t in transactions if t.get("type") == "payment")
        net_balance = credits - payments

        score = 0
        reasons = []

        # Rule 1: Outstanding Balance in Rupees (₹)
        if net_balance > 10000:
            score += 50
            reasons.append(f"High outstanding balance of ₹{int(net_balance)} (> ₹10,000)")
        elif net_balance > 5000:
            score += 30
            reasons.append(f"Moderate outstanding balance of ₹{int(net_balance)} (> ₹5,000)")

        # Rule 2: Days Overdue
        today = date.today()
        max_days_overdue = 0
        for t in transactions:
            if t.get("type") == "credit":
                tx_date_str = t.get("due_date") or t.get("date")
                if tx_date_str:
                    try:
                        tx_d = datetime.strptime(str(tx_date_str)[:10], "%Y-%m-%d").date()
                        days_diff = (today - tx_d).days
                        if days_diff > max_days_overdue:
                            max_days_overdue = days_diff
                    except Exception:
                        pass

        if max_days_overdue > 60:
            score += 50
            reasons.append(f"Payment overdue by {max_days_overdue} days (> 60 days)")
        elif max_days_overdue > 30:
            score += 30
            reasons.append(f"Payment overdue by {max_days_overdue} days (> 30 days)")

        # Rule 3: Repayment Frequency (Payments / Total Transactions)
        total_tx_count = len(transactions)
        payment_tx_count = len([t for t in transactions if t.get("type") == "payment"])
        ratio = (payment_tx_count / total_tx_count) if total_tx_count > 0 else 1.0

        if total_tx_count >= 2 and ratio < 0.3:
            score += 20
            reasons.append(f"Low repayment frequency ({payment_tx_count} payments out of {total_tx_count} transactions)")

        # Cap score at 100
        score = min(score, 100)

        # Determine Risk Level Badge
        if score >= 70:
            risk_level = "RED"
        elif score >= 40:
            risk_level = "YELLOW"
        else:
            risk_level = "GREEN"

        if not reasons:
            reasons.append("Clean payment record with low pending balance")

        return {
            "customer": customer["name"],
            "found": True,
            "risk_level": risk_level,
            "score": score,
            "net_balance": round(float(net_balance), 2),
            "reasons": reasons
        }
    except Exception as e:
        return {
            "customer": customer_name,
            "found": False,
            "risk_level": "UNKNOWN",
            "score": 0,
            "reasons": [f"Error checking risk: {str(e)}"]
        }
