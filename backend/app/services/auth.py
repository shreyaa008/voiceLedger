"""
Real authentication for VoiceLedger, backed by Supabase Auth.

This is the ONLY place in the backend allowed to produce a shopkeeper_id
for use in a database query. Every router that used to accept
shopkeeper_id from the request body, a query string, or (on the frontend)
localStorage must instead depend on get_current_shopkeeper_id() below.

How it works, end to end:
  1. The frontend signs up / logs in directly against Supabase Auth
     (via @supabase/supabase-js), which is the source of truth for
     passwords/sessions. VoiceLedger's backend never sees or stores a
     password.
  2. Supabase gives the frontend a session with an access_token (a JWT).
     The frontend sends that token on every API call as
     `Authorization: Bearer <token>`.
  3. get_current_user() verifies that token directly with Supabase Auth
     (a call to GET /auth/v1/user, which Supabase answers only for a
     currently-valid access token) and returns the authenticated user id.
     This is what actually proves "this request was made by user X" — a
     shopkeeper_id typed into a request body proves nothing.
  4. get_current_shopkeeper_id() looks up the `shopkeepers` row whose
     user_id column equals that authenticated user id, and returns ITS
     id. A shopkeeper can never end up scoped to another shopkeeper_id,
     because this lookup is keyed off the verified user id, not
     anything the client sent.
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException

from app.services.supabase_client import supabase


@dataclass
class AuthedUser:
    id: str
    email: Optional[str] = None


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token. Log in and send Authorization: Bearer <access_token>.",
        )
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def verify_access_token(token: str) -> AuthedUser:
    """Core verification, usable from both regular HTTP routes and the
    /ws/voice WebSocket (which can't send an Authorization header, so it
    passes the same access token as a query param instead — see
    routers/voice_live.py)."""
    try:
        result = supabase.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")

    user = getattr(result, "user", None) if result else None
    if not user or not getattr(user, "id", None):
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")

    return AuthedUser(id=user.id, email=getattr(user, "email", None))


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> AuthedUser:
    """FastAPI dependency: verifies the Supabase Auth access token on the
    incoming request and returns the authenticated user. Use this
    directly only for the bootstrap/me endpoints that manage the
    shopkeeper<->user link itself; every other route should depend on
    get_current_shopkeeper_id() instead."""
    token = _extract_bearer_token(authorization)
    return verify_access_token(token)


def shopkeeper_id_for_user(user_id: str) -> Optional[str]:
    """The shopkeepers.id linked to this Supabase Auth user id, or None
    if they haven't completed onboarding (POST /shopkeepers/bootstrap)
    yet."""
    found = (
        supabase
        .table("shopkeepers")
        .select("id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not found.data:
        return None
    return found.data[0]["id"]


async def get_current_shopkeeper_id(user: AuthedUser = Depends(get_current_user)) -> str:
    """FastAPI dependency used by every ledger/customer/transaction/ask
    route. Resolves the authenticated user straight to their own
    shopkeeper_id — nothing else ever determines shopkeeper_id again."""
    shopkeeper_id = shopkeeper_id_for_user(user.id)
    if not shopkeeper_id:
        raise HTTPException(
            status_code=404,
            detail="No shopkeeper linked to this account yet. Call POST /shopkeepers/bootstrap first.",
        )
    return shopkeeper_id