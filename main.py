"""
Voice AI Agent — Patient Registration System.

FastAPI backend serving three concerns, deliberately separated:
  * /patients/*         — REST API over the patient records (api.py)
  * /webhook            — Vapi tool calls + call event logging (this file)
  * /chat/completions   — optional custom-LLM proxy (llm.py)

The voice agent and the REST API share ONE service layer (crud.py) and ONE
validation layer (schemas.py), so a patient registered by phone is validated
identically to one created over HTTP.
"""
import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api import router as patients_router
from llm import router as llm_router
from models import init_db
from tools import TOOL_REGISTRY

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("voice-agent")

app = FastAPI(
    title="Voice AI Agent — Patient Registration",
    description="Conversational patient intake over the phone, backed by a REST API.",
    version="1.0.0",
)

# Create tables on boot (idempotent).
init_db()

app.include_router(patients_router)
# Custom-LLM endpoint (/chat/completions) — used only if Vapi is configured
# with provider "custom-llm"; harmless otherwise.
app.include_router(llm_router)


# --- Consistent error envelope: {"data": null, "error": {...}} -------------
@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"data": None, "error": {"message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    """422 with field-level detail — the API validates independently of the agent."""
    return JSONResponse(
        status_code=422,
        content={
            "data": None,
            "error": {
                "message": "Validation failed",
                "fields": [
                    {"field": ".".join(str(p) for p in e["loc"][1:]), "reason": e["msg"]}
                    for e in exc.errors()
                ],
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"data": None, "error": {"message": "Internal server error"}},
    )


@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    """Simple status page so the base URL isn't a bare 404."""
    return """<!doctype html>
<html><head><meta charset="utf-8"><title>CareCloud Voice Agent</title>
<style>
  body{font-family:system-ui,sans-serif;background:#0b0f14;color:#e6edf3;
       display:flex;min-height:100vh;margin:0;align-items:center;justify-content:center}
  .card{max-width:520px;padding:2.5rem;border:1px solid #1f2933;border-radius:14px;
        background:#0f151c}
  h1{margin:0 0 .25rem;font-size:1.4rem}
  .dot{color:#3fb950}
  code{background:#161b22;padding:.15rem .4rem;border-radius:5px;color:#79c0ff}
  ul{line-height:1.9;padding-left:1.1rem} .muted{color:#8b949e;font-size:.9rem}
</style></head>
<body><div class="card">
  <h1>CareCloud Voice Agent <span class="dot">&#9679; live</span></h1>
  <p class="muted">Backend for a Vapi-powered voice AI agent. This is an API,
  not a web app &mdash; interact by <b>calling the agent</b>.</p>
  <ul>
    <li><code>GET /health</code> &mdash; liveness check</li>
    <li><code>POST /chat/completions</code> &mdash; custom LLM (GPT-4o-mini)</li>
    <li><code>POST /webhook</code> &mdash; tool calls &amp; call logging</li>
  </ul>
</div></body></html>"""


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

    # --- Observability: log the conversation outcome ---------------------
    if msg_type == "end-of-call-report":
        log.info(
            "CALL ENDED | id=%s from=%s reason=%s\nSUMMARY: %s\nTRANSCRIPT:\n%s",
            (message.get("call") or {}).get("id"),
            (message.get("customer") or {}).get("number"),
            message.get("endedReason"),
            message.get("summary"),
            message.get("transcript"),
        )

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
