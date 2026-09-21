"""
Tool: generate_reminder
Produces personalized payment reminder messages in Hindi or English using live customer data.
Supports Polite, Standard, and Firm tones.
Currency: Indian Rupees (₹).
"""

from datetime import datetime, date
from backend.app.services.supabase_client import supabase


def generate_reminder(customer_name: str, tone: str = "polite", language: str = "hi") -> dict:
    """Generate a personalized debt reminder message using live Supabase balance in Rupees."""
    try:
        normalized_name = customer_name.strip().title()
        tone = tone.lower().strip() if tone else "polite"
        language = language.lower().strip() if language else "hi"

        # 1. Fetch customer from Supabase
        cust_res = supabase.table("customers").select("id, name").ilike("name", normalized_name).execute()
        if not cust_res.data or len(cust_res.data) == 0:
            return {
                "customer": customer_name,
                "found": False,
                "amount_due": 0.0,
                "days_overdue": 0,
                "reminder_text": f"Customer record not found for {customer_name}."
            }

        customer = cust_res.data[0]
        customer_id = customer["id"]

        # 2. Fetch transactions
        tx_res = supabase.table("transactions").select("*").eq("customer_id", customer_id).order("date", desc=True).execute()
        transactions = tx_res.data or []

        credits = sum(float(t.get("amount", 0)) for t in transactions if t.get("type") == "credit")
        payments = sum(float(t.get("amount", 0)) for t in transactions if t.get("type") == "payment")
        net_balance = credits - payments

        if net_balance <= 0:
            msg = f"{customer['name']} ji ka koi udhaar baaki nahi hai." if language == "hi" else f"{customer['name']} has zero outstanding balance."
            return {
                "customer": customer["name"],
                "found": True,
                "amount_due": 0.0,
                "days_overdue": 0,
                "reminder_text": msg
            }

        # 3. Calculate overdue days
        today = date.today()
        days_overdue = 0
        for t in transactions:
            if t.get("type") == "credit":
                tx_date_str = t.get("due_date") or t.get("date")
                if tx_date_str:
                    try:
                        tx_d = datetime.strptime(str(tx_date_str)[:10], "%Y-%m-%d").date()
                        diff = (today - tx_d).days
                        if diff > days_overdue:
                            days_overdue = diff
                    except Exception:
                        pass

        amount_str = f"₹{int(net_balance)}"

        # 4. Generate Tone-specific Message
        if language == "hi":
            if tone in ["firm", "strict", "sakht"]:
                text = f"Namaste {customer['name']} ji, aapka {amount_str} ka udhaar {days_overdue} din se pending hai. Kripya turant bhugtan karein taaki aage udhaar jari rakha ja sake."
            elif tone == "standard":
                text = f"Namaste {customer['name']} ji, aapka kul baaki balance {amount_str} hai. Kripya samay par chukta karein."
            else:  # polite (default)
                text = f"Namaste {customer['name']} ji, aasha hai aap kushal hain. Ek chota reminder ki aapka {amount_str} ka balance baaki hai. Suvidhanusaar bhej dijiye."
        else:
            if tone in ["firm", "strict"]:
                text = f"Dear {customer['name']}, your pending balance of {amount_str} is overdue by {days_overdue} days. Please settle this immediately to avoid interruption in credit."
            elif tone == "standard":
                text = f"Dear {customer['name']}, this is a friendly reminder that your outstanding balance is {amount_str}. Kindly arrange for payment."
            else:  # polite
                text = f"Hello {customer['name']}, hope you are doing well! Just a gentle reminder regarding your pending balance of {amount_str}. Thank you!"

        return {
            "customer": customer["name"],
            "found": True,
            "amount_due": round(float(net_balance), 2),
            "days_overdue": days_overdue,
            "reminder_text": text
        }
    except Exception as e:
        return {
            "customer": customer_name,
            "found": False,
            "amount_due": 0.0,
            "days_overdue": 0,
            "reminder_text": f"Error generating reminder: {str(e)}"
        }
