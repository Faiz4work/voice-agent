"""
Voice AI Agent — FastAPI backend for Vapi webhooks & tool calls.

This is the REUSABLE SKELETON. It handles everything that is the same for
every voice-agent task: the Vapi server URL webhook, tool-call routing,
call logging, and health checks.

At challenge start time you only touch the areas marked  # TASK-SPECIFIC.
"""
import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from db import log_call_event, save_record
from llm import router as llm_router
from tools import TOOL_REGISTRY

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("voice-agent")

app = FastAPI(title="Voice AI Agent")

# Custom-LLM endpoint (/chat/completions) — Vapi calls this as its model.
app.include_router(llm_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Railway/uptime probe + quick 'is it live' check before the demo."""
    return {"status": "ok"}


@app.post("/webhook")
async def vapi_webhook(request: Request) -> JSONResponse:
    """
    Single Vapi 'Server URL'. Vapi POSTs every event here:
      - tool-calls / function-call  -> we run the tool and return its result
      - status-update, end-of-call-report, transcript -> we log them

    Vapi wraps everything in {"message": {...}}.
    """
    body = await request.json()
    message = body.get("message", body)
    msg_type = message.get("type")
    log.info("Vapi event: %s", msg_type)

    # --- Tool / function calls -------------------------------------------
    # Vapi has used both "tool-calls" (new) and "function-call" (legacy).
    if msg_type in ("tool-calls", "function-call"):
        return JSONResponse(await handle_tool_calls(message))

    # --- Everything else: just log it ------------------------------------
    if msg_type == "end-of-call-report":
        # Persist the full call summary — great to show the reviewer.
        call = message.get("call", {})
        save_record(
            "calls",
            {
                "call_id": call.get("id"),
                "phone_number": (message.get("customer") or {}).get("number"),
                "summary": message.get("summary"),
                "transcript": message.get("transcript"),
                "ended_reason": message.get("endedReason"),
            },
        )
    else:
        log_call_event(msg_type, message)

    return JSONResponse({"received": True})


async def handle_tool_calls(message: dict[str, Any]) -> dict[str, Any]:
    """
    Run each requested tool and return results in the shape Vapi expects:
      {"results": [{"toolCallId": "...", "result": "..."}]}
    """
    tool_calls = message.get("toolCalls") or message.get("toolCallList") or []

    # Legacy single function-call shape fallback.
    if not tool_calls and message.get("functionCall"):
        fc = message["functionCall"]
        tool_calls = [{"id": "legacy", "function": fc}]

    results = []
    for call in tool_calls:
        call_id = call.get("id")
        fn = call.get("function", {})
        name = fn.get("name")
        args = fn.get("arguments", {})
        if isinstance(args, str):
            import json
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        handler = TOOL_REGISTRY.get(name)
        if handler is None:
            log.warning("Unknown tool: %s", name)
            result = f"Error: no tool named {name}"
        else:
            try:
                result = handler(args)
            except Exception as exc:  # noqa: BLE001 - never 500 mid-call
                log.exception("Tool %s failed", name)
                result = f"Error running {name}: {exc}"

        results.append({"toolCallId": call_id, "result": result})

    return {"results": results}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
