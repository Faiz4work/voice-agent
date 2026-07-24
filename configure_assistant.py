"""One-shot configuration of the Vapi assistant.

Keeps the assistant definition in version control instead of hand-edited in a
dashboard: system prompt (prompt.md), tool JSON schemas, voice, transcriber
and the server URL are all applied from this repo in a single API call.

Usage:
    set VAPI_API_KEY=...            # PowerShell:  $env:VAPI_API_KEY="..."
    python configure_assistant.py

Optional overrides:
    VAPI_ASSISTANT_ID   which assistant to update
    SERVER_URL          public base URL of this backend
"""
import json
import os
import re
import sys

import httpx

ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "60f2a788-a8e6-4271-bf17-05c03ef34dee")
SERVER_URL = os.getenv(
    "SERVER_URL", "https://voice-agent-production-23aa.up.railway.app"
)
API = f"https://api.vapi.ai/assistant/{ASSISTANT_ID}"

FIRST_MESSAGE = (
    "Thanks for calling CareCloud Medical, this is Riley. I can get you "
    "registered as a new patient — can I start with your first and last name?"
)


def load_system_prompt() -> str:
    """Pull the prompt out of the ```text fenced block in prompt.md."""
    md = open("prompt.md", encoding="utf-8").read()
    match = re.search(r"```text\n(.*?)```", md, re.DOTALL)
    if not match:
        sys.exit("Could not find the ```text block in prompt.md")
    return match.group(1).strip()


def load_tools() -> list[dict]:
    """Reuse the tool schemas already defined in vapi_assistant.json."""
    cfg = json.load(open("vapi_assistant.json", encoding="utf-8"))
    return cfg["model"]["tools"]


def main() -> None:
    key = os.getenv("VAPI_API_KEY")
    if not key:
        sys.exit("Set VAPI_API_KEY first (Vapi dashboard > Settings > API Keys).")

    payload = {
        "name": "Riley — CareCloud Patient Registration",
        "firstMessage": FIRST_MESSAGE,
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.5,
            "messages": [{"role": "system", "content": load_system_prompt()}],
            "tools": load_tools(),
        },
        "voice": {"provider": "vapi", "voiceId": "Elliot"},
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en",
            "numerals": True,
        },
        "server": {"url": f"{SERVER_URL}/webhook"},
        "serverMessages": ["tool-calls", "end-of-call-report", "status-update"],
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 900,
        "endCallFunctionEnabled": True,
    }

    resp = httpx.patch(
        API,
        json=payload,
        headers={"Authorization": f"Bearer {key}"},
        timeout=30,
    )
    if resp.status_code >= 300:
        print(f"FAILED {resp.status_code}:\n{resp.text}")
        sys.exit(1)

    data = resp.json()
    tools = data.get("model", {}).get("tools", [])
    print("Assistant configured.")
    print("  name       :", data.get("name"))
    print("  model      :", data.get("model", {}).get("model"))
    print("  server url :", (data.get("server") or {}).get("url"))
    print("  tools      :", [t["function"]["name"] for t in tools])
    print("  prompt     :", len(load_system_prompt()), "chars")


if __name__ == "__main__":
    main()
