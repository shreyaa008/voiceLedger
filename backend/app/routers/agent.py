"""
FastAPI Router for VoiceLedger AI Agent (POST /ask) — READ-ONLY.

Connects a shopkeeper's question to the AI Agent and the read-only MCP
tool loop (agent/mcp_server.py). shopkeeper_id is required on every
request and is passed straight through to every tool call, so this
endpoint can never answer with, or act on, another shopkeeper's data.
"""

import re
import sys
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

# Ensure project root is in sys.path when running from backend directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.mcp_server import call_tool
from agent.agent_config import run_foundry_agent

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    shopkeeper_id: str  # required — Ask must always be scoped to one shopkeeper
    language: Optional[str] = "hi"


def extract_customer_name(question: str) -> Optional[str]:
    """Extract customer name from common Hindi and English questions."""
    hindi_match = re.search(r'([A-Za-z\u0900-\u097F]+)\s+(?:ka|ki|ke|ko|se)\b', question, re.IGNORECASE)
    if hindi_match:
        cand = hindi_match.group(1).strip()
        stop_words = ["sabse", "is", "mera", "kiska", "aaj", "kal", "kul", "kis", "kaun"]
        if cand.lower() not in stop_words:
            return cand

    eng_match = re.search(r'(?:for|about|does|to)\s+([A-Za-z]+)', question, re.IGNORECASE)
    if eng_match:
        return eng_match.group(1).strip()

    words = [w for w in re.findall(r'\b[A-Za-z]{3,}\b', question) if w.lower() not in [
        "how", "much", "does", "what", "check", "risk", "tell", "send", "give", "show",
        "ledger", "balance", "udhaar", "baaki", "kitna", "hai", "karo", "bhejo", "batao",
        "total", "all", "today", "date", "day",
    ]]
    return words[0] if words else None


def _clarify(is_hindi: bool) -> dict:
    """Used whenever a question needs a customer name and none could be
    found — asks which customer, instead of silently guessing one."""
    answer = "Kis customer ke baare mein? Naam bataiye." if is_hindi else "Which customer do you mean? Please tell me the name."
    return {"answer": answer, "tool_called": None, "data": None}


