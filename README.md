# CareCloud Voice AI Agent

FastAPI backend for a Vapi-powered voice agent. **Reusable skeleton** — the
call pipeline (webhook, tool routing, DB logging, deploy) is done; only the
`# TASK-SPECIFIC` slots are filled in at challenge start.

## Stack
- **Voice/Telephony:** Vapi (STT/TTS/turn-taking + phone number)
- **LLM:** OpenAI GPT-4o-mini
- **Backend:** Python / FastAPI
- **DB:** Supabase (Postgres)
- **Hosting:** Railway (ngrok fallback for local)

## Architecture
```
Caller ──phone──▶ Vapi ──HTTPS webhook──▶ FastAPI (/webhook)
                   ▲                          │
                   │   tool results           ▼
                   └──────────────────  tools.py ─▶ Supabase
```
Vapi sends every event (tool calls, transcripts, end-of-call report) to the
single `/webhook` URL. Tool calls are routed through `TOOL_REGISTRY` in
`tools.py`; results are returned to Vapi to be spoken back.

## Files
| File | Purpose |
|---|---|
| `main.py` | FastAPI app: `/webhook`, `/health`, tool-call routing |
| `tools.py` | Tool handlers + `TOOL_REGISTRY`  ← **TASK-SPECIFIC** |
| `db.py` | Supabase client (no-op if unconfigured) |
| `vapi_assistant.json` | Assistant config template ← **TASK-SPECIFIC** |
| `schema.sql` | Supabase tables |
| `railway.json` / `Procfile` | Deploy config |

## Local run
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env      # then fill it in
python main.py              # http://localhost:8000/health
```

Expose locally for Vapi:
```bash
ngrok http 8000
# put https://xxxx.ngrok.app/webhook into the Vapi assistant's Server URL
```

## Deploy (Railway)
1. Push this repo to GitHub.
2. Railway → New Project → Deploy from GitHub repo.
3. Add env vars (`SUPABASE_URL`, `SUPABASE_KEY`, etc.) in Railway → Variables.
4. Copy the public URL → set it (+`/webhook`) as the Vapi Server URL.
5. Verify: open `https://<railway-url>/health` → `{"status":"ok"}`.

## At 9 PM — the ~20% that's left
1. Paste the real scenario into the system prompt (`vapi_assistant.json`).
2. Write the 1–3 tools they ask for in `tools.py` + register them.
3. Add matching tool schemas to the assistant config.
4. `git push` → Railway auto-deploys.
5. Call the Vapi number and test.
