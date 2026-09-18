"""
Tool: get_customer_ledger
Fetches customer balance and transaction history directly from Supabase.
"""

import os
from dotenv import load_dotenv

from backend.app.services.supabase_client import supabase


def get_customer_ledger(customer_name: str) -> dict:
    """Fetch customer balance and transaction history from Supabase database."""
    try:
        normalized_name = customer_name.strip().title()
        
        # 1. Query customer by name
        cust_res = supabase.table("customers").select("id, name").ilike("name", normalized_name).execute()
        
        if not cust_res.data or len(cust_res.data) == 0:
            return {
                "customer": customer_name,
                "found": False,
                "net_balance": 0.0,
                "transactions": []
            }
        
        customer = cust_res.data[0]
        customer_id = customer["id"]
        
        # 2. Query transactions for customer
        tx_res = supabase.table("transactions").select("*").eq("customer_id", customer_id).order("date", desc=True).execute()
        transactions = tx_res.data or []
        
        # 3. Calculate net balance: SUM(credit) - SUM(payment)
        credits = sum(float(t.get("amount", 0)) for t in transactions if t.get("type") == "credit")
        payments = sum(float(t.get("amount", 0)) for t in transactions if t.get("type") == "payment")
        net_balance = credits - payments
        
        return {
            "customer": customer["name"],
            "found": True,
            "net_balance": round(float(net_balance), 2),
            "transactions": transactions
        }
    except Exception as e:
        return {
            "customer": customer_name,
            "found": False,
            "net_balance": 0.0,
            "transactions": [],
            "error": str(e)
        }
