from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
)
from app.services.azure_language import extract_transaction
from app.services.supabase_client import supabase


router = APIRouter()


@router.post(
    "/transactions",
    response_model=TransactionResponse
)
async def create_transaction(transaction: TransactionCreate):

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


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(transaction_id: str):
    """Undo: remove a transaction (used right after a voice entry is auto-saved)."""
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
async def get_ledger(customer_id: str):

    try:
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

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
@router.get("/customers/name/{customer_name}")
async def get_customer_by_name(customer_name: str):

    try:
        response = (
            supabase
            .table("customers")
            .select("id, name, phone, shopkeeper_id")
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
@router.post("/customers")
async def create_customer(
    shopkeeper_id: str,
    name: str,
    phone: str | None = None
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


@router.get("/customers/{shopkeeper_id}/name/{customer_name}")
async def get_customer_by_name(
    shopkeeper_id: str,
    customer_name: str
):
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
    shopkeeper_id: str


@router.post("/process-transaction")
async def process_transaction(
    request: ProcessTransactionRequest
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

        # 2. Find customer for this shopkeeper
        customer_response = (
            supabase
            .table("customers")
            .select("id, name, phone, shopkeeper_id")
            .eq("shopkeeper_id", request.shopkeeper_id)
            .eq("name", customer_name)
            .limit(1)
            .execute()
        )

        # 3. If customer doesn't exist, create one
        if customer_response.data:
            customer = customer_response.data[0]
            customer_created = False

        else:
            create_response = (
                supabase
                .table("customers")
                .insert({
                    "shopkeeper_id": request.shopkeeper_id,
                    "name": customer_name
                })
                .execute()
            )

            if not create_response.data:
                raise HTTPException(
                    status_code=500,
                    detail="Customer could not be created"
                )

            customer = create_response.data[0]
            customer_created = True

        customer_id = customer["id"]

        # 4. Save transaction
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