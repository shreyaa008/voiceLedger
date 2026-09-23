"""
Shopkeeper identity — linking a real Supabase Auth user to their
`shopkeepers` row.

Replaces the old per-device "identify by phone number" stand-in
(POST /shopkeepers/identify), which trusted whatever name/phone the
frontend sent and let any client claim any shopkeeper_id. That endpoint
is gone. From here on, a shopkeeper_id is only ever produced by
app.services.auth.get_current_shopkeeper_id(), which resolves the
signed-in Supabase Auth user to their own shopkeepers.user_id — never
something a client sends directly.

  POST /shopkeepers/bootstrap  — call once, right after sign up (or first
                                  login on a fresh account): get-or-create
                                  the shopkeepers row for the signed-in
                                  user.
  GET  /shopkeepers/me         — fetch the signed-in user's shopkeeper
                                  profile; 404 if bootstrap hasn't run yet.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import AuthedUser, get_current_user
from app.services.supabase_client import supabase

router = APIRouter(prefix="/shopkeepers", tags=["shopkeepers"])


class BootstrapRequest(BaseModel):
    name: str
    phone: str | None = None
    preferred_language: str | None = "hi"


@router.post("/bootstrap")
async def bootstrap_shopkeeper(
    payload: BootstrapRequest,
    user: AuthedUser = Depends(get_current_user),
):
    """Get-or-create the shopkeeper row for the signed-in Supabase Auth
    user. Idempotent/safe to call every time the app loads — returns the
    existing row for this user_id instead of creating a duplicate."""
    try:
        existing = (
            supabase
            .table("shopkeepers")
            .select("id, name, phone, preferred_language")
            .eq("user_id", user.id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return {"shopkeeper": existing.data[0]}

        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")

        created = (
            supabase
            .table("shopkeepers")
            .insert({
                "user_id": user.id,
                "name": name,
                "phone": (payload.phone or "").strip() or None,
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


@router.get("/me")
async def get_my_shopkeeper(user: AuthedUser = Depends(get_current_user)):
    """The shopkeeper profile linked to the signed-in user. 404 means
    bootstrap hasn't been called yet for this account (e.g. right after
    sign up, before the frontend's onboarding step runs)."""
    try:
        existing = (
            supabase
            .table("shopkeepers")
            .select("id, name, phone, preferred_language")
            .eq("user_id", user.id)
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="No shopkeeper linked to this account yet")
        return {"shopkeeper": existing.data[0]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))