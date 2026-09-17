from pydantic import BaseModel
from datetime import date
from typing import Literal

class Transaction(BaseModel):
    customer: str
    amount: float
    type: Literal[`"credit`", `"payment`"]
    date: date
    language: Literal[`"hi`", `"en`"]
