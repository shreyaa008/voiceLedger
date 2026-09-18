"""
Configuration and Prompt Loader for VoiceLedger AI Agent.
"""

from pathlib import Path
from agent.mcp_server import list_tools, call_tool

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt.md"


def get_system_prompt() -> str:
    """Load the system prompt from markdown file."""
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return "You are VoiceLedger AI, a bookkeeping assistant. Never invent data."


def get_available_tools() -> list:
    """Return tools list registered on MCP server."""
    return list_tools()
