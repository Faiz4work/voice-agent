# RUNBOOK — Challenge night (9 PM)

## How the reviewer tests it (deliverable)
Provide BOTH:
1. **Web call link (primary)** — Vapi assistant → share/embed link. Free,
   works globally, no dialing. Best for a reviewer outside the US.
2. **Twilio phone number (secondary)** — real +1 number, see setup below.

### Twilio number setup (one-time)
1. Sign up: https://www.twilio.com/try-twilio (free ~$15 trial credit).
2. Console dashboard → copy **Account SID** (AC…) + **Auth Token**.
3. Phone Numbers → Manage → Buy a number (US, Voice-capable) — free on trial.
4. Vapi → Create Phone Number → **Import Twilio** → paste number (E.164
   `+1…`), Account SID, Auth Token → Import.
- Trial caveat: inbound calls play a short "trial" notice (upgrade ~$20 to
  remove). International callers pay their own rates — hence web link is primary.
- Vapi "Free Vapi SIP" is NOT a dialable phone number — ignore it.

## Layout of what talks to what (CURRENT SETUP)
```
Caller ─phone─▶ Vapi ──(built-in GPT-4o-mini, billed from Vapi credits)
                 └────▶ POST <BASE>/webhook   (tool exec + event logs → Supabase)
<BASE> = https://voice-agent-production-23aa.up.railway.app   (or ngrok URL)
```
Set in the Vapi assistant:
- **Server URL** = `<BASE>/webhook`   ← the only one required
- No OpenAI account needed. LLM cost comes out of Vapi credits.

### OPTIONAL upgrade — run the LLM through your own backend
Only if time allows AND you've loaded ~$5 OpenAI credit:
1. Set `OPENAI_API_KEY` in Railway → Variables.
2. Vapi assistant → Model → provider **Custom LLM**, URL = `<BASE>`
   (no path — Vapi appends `/chat/completions`; already implemented in `llm.py`).
3. Test a call. If latency/errors appear, switch the provider back to
   built-in OpenAI — that's the safe fallback.

---

## Plan A — Railway (primary)
1. `git push` → Railway auto-deploys.
2. Confirm live: open `<BASE>/health` → `{"status":"ok"}`.
3. Paste `<BASE>` into Vapi assistant (both fields above).
4. Call the number. Done.

## Plan B — ngrok (fallback if Railway breaks)
Run locally + expose. Two terminals.

**Terminal 1 — start the server:**
```bash
cd /e/voice_agent
./.venv/Scripts/python.exe main.py
```
(Confirm http://localhost:8000/health works.)

**Terminal 2 — expose it:**
```bash
ngrok http 8000
```
Copy the `https://xxxx.ngrok-free.app` URL. That is your `<BASE>`.
- Vapi `model.url`  = `https://xxxx.ngrok-free.app`
- Vapi `server.url` = `https://xxxx.ngrok-free.app/webhook`

> ngrok setup (do ONCE tonight): download from https://ngrok.com, sign up,
> run `ngrok config add-authtoken <token>`. Then Plan B is 10 seconds.

---

## Pre-flight checklist (run before 9 PM)
- [ ] `<BASE>/health` returns ok (Railway)
- [ ] ngrok installed + authtoken set (Plan B ready)
- [ ] Vapi phone number purchased
- [ ] OPENAI_API_KEY set in Railway Variables AND local .env
- [ ] SUPABASE_URL / SUPABASE_KEY set in both; schema.sql run
- [ ] Test call completes end-to-end; a row lands in Supabase `calls`

## The 20% you write live
1. `llm.py` → `SYSTEM_PREAMBLE`: paste the real scenario.
2. `tools.py`: add the 1–3 tools + register in `TOOL_REGISTRY`.
3. `vapi_assistant.json` → `model.tools[]`: matching JSON schemas.
4. `schema.sql`: any new table → paste into Supabase SQL editor.
5. `git push` (or restart local server for ngrok) → test call.

## Common gotchas
- **Vapi says LLM error** → check `<BASE>/chat/completions` reachable & OPENAI_API_KEY set in Railway (not just local).
- **Tool never fires** → tool name in `tools.py` must EXACTLY match the name in `vapi_assistant.json`.
- **ngrok URL changed** → free ngrok gives a new URL each restart; re-paste into Vapi.
- **No DB rows** → using service_role key? table exists? check server logs.
