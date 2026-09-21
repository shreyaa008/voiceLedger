"""
Endpoints behind the Ledger and Risk screens.

  GET  /dashboard/summary?shopkeeper_id=...   every customer + balance + risk (2 DB queries total)
  POST /dashboard/reminder                    ready-to-send payment reminder text

A single customer's entries still come from the existing
GET /customers/{customer_id}/ledger endpoint.
"""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.risk import inr, summarize
from app.services.supabase_client import supabase

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

PAGE_SIZE = 1000  # Supabase returns at most 1000 rows per request


def _fetch_transactions(customer_ids: list[str]) -> list[dict]:
    """All transactions for these customers, paging past Supabase's 1000-row limit."""
    rows: list[dict] = []
    start = 0
    while True:
        page = (
            supabase.table("transactions")
            .select("id, customer_id, amount, type, date, due_date")
            .in_("customer_id", customer_ids)
            .order("id")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


@router.get("/summary")
async def dashboard_summary(shopkeeper_id: str):
    try:
        customers = (
            supabase.table("customers")
            .select("id, name, phone")
            .eq("shopkeeper_id", shopkeeper_id)
            .execute()
            .data
            or []
        )

        if not customers:
            return {
                "totals": {"you_will_get": 0, "you_will_give": 0, "customer_count": 0},
                "risk_counts": {"RED": 0, "YELLOW": 0, "GREEN": 0},
                "customers": [],
            }

        by_customer: dict[str, list[dict]] = {c["id"]: [] for c in customers}
        for t in _fetch_transactions(list(by_customer)):
            by_customer[t["customer_id"]].append(t)

        result = []
        you_will_get = 0.0
        you_will_give = 0.0
        risk_counts = {"RED": 0, "YELLOW": 0, "GREEN": 0}

        for c in customers:
            info = summarize(by_customer[c["id"]])
            result.append({"id": c["id"], "name": c["name"], "phone": c.get("phone"), **info})
            if info["balance"] > 0:
                you_will_get += info["balance"]
                risk_counts[info["risk_level"]] += 1
            elif info["balance"] < 0:
                you_will_give += -info["balance"]

        # Biggest amount owed first; settled / advance customers drop to the bottom.
        result.sort(key=lambda r: r["balance"], reverse=True)

        return {
            "totals": {
                "you_will_get": round(you_will_get, 2),
                "you_will_give": round(you_will_give, 2),
                "customer_count": len(customers),
            },
            "risk_counts": risk_counts,
            "customers": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ReminderRequest(BaseModel):
    shopkeeper_id: str
    customer_id: str
    tone: Literal["polite", "standard", "firm"] = "polite"
    language: Literal["hi", "en"] = "hi"


def _reminder_text(name: str, amount: float, days: int, tone: str, language: str) -> str:
    amt = inr(amount)
    if language == "hi":
        if tone == "firm":
            return (
                f"Namaste {name} ji, aapka {amt} ka udhaar {days} din se baaki hai. "
                "Kripya jaldi se jaldi bhugtan karein taaki aage bhi udhaar diya ja sake."
            )
        if tone == "standard":
            return f"Namaste {name} ji, aapka kul baaki balance {amt} hai. Kripya samay par chukta karein."
        return (
            f"Namaste {name} ji, aasha hai aap kushal hain. Ek chhota sa reminder — "
            f"aapka {amt} baaki hai. Suvidha anusaar bhej dijiye. Dhanyavaad!"
        )

    if tone == "firm":
        return (
            f"Dear {name}, your balance of {amt} has been pending for {days} days. "
            "Please clear it as soon as possible so we can continue giving credit."
        )
    if tone == "standard":
        return f"Dear {name}, this is a reminder that your outstanding balance is {amt}. Kindly arrange the payment."
    return f"Hello {name}, hope you're doing well! A gentle reminder about your pending balance of {amt}. Thank you!"


@router.post("/reminder")
async def make_reminder(req: ReminderRequest):
    try:
        found = (
            supabase.table("customers")
            .select("id, name, phone")
            .eq("id", req.customer_id)
            .eq("shopkeeper_id", req.shopkeeper_id)
            .limit(1)
            .execute()
            .data
        )
        if not found:
            raise HTTPException(status_code=404, detail="Customer not found")
        customer = found[0]

        info = summarize(_fetch_transactions([customer["id"]]))

        if info["balance"] <= 0:
            raise HTTPException(status_code=400, detail=f"{customer['name']} has nothing pending")

        return {
            "customer": customer["name"],
            "phone": customer.get("phone"),
            "amount_due": info["balance"],
            "days_overdue": info["days_overdue"],
            "tone": req.tone,
            "language": req.language,
            "reminder_text": _reminder_text(
                customer["name"], info["balance"], info["days_overdue"], req.tone, req.language
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))