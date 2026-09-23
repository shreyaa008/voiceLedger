from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
)
from app.services.auth import get_current_shopkeeper_id
from app.services.azure_language import extract_transaction
from app.services.customer_identity import canonical_key, display_name
from app.services.supabase_client import supabase


router = APIRouter()


def _customer_belongs_to(customer_id: str, shopkeeper_id: str) -> bool:
    """True only if `customer_id` exists AND is owned by this shopkeeper.
    Used to enforce ownership before creating anything under a
    client-supplied customer_id."""
    found = (
        supabase
        .table("customers")
        .select("id")
        .eq("id", customer_id)
        .eq("shopkeeper_id", shopkeeper_id)
        .limit(1)
        .execute()
    )
    return bool(found.data)


def _transaction_owner_shopkeeper_id(transaction_id: str) -> str | None:
    """The shopkeeper_id that actually owns this transaction (via its
    customer), or None if the transaction doesn't exist. Used to enforce
    ownership before PATCH/DELETE, since transactions don't carry
    shopkeeper_id directly — they belong to a customer, who belongs to a
    shopkeeper."""
    found = (
        supabase
        .table("transactions")
        .select("id, customers(shopkeeper_id)")
        .eq("id", transaction_id)
        .limit(1)
        .execute()
    )
    if not found.data:
        return None
    customer = found.data[0].get("customers")
    if not customer:
        return None
    return customer.get("shopkeeper_id")

# How long an identical (customer, amount, type, raw_text) submission is
# treated as an accidental duplicate rather than a genuine second entry —
# guards against double network retries / VAD firing twice for one
# utterance. A shopkeeper can still log the same amount for the same
# customer again on purpose after this window.
DUPLICATE_SAVE_WINDOW_SECONDS = 8


def _insert_customer(shopkeeper_id: str, name: str):
    """Create a customer row. Opportunistically stores canonical_key if the
    optional migration (backend/app/db/migrations/002_customer_canonical_key.sql)
    has been applied; degrades gracefully if it hasn't, since duplicate
    matching itself does not depend on that column — see
    _find_customer_by_name, which computes it in Python instead."""
    try:
        return (
            supabase
            .table("customers")
            .insert({
                "shopkeeper_id": shopkeeper_id,
                "name": name,
                "canonical_key": canonical_key(name),
            })
            .execute()
        )
    except Exception as e:
        if "canonical_key" not in str(e):
            raise
        return (
            supabase
            .table("customers")
            .insert({"shopkeeper_id": shopkeeper_id, "name": name})
            .execute()
        )


def _find_customer_by_name(shopkeeper_id: str, name: str) -> dict | None:
    """Match a customer by canonical identity (case/script-insensitive),
    not by exact string equality — see customer_identity.py for why."""
    existing = (
        supabase
        .table("customers")
        .select("id, name, phone, shopkeeper_id")
        .eq("shopkeeper_id", shopkeeper_id)
        .execute()
    )
    target_key = canonical_key(name)
    for row in existing.data or []:
        if canonical_key(row["name"]) == target_key:
            return row
    return None


@router.post(
    "/transactions",
    response_model=TransactionResponse
)
async def create_transaction(
    transaction: TransactionCreate,
    shopkeeper_id: str = Depends(get_current_shopkeeper_id),
):
    # Ownership check: the customer this transaction is being attached to
    # must belong to the signed-in shopkeeper — otherwise a shopkeeper
    # could post a transaction onto another shopkeeper's customer_id.
    if not _customer_belongs_to(transaction.customer_id, shopkeeper_id):
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        data = {
            "customer_id": transaction.customer_id,
            "amount": float(transaction.amount),
            "type": transaction.type,
            "date": transaction.date.isoformat(),
            "due_date": (
                transaction.due_date.isoformat()
                if transaction.due_date
                else None
            ),
            "raw_text": transaction.raw_text,
            "language": transaction.language,
        }

        response = (
            supabase
            .table("transactions")
            .insert(data)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=500,
                detail="Transaction was not saved"
            )

        return response.data[0]

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


