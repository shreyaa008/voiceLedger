from pydantic import BaseModel
from typing import List
from .transaction import Transaction

class Ledger(BaseModel):
    customer_id: str
    transactions: List[Transaction]
