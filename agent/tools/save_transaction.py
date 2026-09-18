"""
Tool: save_transaction
Saves a confirmed transaction (credit or payment) to the Supabase database.
"""

import os
from datetime import datetime
from dotenv import load_dotenv

from backend.app.services.supabase_client import supabase


def _get_or_create_shopkeeper_id() -> str:
    """Ensure a default shopkeeper exists and return their UUID."""
    res = supabase.table("shopkeepers").select("id").limit(1).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]["id"]
    
    # Create default shopkeeper if none exists
    new_shopkeeper = supabase.table("shopkeepers").insert({
        "name": "Dukaan Owner",
        "preferred_language": "hi"
    }).execute()
    return new_shopkeeper.data[0]["id"]


def save_transaction(customer_name: str, amount: float, type: str, date: str = None) -> dict:
    """Save a confirmed transaction into the Supabase ledger."""
    try:
        normalized_name = customer_name.strip().title()
        tx_type = type.strip().lower()
        if tx_type not in ["credit", "payment"]:
            tx_type = "credit"
        
        tx_date = date or datetime.now().strftime("%Y-%m-%d")
        
        # 1. Look up existing customer by name
        cust_res = supabase.table("customers").select("id, name").ilike("name", normalized_name).execute()
        
        if cust_res.data and len(cust_res.data) > 0:
            customer_id = cust_res.data[0]["id"]
        else:
            # Create new customer
            shopkeeper_id = _get_or_create_shopkeeper_id()
            new_cust = supabase.table("customers").insert({
                "name": normalized_name,
                "shopkeeper_id": shopkeeper_id
            }).execute()
            customer_id = new_cust.data[0]["id"]
        
        # 2. Insert transaction
        tx_data = {
            "customer_id": customer_id,
            "amount": float(amount),
            "type": tx_type,
            "date": tx_date
        }
        inserted_tx = supabase.table("transactions").insert(tx_data).execute()
        tx_id = inserted_tx.data[0]["id"] if inserted_tx.data else "tx_created"

        return {
            "status": "success",
            "transaction_id": str(tx_id),
            "customer": normalized_name,
            "amount": float(amount),
            "type": tx_type,
            "date": tx_date
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to save transaction: {str(e)}"
        }
