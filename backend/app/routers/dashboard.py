"""
Endpoints behind the Ledger and Risk screens.

  GET  /dashboard/summary                      every customer + balance + risk (2 DB queries total),
                                                 scoped to the signed-in shopkeeper via Authorization: Bearer
  POST /dashboard/reminder                      ready-to-send payment reminder text

A single customer's entries still come from the existing
GET /customers/{customer_id}/ledger endpoint.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import get_current_shopkeeper_id
from app.services.ledger_data import fetch_customers, fetch_transactions
from app.services.risk import reminder_text, summarize
from app.services.supabase_client import supabase

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(shopkeeper_id: str = Depends(get_current_shopkeeper_id)):
    try:
        customers = fetch_customers(shopkeeper_id)

        if not customers:
            return {
                "totals": {"you_will_get": 0, "you_will_give": 0, "customer_count": 0},
                "risk_counts": {"RED": 0, "YELLOW": 0, "GREEN": 0},
                "customers": [],
            }

        by_customer: dict[str, list[dict]] = {c["id"]: [] for c in customers}
        for t in fetch_transactions(list(by_customer)):
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
    customer_id: str
    tone: Literal["polite", "standard", "firm"] = "polite"
    language: Literal["hi", "en"] = "hi"


@router.post("/reminder")
async def make_reminder(
    req: ReminderRequest,
    shopkeeper_id: str = Depends(get_current_shopkeeper_id),
):
    try:
        found = (
            supabase.table("customers")
            .select("id, name, phone")
            .eq("id", req.customer_id)
            .eq("shopkeeper_id", shopkeeper_id)
            .limit(1)
            .execute()
            .data
        )
        if not found:
            raise HTTPException(status_code=404, detail="Customer not found")
        customer = found[0]

        info = summarize(fetch_transactions([customer["id"]]))

        if info["balance"] <= 0:
            raise HTTPException(status_code=400, detail=f"{customer['name']} has nothing pending")

        return {
            "customer": customer["name"],
            "phone": customer.get("phone"),
            "amount_due": info["balance"],
            "days_overdue": info["days_overdue"],
            "tone": req.tone,
            "language": req.language,
            "reminder_text": reminder_text(
                customer["name"], info["balance"], info["days_overdue"], req.tone, req.language
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))