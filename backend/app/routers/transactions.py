from fastapi import APIRouter

router = APIRouter()


@router.post("/transactions")
async def save_transaction():
    # TODO: save confirmed transaction to Supabase
    return {
        "status": "saved"
    }


@router.get("/customers/{customer_id}/ledger")
async def get_ledger(customer_id: str):
    # TODO: fetch all transactions for this customer
    return {
        "customer_id": customer_id,
        "transactions": []
    }