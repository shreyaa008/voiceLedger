"""
Tool: search_transactions
Performs aggregate business queries across customers and transactions using live Supabase data.
Currency: Indian Rupees (₹).
"""

from datetime import datetime, date
from backend.app.services.supabase_client import supabase


def search_transactions(filter_query: dict = None) -> dict:
    """
    Perform aggregate transaction queries on live Supabase data:
    - Top debtor (customer with highest net credit)
    - Monthly collection totals
    - Overdue balances list
    """
    try:
        filter_query = filter_query or {}
        
        # 1. Fetch all customers and all transactions
        cust_res = supabase.table("customers").select("id, name").execute()
        tx_res = supabase.table("transactions").select("*").execute()

        customers = cust_res.data or []
        transactions = tx_res.data or []

        # Map customer ID to Name
        cust_map = {c["id"]: c["name"] for c in customers}

        # Calculate balance per customer
        customer_balances = {}
        for c in customers:
            customer_balances[c["id"]] = {"name": c["name"], "balance": 0.0, "credits": 0.0, "payments": 0.0}

        for t in transactions:
            cid = t.get("customer_id")
            if cid in customer_balances:
                amt = float(t.get("amount", 0))
                if t.get("type") == "credit":
                    customer_balances[cid]["balance"] += amt
                    customer_balances[cid]["credits"] += amt
                elif t.get("type") == "payment":
                    customer_balances[cid]["balance"] -= amt
                    customer_balances[cid]["payments"] += amt

        # Sort debtors by balance descending
        sorted_debtors = sorted(customer_balances.values(), key=lambda x: x["balance"], reverse=True)
        top_debtor = sorted_debtors[0] if sorted_debtors and sorted_debtors[0]["balance"] > 0 else None

        # Calculate total payments for current month
        current_month = datetime.now().strftime("%Y-%m")
        monthly_payments = sum(
            float(t.get("amount", 0)) for t in transactions 
            if t.get("type") == "payment" and str(t.get("date", "")).startswith(current_month)
        )

        results = [
            {"customer": d["name"], "net_balance_rupees": round(d["balance"], 2)}
            for d in sorted_debtors if d["balance"] > 0
        ]

        return {
            "results": results,
            "top_debtor": {
                "customer": top_debtor["name"] if top_debtor else "None",
                "balance_rupees": round(top_debtor["balance"], 2) if top_debtor else 0.0
            },
            "current_month_payments_rupees": round(monthly_payments, 2),
            "total_debtors_count": len(results)
        }
    except Exception as e:
        return {
            "results": [],
            "top_debtor": {"customer": "None", "balance_rupees": 0.0},
            "error": str(e)
        }
