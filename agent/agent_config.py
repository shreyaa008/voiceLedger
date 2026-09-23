"""
Configuration, Foundry Agent Loader, and MCP Tool Bindings for VoiceLedger.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import AzureOpenAI

from agent.mcp_server import list_tools, call_tool

# Ensure environment variables are loaded
load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt.md"


def get_system_prompt() -> str:
    """Load the strict anti-hallucination system prompt."""
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return "You are VoiceLedger AI, a bookkeeping assistant. Never invent data. Always use Rupees."


def get_foundry_client():
    """Return initialized AI client (Azure OpenAI, GitHub Models, Groq, or OpenAI) if credentials exist."""
    # 1. Check for standard OpenAI / GitHub Models / Groq configuration
    openai_base = os.getenv("OPENAI_BASE_URL")
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_base or (openai_key and not openai_key.startswith("3zh")):
        try:
            from openai import OpenAI
            return OpenAI(
                base_url=openai_base or "https://models.inference.ai.azure.com",
                api_key=openai_key or os.getenv("GITHUB_TOKEN")
            )
        except Exception:
            pass

    # 2. Check for Azure OpenAI / Foundry configuration
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("FOUNDRY_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
    
    if endpoint and api_key:
        try:
            # Clean and normalize endpoint for AzureOpenAI client
            clean_endpoint = endpoint.strip().rstrip("/")
            if "/openai/v1" in clean_endpoint:
                clean_endpoint = clean_endpoint.replace("/openai/v1", "")
            elif "/api/projects" in clean_endpoint:
                clean_endpoint = clean_endpoint.split("/api/projects")[0]

            return AzureOpenAI(
                azure_endpoint=clean_endpoint,
                api_key=api_key,
                api_version="2024-06-01"
            )
        except Exception:
            return None
    return None



def get_tools_schema() -> list:
    """Convert MCP tools into standard tool-calling format for the agent."""
    mcp_tools = list_tools()
    openai_tools = []
    for t in mcp_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t.get("inputSchema", {"type": "object", "properties": {}})
            }
        })
    return openai_tools


def run_foundry_agent(question: str, language: str = "hi", shopkeeper_id: str = None) -> dict | None:
    """Execute query through Microsoft Foundry Agent with tool-calling loop.
    shopkeeper_id scopes every tool call to this shopkeeper's own data —
    it is never something the model chooses; it comes from the caller."""
    client = get_foundry_client()
    if not client:
        return None

    deployment_name = os.getenv("FOUNDRY_MODEL_DEPLOYMENT", "gpt-4o-mini")
    system_prompt = get_system_prompt()
    tools = get_tools_schema()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Language: {language}\nQuestion: {question}"}
    ]

    try:
        # 1. First model call to select tool
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=300
        )

        msg = response.choices[0].message
        
        # 2. If the model wants to call an MCP tool
        if msg.tool_calls:
            tool_call = msg.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments or "{}")

            print(f"\n[AZURE FOUNDRY] Model '{deployment_name}' decided to call MCP Tool: '{tool_name}'")
            print(f"[AZURE FOUNDRY] Extracted Arguments: {tool_args}")

            # Execute the tool via our MCP server — shopkeeper_id is injected
            # server-side inside call_tool(), not taken from tool_args.
            tool_output = call_tool(tool_name, tool_args, shopkeeper_id=shopkeeper_id)
            print(f"[MCP SERVER] Tool Output from DB: {tool_output}")

            messages.append(msg)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_output)
            })

            # 3. Second model call to generate grounded answer from tool output
            second_resp = client.chat.completions.create(
                model=deployment_name,
                messages=messages,
                max_tokens=300
            )
            answer = second_resp.choices[0].message.content
            print(f"[AZURE FOUNDRY] Final Synthesized Answer: {answer}\n")

            return {
                "answer": answer,
                "tool_called": tool_name,
                "data": tool_output
            }

        # If model answered directly without tools
        return {
            "answer": msg.content,
            "tool_called": None,
            "data": None
        }
    except Exception as e:
        # Fall back gracefully to direct dispatcher if cloud call encounters quota/network issues
        return None