def process_agent_query(question: str, language: str, shopkeeper_id: str) -> dict:
    """Process a shopkeeper's question with the Foundry Agent, or the
    read-only fallback dispatcher if no LLM credentials are configured."""
    # 1. Try running through Microsoft Foundry / Azure OpenAI if credentials exist
    foundry_res = run_foundry_agent(question, language, shopkeeper_id=shopkeeper_id)
    if foundry_res is not None:
        return foundry_res

    q_lower = question.lower()
    is_hindi = (language == "hi") or any(w in q_lower for w in ["ka", "ki", "hai", "kitna", "baaki", "kiska", "udhaar", "bhejo", "batao"])

    # 2. Current date/time — never guessed.
    if any(w in q_lower for w in [
        "aaj ki date", "aaj kaunsa din", "aaj ka din", "today's date", "what day",
        "current date", "current time", "abhi ka time", "kya din hai",
    ]):
        data = call_tool("get_current_datetime", {}, shopkeeper_id=shopkeeper_id)
        if is_hindi:
            answer = f"Aaj {data['date_readable']} hai ({data['day_of_week']})."
        else:
            answer = f"Today is {data['date_readable']} ({data['day_of_week']})."
        return {"answer": answer, "tool_called": "get_current_datetime", "data": data}

    # 3. Total transaction count.
    if any(w in q_lower for w in ["kitne transactions", "total transactions", "how many transactions", "transaction count", "kul transactions"]):
        data = call_tool("get_business_summary", {}, shopkeeper_id=shopkeeper_id)
        count = data.get("total_transaction_count", 0)
        answer = f"Total {count} transactions hue hain." if is_hindi else f"There have been a total of {count} transactions."
        return {"answer": answer, "tool_called": "get_business_summary", "data": data}

    # 4. Customer-wise outstanding list ("kis kis se paise lene hain") —
    #    checked BEFORE the generic total-receivable branch below, since
    #    this phrase also contains "lene hain" and is more specific.
    if any(w in q_lower for w in ["kis kis se", "kaun kaun", "which customers owe", "who owes"]):
        data = call_tool("get_business_summary", {}, shopkeeper_id=shopkeeper_id)
        owing = [b for b in data.get("customer_balances", []) if b["status"] == "receivable"]
        if not owing:
            answer = "Filhal kisi se bhi paise lene nahi hain." if is_hindi else "There's currently no one who owes you money."
        else:
            listing = ", ".join(f"{b['customer']} (₹{int(b['balance'])})" for b in owing[:8])
            answer = f"Inse paise lene hain: {listing}." if is_hindi else f"You need to collect money from: {listing}."
        return {"answer": answer, "tool_called": "get_business_summary", "data": data}

    # 5. Total receivable ("paise lene hain").
    if any(w in q_lower for w in ["lene hain", "lena hai", "kitna lena", "total receivable", "mujhe kitne paise"]) and "dene" not in q_lower:
        data = call_tool("get_business_summary", {}, shopkeeper_id=shopkeeper_id)
        amt = data.get("total_receivable", 0.0)
        answer = f"Aapko total ₹{int(amt)} lene hain." if is_hindi else f"You have a total of ₹{int(amt)} receivable."
        return {"answer": answer, "tool_called": "get_business_summary", "data": data}

    # 6. Total payable ("paise dene hain").
    if any(w in q_lower for w in ["dene hain", "dena hai", "kitna dena", "total payable"]):
        data = call_tool("get_business_summary", {}, shopkeeper_id=shopkeeper_id)
        amt = data.get("total_payable", 0.0)
        answer = f"Aapko total ₹{int(amt)} dene hain." if is_hindi else f"You owe a total of ₹{int(amt)} to customers."
        return {"answer": answer, "tool_called": "get_business_summary", "data": data}

    cust_name = extract_customer_name(question)

    # 7. Top debtor ("sabse zyada udhaar").
    if any(w in q_lower for w in ["sabse zyada", "highest", "top", "sabse bada"]):
        data = call_tool("get_business_summary", {}, shopkeeper_id=shopkeeper_id)
        balances = data.get("customer_balances", [])
        top = balances[0] if balances and balances[0]["balance"] > 0 else None
        if top:
            answer = f"Sabse zyada udhaar {top['customer']} ka hai (₹{int(top['balance'])})." if is_hindi else f"{top['customer']} has the highest outstanding balance of ₹{int(top['balance'])}."
        else:
            answer = "Filhal kisi customer ka udhaar baaki nahi hai." if is_hindi else "No customer currently has an outstanding balance."
        return {"answer": answer, "tool_called": "get_business_summary", "data": data}

    # 8. Risk check.
    if any(w in q_lower for w in ["risk", "safe", "khatra"]):
        if not cust_name:
            return _clarify(is_hindi)
        data = call_tool("check_risk", {"customer_name": cust_name}, shopkeeper_id=shopkeeper_id)
        if not data.get("found"):
            answer = f"Is naam ({cust_name}) ka koi record nahi mila." if is_hindi else f"No customer record found for {cust_name}."
        else:
            level, score = data.get("risk_level", "GREEN"), data.get("score", 0)
            answer = f"{data['customer']} ka risk level {level} hai (Score: {score}/100)." if is_hindi else f"{data['customer']}'s credit risk level is {level} with a score of {score}/100."
        return {"answer": answer, "tool_called": "check_risk", "data": data}

    # 9. Reminder generation.
    if any(w in q_lower for w in ["reminder", "message", "whatsapp", "bhejo"]):
        if not cust_name:
            return _clarify(is_hindi)
        tone = "firm" if any(w in q_lower for w in ["firm", "strict", "sakht"]) else "polite"
        lang_code = "hi" if is_hindi else "en"
        data = call_tool("generate_reminder", {"customer_name": cust_name, "tone": tone, "language": lang_code}, shopkeeper_id=shopkeeper_id)
        answer = data.get("reminder_text", "Reminder generated.")
        return {"answer": answer, "tool_called": "generate_reminder", "data": data}

    # 10. Single customer ledger / balance / full history (default).
    if not cust_name:
        return _clarify(is_hindi)

    ledger = call_tool("get_customer_ledger", {"customer_name": cust_name}, shopkeeper_id=shopkeeper_id)

    if not ledger.get("found"):
        answer = f"Is naam ({cust_name}) ka koi record nahi mila." if is_hindi else f"No customer record found for {cust_name}."
        return {"answer": answer, "tool_called": "get_customer_ledger", "data": ledger}

    if any(w in q_lower for w in ["saare transactions", "saari transactions", "all transactions", "transaction history", "poora hisaab"]):
        entries = ledger.get("transactions", [])
        if not entries:
            answer = f"{ledger['customer']} ka koi transaction nahi mila." if is_hindi else f"{ledger['customer']} has no transactions."
        else:
            parts = [f"{'udhaar' if t['type']=='credit' else 'payment'} ₹{int(t['amount'])}" for t in entries[:8]]
            answer = f"{ledger['customer']} ke transactions: " + ", ".join(parts) + "." if is_hindi else f"{ledger['customer']}'s transactions: " + ", ".join(parts) + "."
        return {"answer": answer, "tool_called": "get_customer_ledger", "data": ledger}

    balance = ledger.get("net_balance", 0.0)
    if is_hindi:
        if balance > 0:
            answer = f"{ledger['customer']} ka kul baaki udhaar ₹{int(balance)} hai."
        elif balance == 0:
            answer = f"{ledger['customer']} ka koi udhaar baaki nahi hai. Hisaab barabar hai."
        else:
            answer = f"{ledger['customer']} ka ₹{int(abs(balance))} jama hai."
    else:
        if balance > 0:
            answer = f"{ledger['customer']}'s outstanding balance is ₹{int(balance)}."
        elif balance == 0:
            answer = f"{ledger['customer']} has zero outstanding balance. All cleared."
        else:
            answer = f"{ledger['customer']} has an advance credit of ₹{int(abs(balance))}."

    return {"answer": answer, "tool_called": "get_customer_ledger", "data": ledger}


@router.post("/ask")
async def ask(payload: AskRequest):
    """Handle a shopkeeper's voice/text question via the Agent and
    read-only MCP tools, scoped to their own data."""
    return process_agent_query(payload.question, payload.language or "hi", payload.shopkeeper_id)