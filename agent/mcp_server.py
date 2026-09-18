"""
Model Context Protocol (MCP) Server for VoiceLedger
Exposes the 5 core bookkeeping tools to the AI Agent.
"""

from agent.tools.get_customer_ledger import get_customer_ledger
from agent.tools.check_risk import check_risk
from agent.tools.generate_reminder import generate_reminder
from agent.tools.search_transactions import search_transactions
from agent.tools.save_transaction import save_transaction

# MCP Tool Specifications (Standard JSON Schema format)
TOOLS = [
    {
        "name": "get_customer_ledger",
        "description": "Fetch customer outstanding balance and recent transaction history by customer name.",
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
        "description": "Calculate credit risk score (0-100) and risk level (GREEN, YELLOW, RED) for a customer.",
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
        "description": "Generate a personalized debt reminder message in Hindi or English with chosen tone.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Name of the customer."
                },
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
        "name": "search_transactions",
        "description": "Perform aggregate business analytics across transactions (e.g. top debtor, monthly total).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter_query": {
                    "type": "object",
                    "description": "Optional filter criteria such as sort_by, date_range, or transaction type."
                }
            }
        }
    },
    {
        "name": "save_transaction",
        "description": "Save a confirmed credit or payment transaction into the ledger.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Name of the customer."
                },
                "amount": {
                    "type": "number",
                    "description": "Transaction amount in Rupees."
                },
                "type": {
                    "type": "string",
                    "enum": ["credit", "payment"],
                    "description": "Type of transaction: 'credit' (udhaar given) or 'payment' (jama received)."
                },
                "date": {
                    "type": "string",
                    "description": "Date of transaction in YYYY-MM-DD format (optional)."
                }
            },
            "required": ["customer_name", "amount", "type"]
        }
    }
]

# Tool registry mapping tool names to python functions
TOOL_REGISTRY = {
    "get_customer_ledger": get_customer_ledger,
    "check_risk": check_risk,
    "generate_reminder": generate_reminder,
    "search_transactions": search_transactions,
    "save_transaction": save_transaction
}


def list_tools() -> list:
    """Return list of available MCP tool definitions."""
    return TOOLS


def call_tool(tool_name: str, arguments: dict = None) -> dict:
    """Invoke a tool by name with provided arguments."""
    arguments = arguments or {}
    if tool_name not in TOOL_REGISTRY:
        return {
            "error": f"Tool '{tool_name}' is not registered in MCP server."
        }

    handler = TOOL_REGISTRY[tool_name]
    try:
        return handler(**arguments)
    except Exception as e:
        return {
            "error": f"Error executing tool '{tool_name}': {str(e)}"
        }


if __name__ == "__main__":
    print(f"MCP Server initialized with {len(TOOLS)} tools:")
    for t in list_tools():
        print(f" - {t['name']}: {t['description']}")
    
    # Quick sanity test
    test_result = call_tool("get_customer_ledger", {"customer_name": "Ramesh"})
    print(f"\nTest invocation (get_customer_ledger for Ramesh):\n{test_result}")