class TransactionUpdate(BaseModel):
    amount: float | None = None
    type: str | None = None  # "credit" | "payment"


@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: str,
    update: TransactionUpdate,
    shopkeeper_id: str = Depends(get_current_shopkeeper_id),
):
    """Edit a past entry (e.g. fix a misheard amount or the wrong
    credit/payment type). Balance is always recomputed live from the
    transactions table, so editing a row here is all that's needed —
    no separate balance field to keep in sync.

    Ownership check: the transaction must belong (via its customer) to
    the signed-in shopkeeper, or this 404s instead of touching someone
    else's data. This is the fix for Shopkeeper A being able to edit
    Shopkeeper B's entries just by guessing/reusing a transaction_id."""
    owner_id = _transaction_owner_shopkeeper_id(transaction_id)
    if owner_id is None or owner_id != shopkeeper_id:
        raise HTTPException(status_code=404, detail="Transaction not found")

    changes = {}

    if update.amount is not None:
        if update.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")
        changes["amount"] = float(update.amount)

    if update.type is not None:
        if update.type not in ("credit", "payment"):
            raise HTTPException(status_code=400, detail="Type must be 'credit' or 'payment'")
        changes["type"] = update.type

    if not changes:
        raise HTTPException(status_code=400, detail="Nothing to update")

    try:
        response = (
            supabase
            .table("transactions")
            .update(changes)
            .eq("id", transaction_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Transaction not found")

        return {"success": True, "transaction": response.data[0]}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: str,
    shopkeeper_id: str = Depends(get_current_shopkeeper_id),
):
    """Undo: remove a transaction (used right after a voice entry is
    auto-saved). Ownership check first — see update_transaction above for
    why this can't just trust the transaction_id."""
    owner_id = _transaction_owner_shopkeeper_id(transaction_id)
    if owner_id is None or owner_id != shopkeeper_id:
        raise HTTPException(status_code=404, detail="Transaction not found")

    try:
        response = (
            supabase
            .table("transactions")
            .delete()
            .eq("id", transaction_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found"
            )

        return {"success": True, "deleted_id": transaction_id}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/customers/{customer_id}/ledger")
async def get_ledger(
    customer_id: str,
    shopkeeper_id: str = Depends(get_current_shopkeeper_id),
):
    """A single customer's entries. shopkeeper_id now comes exclusively
    from the authenticated session (never a query param a client could
    set to any value) and is checked against the customer's own
    shopkeeper_id first, so one shopkeeper can never pull another
    shopkeeper's customer ledger by guessing/reusing a customer_id — the
    same isolation guarantee dashboard/summary already has, applied here
    too."""
    try:
        owner_check = (
            supabase
            .table("customers")
            .select("id")
            .eq("id", customer_id)
            .eq("shopkeeper_id", shopkeeper_id)
            .limit(1)
            .execute()
        )
        if not owner_check.data:
            raise HTTPException(status_code=404, detail="Customer not found")

        response = (
            supabase
            .table("transactions")
            .select("*")
            .eq("customer_id", customer_id)
            .order("date", desc=True)
            .execute()
        )

        return {
            "customer_id": customer_id,
            "transactions": response.data
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
@router.post("/customers")
async def create_customer(
    name: str,
    phone: str | None = None,
    shopkeeper_id: str = Depends(get_current_shopkeeper_id),
):
    try:
        # Check if customer already exists
        existing = (
            supabase
            .table("customers")
            .select("id, name, phone, shopkeeper_id")
            .eq("shopkeeper_id", shopkeeper_id)
            .eq("name", name)
            .limit(1)
            .execute()
        )

        if existing.data:
            return {
                "success": True,
                "message": "Customer already exists",
                "customer": existing.data[0]
            }

        # Create new customer
        response = (
            supabase
            .table("customers")
            .insert({
                "shopkeeper_id": shopkeeper_id,
                "name": name,
                "phone": phone
            })
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=500,
                detail="Customer was not created"
            )

        return {
            "success": True,
            "message": "Customer created",
            "customer": response.data[0]
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/customers/name/{customer_name}")
async def get_customer_by_name(
    customer_name: str,
    shopkeeper_id: str = Depends(get_current_shopkeeper_id),
):
    """Look up one of the signed-in shopkeeper's own customers by name.
    shopkeeper_id now comes from the authenticated session, not the URL —
    the old /customers/{shopkeeper_id}/name/{name} shape let any caller
    pass any shopkeeper_id and read that shopkeeper's customer."""
    try:
        response = (
            supabase
            .table("customers")
            .select("id, name, phone, shopkeeper_id")
            .eq("shopkeeper_id", shopkeeper_id)
            .eq("name", customer_name)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail=f"Customer '{customer_name}' not found"
            )

        return {
            "success": True,
            "customer": response.data[0]
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


class ProcessTransactionRequest(BaseModel):
    text: str
    language: str = "en"


@router.post("/process-transaction")
async def process_transaction(
    request: ProcessTransactionRequest,
    shopkeeper_id: str = Depends(get_current_shopkeeper_id),
):
    try:
        # 1. Extract transaction from text
        transaction = extract_transaction(
            request.text,
            request.language
        )

        customer_name = transaction.get("customer")
        amount = transaction.get("amount")
        transaction_type = transaction.get("type")
        transaction_date = transaction.get("date")
        language = transaction.get("language")

        if not customer_name:
            raise HTTPException(
                status_code=400,
                detail="Customer could not be identified"
            )

        if amount is None:
            raise HTTPException(
                status_code=400,
                detail="Amount could not be identified"
            )

        if not transaction_type:
            raise HTTPException(
                status_code=400,
                detail="Transaction type could not be identified"
            )

        # 2. Find customer for this shopkeeper — matched by canonical
        #    identity so "Shreya" / "shreya" / "SHREYA" / "श्रेया" all
        #    resolve to the same customer instead of creating duplicates.
        customer = _find_customer_by_name(shopkeeper_id, customer_name)
        customer_created = customer is None

        # 3. If customer doesn't exist, create one
        if customer is None:
            create_response = _insert_customer(
                shopkeeper_id, display_name(customer_name)
            )

            if not create_response.data:
                raise HTTPException(
                    status_code=500,
                    detail="Customer could not be created"
                )

            customer = create_response.data[0]

        customer_id = customer["id"]

        # 4. Duplicate-save guard: if the exact same (customer, amount,
        #    type, sentence) was saved moments ago, this is almost
        #    certainly an accidental double-submit (flaky network retry,
        #    or the mic picking up one utterance as two segments) rather
        #    than a genuine second transaction — return the existing row
        #    instead of inserting another one.
        recent_cutoff = (
            datetime.now(timezone.utc).timestamp() - DUPLICATE_SAVE_WINDOW_SECONDS
        )
        recent_response = (
            supabase
            .table("transactions")
            .select("*")
            .eq("customer_id", customer_id)
            .eq("amount", amount)
            .eq("type", transaction_type)
            .eq("raw_text", request.text)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if recent_response.data:
            candidate = recent_response.data[0]
            created_at = candidate.get("created_at")
            if created_at:
                created_ts = datetime.fromisoformat(
                    str(created_at).replace("Z", "+00:00")
                ).timestamp()
                if created_ts >= recent_cutoff:
                    return {
                        "success": True,
                        "customer_created": customer_created,
                        "customer": customer,
                        "transaction": candidate,
                        "duplicate_ignored": True,
                    }

        # 5. Save transaction — only reported as success once Supabase
        #    actually confirms the insert (checked below), never before.
        transaction_response = (
            supabase
            .table("transactions")
            .insert({
                "customer_id": customer_id,
                "amount": amount,
                "type": transaction_type,
                "date": transaction_date,
                "raw_text": request.text,
                "language": language
            })
            .execute()
        )

        if not transaction_response.data:
            raise HTTPException(
                status_code=500,
                detail="Transaction could not be saved"
            )

        saved_transaction = transaction_response.data[0]

        return {
            "success": True,
            "customer_created": customer_created,
            "customer": customer,
            "transaction": saved_transaction
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )