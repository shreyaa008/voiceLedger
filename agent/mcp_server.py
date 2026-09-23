"""
Model Context Protocol (MCP) Server for VoiceLedger — ASK, READ-ONLY.

ASK must never modify Supabase. Every tool registered here only reads
data. There is no save/create/update/delete tool wired in — see
WRITE_TOOL_NAMES below for a hard, explicit refusal if one is ever added
to TOOL_REGISTRY by mistake.

shopkeeper_id is never something the model fills in. It is injected by
call_tool() from the trusted server-side session (the WebSocket
connection's query param in routers/voice_live.py, or the authenticated
request body in routers/agent.py) and overwrites anything the model might
have put in its own tool-call arguments — so a customer name spoken over
voice can never be used to reach into another shopkeeper's data.
"""

from agent.tools.get_customer_ledger import get_customer_ledger
from agent.tools.check_risk import check_risk
from agent.tools.generate_reminder import generate_reminder
from agent.tools.get_business_summary import get_business_summary
from agent.tools.get_current_datetime import get_current_datetime

# MCP Tool Specifications (Standard JSON Schema format).
# NOTE: shopkeeper_id is deliberately NOT a property here — it must never
# be something the model can choose or the transcript can influence.
TOOLS = [
    {
        "name": "get_customer_ledger",
        "description": (
            "Fetch one customer's outstanding balance and full transaction "
            "history, for the shopkeeper asking. Read-only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "The name of the customer (e.g., 'Ramesh', 'Suresh')."
                }
            },
            "required": ["customer_name"]
        }
    },
    {
        "name": "check_risk",
        "description": "Calculate credit risk score (0-100) and level (GREEN, YELLOW, RED) for a customer. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "The name of the customer to assess risk for."
                }
            },
            "required": ["customer_name"]
        }
    },
    {
        "name": "generate_reminder",
        "description": (
            "Compose a payment reminder message in Hindi or English for the shopkeeper "
            "to read out or send themselves. Read-only — does not send anything, "
            "does not write to the database."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Name of the customer."},
                "tone": {
                    "type": "string",
                    "enum": ["polite", "standard", "firm"],
                    "description": "Tone of the reminder message."
                },
                "language": {
                    "type": "string",
                    "enum": ["hi", "en"],
                    "description": "Language for the reminder ('hi' for Hindi, 'en' for English)."
                }
            },
            "required": ["customer_name"]
        }
    },
    {
        "name": "get_business_summary",
        "description": (
            "Deterministic totals for the shopkeeper's whole business: total number of "
            "transactions, total credit given, total payments received, total receivable "
            "(money customers owe — 'paise lene hain'), total payable (money owed back to "
            "customers — 'paise dene hain'), and every customer's balance. Use this for any "
            "aggregate/whole-business question instead of adding up individual lookups "
            "yourself — the numbers are pre-computed, not estimated."
        ),
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_current_datetime",
        "description": (
            "The real current date, day of week and time in India (Asia/Kolkata). "
            "Always call this for any question about today's date or day — never guess it."
        ),
        "inputSchema": {"type": "object", "properties": {}}
    },
]

# Tool registry mapping tool names to python functions.
TOOL_REGISTRY = {
    "get_customer_ledger": get_customer_ledger,
    "check_risk": check_risk,
    "generate_reminder": generate_reminder,
    "get_business_summary": get_business_summary,
    "get_current_datetime": get_current_datetime,
}

# Tools that need to be scoped to the asking shopkeeper. call_tool()
# injects shopkeeper_id for these and refuses to run them without one.
SHOPKEEPER_SCOPED_TOOLS = {
    "get_customer_ledger",
    "check_risk",
    "generate_reminder",
    "get_business_summary",
}

# Defense in depth: ASK is read-only. If a save/update/delete tool is ever
# added to TOOL_REGISTRY again (by name), call_tool refuses it outright,
# regardless of what TOOL_REGISTRY contains — this check does not rely on
# anyone remembering to keep the registry clean.
WRITE_TOOL_NAMES = {
    "save_transaction", "create_transaction", "update_transaction", "delete_transaction",
    "create_customer", "update_customer", "delete_customer", "merge_customer",
}


def list_tools() -> list:
    """Return list of available MCP tool definitions (read-only tools only)."""
    return TOOLS


def call_tool(tool_name: str, arguments: dict = None, shopkeeper_id: str = None) -> dict:
    """Invoke a read-only tool by name. shopkeeper_id always comes from the
    trusted caller (never the model) and is injected here, overwriting
    anything already in `arguments`."""
    arguments = dict(arguments or {})

    if tool_name in WRITE_TOOL_NAMES:
        return {"error": f"Tool '{tool_name}' is a write operation and is disabled for Ask (read-only)."}

    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool '{tool_name}' is not registered in MCP server."}

    if tool_name in SHOPKEEPER_SCOPED_TOOLS:
        arguments["shopkeeper_id"] = shopkeeper_id  # overwrite; never trust the model's own value
        if not shopkeeper_id:
            return {"error": "No shopkeeper session — cannot look up data."}

    handler = TOOL_REGISTRY[tool_name]
    try:
        return handler(**arguments)
    except Exception as e:
        return {
            "error": f"Error executing tool '{tool_name}': {str(e)}"
        }


if __name__ == "__main__":
    print(f"MCP Server initialized with {len(TOOLS)} tools (all read-only):")
    for t in list_tools():
        print(f" - {t['name']}: {t['description']}")

    # Quick sanity test (no real shopkeeper_id, so this is expected to
    # return found=False rather than raise — it's just checking the
    # registry wiring works, not real data).
    test_result = call_tool("get_customer_ledger", {"customer_name": "Ramesh"}, shopkeeper_id="test-shopkeeper-id")
    print(f"\nTest invocation (get_customer_ledger for Ramesh):\n{test_result}")