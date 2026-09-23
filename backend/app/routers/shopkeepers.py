"""
Per-shopkeeper identity — the fix for the shared-ledger data-isolation bug.

Root cause (see docs/README.md or the PR description): the frontend never
had a real login. Every browser used the same hardcoded
DEMO_SHOPKEEPER_ID, so two different shopkeepers were, as far as the
database was concerned, literally the same shopkeeper — every table was
already correctly scoped by shopkeeper_id, there was just only ever one
of them in use.

There is no auth system in this project yet (no Supabase Auth, no
sessions/JWTs anywhere in the codebase), so this endpoint is the
smallest safe stand-in: a shopkeeper identifies themselves once by phone
number, we get-or-create their row in the existing `shopkeepers` table
(phone is already UNIQUE in schema.sql), and the frontend remembers that
id on-device from then on. Same phone -> same shopkeeper_id, even across
devices; a different phone -> a different, properly isolated shopkeeper.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.supabase_client import supabase

router = APIRouter(prefix="/shopkeepers", tags=["shopkeepers"])


class ShopkeeperIdentify(BaseModel):
    name: str
    phone: str
    preferred_language: str | None = "hi"


@router.post("/identify")
async def identify_shopkeeper(payload: ShopkeeperIdentify):
    """Get-or-create a shopkeeper by phone number. Safe to call every time
    the app loads — returns the same row for a phone that already exists
    instead of creating a duplicate."""
    phone = payload.phone.strip()
    name = payload.name.strip()

    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    try:
        existing = (
            supabase
            .table("shopkeepers")
            .select("id, name, phone, preferred_language")
            .eq("phone", phone)
            .limit(1)
            .execute()
        )
        if existing.data:
            return {"shopkeeper": existing.data[0]}

        created = (
            supabase
            .table("shopkeepers")
            .insert({
                "name": name,
                "phone": phone,
                "preferred_language": payload.preferred_language or "hi",
            })
            .execute()
        )
        if not created.data:
            raise HTTPException(status_code=500, detail="Could not create shopkeeper")

        return {"shopkeeper": created.data[0]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))