"""
FastAPI Router for VoiceLedger AI Agent (POST /ask)
Connects user questions to the AI Agent and MCP tool loop.
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
    language: Optional[str] = "hi"


def extract_customer_name(question: str) -> Optional[str]:
    """Extract customer name from common Hindi and English questions."""
    # Pattern 1: Hindi/Hinglish "X ka kitna baaki", "X ko reminder", "X ka risk"
    hindi_match = re.search(r'([A-Za-z\u0900-\u097F]+)\s+(?:ka|ki|ke|ko|se)\b', question, re.IGNORECASE)
    if hindi_match:
        cand = hindi_match.group(1).strip()
        stop_words = ["sabse", "is", "mera", "kiska", "aaj", "kal", "kul"]
        if cand.lower() not in stop_words:
            return cand

    # Pattern 2: English "does X owe", "risk for X", "reminder for X"
    eng_match = re.search(r'(?:for|about|does|to)\s+([A-Za-z]+)', question, re.IGNORECASE)
    if eng_match:
        return eng_match.group(1).strip()

    # Pattern 3: Simple word lookup
    words = [w for w in re.findall(r'\b[A-Za-z]{3,}\b', question) if w.lower() not in [
        "how", "much", "does", "what", "check", "risk", "tell", "send", "give", "show",
        "ledger", "balance", "udhaar", "baaki", "kitna", "hai", "karo", "bhejo", "batao"
    ]]
    return words[0] if words else None


def process_agent_query(question: str, language: str = "hi") -> dict:
    """Process shopkeeper question with Foundry Agent or fallback MCP tool dispatcher."""
    # 1. Try running through Microsoft Foundry / Azure OpenAI if credentials exist
    foundry_res = run_foundry_agent(question, language)
    if foundry_res is not None:
        return foundry_res

    q_lower = question.lower()
    is_hindi = (language == "hi") or any(w in q_lower for w in ["ka", "ki", "hai", "kitna", "baaki", "kiska", "udhaar", "bhejo", "batao"])
    
    cust_name = extract_customer_name(question)


    # 1. Aggregate Queries (e.g. "sabse zyada udhaar")
    if any(w in q_lower for w in ["sabse zyada", "highest", "top", "total", "sabse bada"]):
        data = call_tool("search_transactions", {})
        top = data.get("top_debtor", {})
        top_name = top.get("customer", "None")
        top_bal = top.get("balance_rupees", 0.0)
        
        if top_name != "None" and top_bal > 0:
            answer = f"Sabse zyada udhaar {top_name} ka hai (₹{int(top_bal)})." if is_hindi else f"{top_name} has the highest outstanding balance of ₹{int(top_bal)}."
        else:
            answer = "Filhal kisi customer ka udhaar baaki nahi hai." if is_hindi else "No customer currently has an outstanding balance."
        return {"answer": answer, "tool_called": "search_transactions", "data": data}


    # 2. Risk Check Queries
    if any(w in q_lower for w in ["risk", "safe", "khatra"]):
        target_name = cust_name or "Ramesh"
        data = call_tool("check_risk", {"customer_name": target_name})
        if data.get("risk_level") == "UNKNOWN":
            answer = f"Is naam ({target_name}) ka koi record nahi mila." if is_hindi else f"No customer record found for {target_name}."
        else:
            level = data.get("risk_level", "GREEN")
            score = data.get("score", 0)
            answer = f"{target_name} ka risk level {level} hai (Score: {score}/100)." if is_hindi else f"{target_name}'s credit risk level is {level} with a score of {score}/100."
        return {"answer": answer, "tool_called": "check_risk", "data": data}

    # 3. Reminder Generation Queries
    if any(w in q_lower for w in ["reminder", "message", "whatsapp", "bhejo"]):
        target_name = cust_name or "Ramesh"
        tone = "firm" if any(w in q_lower for w in ["firm", "strict", "sakht"]) else "polite"
        lang_code = "hi" if is_hindi else "en"
        data = call_tool("generate_reminder", {"customer_name": target_name, "tone": tone, "language": lang_code})
        answer = data.get("reminder_text", "Reminder generated.")
        return {"answer": answer, "tool_called": "generate_reminder", "data": data}

    # 4. Single Customer Ledger / Balance Queries (Default)
    target_name = cust_name or "Ramesh"
    ledger = call_tool("get_customer_ledger", {"customer_name": target_name})
    
    if not ledger.get("found"):
        answer = f"Is naam ({target_name}) ka koi record nahi mila." if is_hindi else f"No customer record found for {target_name}."
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
    """Handle shopkeeper voice/text question via Agent and MCP tools."""
    return process_agent_query(payload.question, payload.language or "hi")