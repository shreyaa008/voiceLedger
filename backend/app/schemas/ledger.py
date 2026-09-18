from pydantic import BaseModel

from .transaction import TransactionResponse


class Ledger(BaseModel):
    customer_id: str
    transactions: list[TransactionResponse]