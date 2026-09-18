from datetime import date as Date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# Data extracted from the user's voice/text
# Used by /extract
class Transaction(BaseModel):
    customer: str
    amount: Decimal = Field(gt=0)
    type: Literal["credit", "payment"]
    date: Date
    language: Literal["hi", "en"]


# Data sent when saving a confirmed transaction
# Used by POST /transactions
class TransactionCreate(BaseModel):
    customer_id: str
    amount: Decimal = Field(gt=0)
    type: Literal["credit", "payment"]
    date: Date
    due_date: Date | None = None
    raw_text: str | None = None
    language: Literal["hi", "en"] | None = None


# Data returned from the database
class TransactionResponse(BaseModel):
    id: str
    customer_id: str
    amount: Decimal
    type: Literal["credit", "payment"]
    date: Date
    due_date: Date | None = None
    raw_text: str | None = None
    language: Literal["hi", "en"] | None = None