"""
Custom-LLM endpoint for Vapi.

When the Vapi assistant's model provider is 'custom-llm', Vapi POSTs an
OpenAI-format chat-completion request to `<server>/chat/completions` and
expects an OpenAI-compatible (optionally streaming) response back.

This lets us own the prompt, inject context, log turns, etc. — while still
using GPT-4o-mini under the hood. Tool CALLS still surface as normal
OpenAI tool_calls; Vapi then executes them via /webhook (see main.py).
"""
import json
import logging
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

log = logging.getLogger("voice-agent.llm")

router = APIRouter()

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# ============================  TASK-SPECIFIC  ==========================
# Extra system context injected on every turn. At 9 PM, paste the real
# scenario rules here (or leave the prompt in the Vapi assistant config).
SYSTEM_PREAMBLE = (
    "You are a professional, friendly voice assistant for CareCloud. "
    "Keep replies short and natural for speech. Confirm details before "
    "taking any action."
)
# ======================================================================


@router.post("/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible proxy Vapi calls as its custom LLM."""
    body = await request.json()
    messages = body.get("messages", [])

    # Inject our system preamble if the caller didn't already lead with one.
    if not messages or messages[0].get("role") != "system":
        messages = [{"role": "system", "content": SYSTEM_PREAMBLE}] + messages
    else:
        messages[0]["content"] = SYSTEM_PREAMBLE + "\n\n" + messages[0]["content"]

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": body.get("temperature", 0.4),
        "stream": body.get("stream", True),
    }
    # Pass through tools/tool_choice if Vapi supplied them.
    for key in ("tools", "tool_choice", "max_tokens"):
        if key in body:
            payload[key] = body[key]

    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }

    if payload["stream"]:
        return StreamingResponse(
            _stream_openai(payload, headers),
            media_type="text/event-stream",
        )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(OPENAI_URL, json=payload, headers=headers)
        return resp.json()


async def _stream_openai(payload, headers):
    """Relay OpenAI's SSE stream straight through to Vapi."""
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST", OPENAI_URL, json=payload, headers=headers
        ) as resp:
            if resp.status_code != 200:
                text = await resp.aread()
                log.error("OpenAI error %s: %s", resp.status_code, text)
                err = {"error": {"message": text.decode(errors="ignore")}}
                yield f"data: {json.dumps(err)}\n\n"
                yield "data: [DONE]\n\n"
                return
            async for line in resp.aiter_lines():
                if line:
                    yield line + "\n"
