# Reception Studio — AI chat and Vapi voice receptionist

FastAPI demonstration with business-specific chat, Vapi voice tools, live appointment availability, booking, callback requests, and a responsive website. The original CareCloud patient intake models, validation, CRUD API, dashboard and voice tools are retained behind authentication. The HVAC demo uses separate business context and scheduling tables.

All business details and appointments in the public demo are fictional. This is not a clinical system or a healthcare compliance claim.

## Run locally (Windows PowerShell)

```powershell
cd E:\voice_agent
python -m venv .venv  # only if a virtual environment does not exist
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# For a fresh clone, copy .env.example to .env and generate private access keys.
.\run_local.ps1
```

Open http://127.0.0.1:8000. `/hvac` opens home services and `/medical` opens medical scheduling. `/dashboard` retains the original patient management screen; `/staff` manages appointments and callback requests. Both staff screens require `ADMIN_API_KEY` for every data request. Keys stay in tab memory, never local storage. This development session generated local private access keys in the ignored `.env`; do not share them or add `.env` to Git.

Without a key for the selected provider, the chat clearly identifies itself as a **guided preview**, answers supported FAQ questions and reads live scheduling availability. The booking and callback forms remain functional. A real Groq or OpenAI key enables server-side AI conversation and tool calls. Set `CHAT_PROVIDER=groq` and `GROQ_API_KEY` for Groq’s free tier; `GROQ_MODEL` defaults to `openai/gpt-oss-20b`. No OpenAI key is required for Groq. There is no false claim that the guided fallback is a live AI model.

## What is implemented

- Business profiles in `businesses.json`: services, timezone, opening hours, FAQs, service area and receptionist greeting.
- Server-owned chat history and business context, bounded sessions and request rates. Users cannot submit their own system prompts or tool-result history.
- Tools: `get_business_info`, `check_availability`, `book_appointment`, `create_inquiry`. Public chat has no patient-record tools.
- Chat booking uses a separate explicit confirmation turn; changed details require a new confirmation. The web form also requires confirmation. Voice uses validated tool fields plus the saved assistant's read-back instructions.
- US contact validation, timezone-aware booking windows, 60-minute lead time, single shared appointment capacity per business, unique active-slot constraint, idempotent booking retries and staff cancellation.
- Appointment and inquiry persistence through SQLAlchemy. SQLite locally; PostgreSQL supported for deployment.
- Browser voice controls: consent, start, transcript display, mute, hang-up, connection failure handling and business switching. Only the Vapi public key and saved assistant ID enter browser code.
- The medical `/webhook` still supports the original `register_patient`, `lookup_patient` and `update_patient`. Caller-provided last name and DOB verification is required for lookup/update disclosure; these checks do not constitute strong patient identity authentication.
- Private patient APIs, Vapi webhooks and custom-LLM proxy fail closed when unconfigured. Sensitive values, transcripts and SQL parameters are excluded from application logs.

Availability represents the app's own database scheduler. It does not sync Google Calendar, Outlook, an EHR or dispatch software. Callback requests are saved for staff; no SMS, email or notification is sent.

## Architecture

```text
static/index.html + app.js + style.css
             |
             +-- /api/{business}/chat --> chatbot.py --> provider + shared tools
             +-- /api/{business}/availability, bookings, inquiries
             |                              |
Vapi saved assistant --> authenticated /webhook[/hvac]
                                            |
                              reception.py / tools.py
                                            |
                           SQLAlchemy + SQLite / PostgreSQL
                           patients | appointments | inquiries
```

`config.py` loads `.env` **before** database/router imports. `main.py` initializes tables at startup and verifies production settings. `reception.py` is the single scheduling service for forms, chat and voice. `reception_models.py` adds tables without modifying the existing patient schema. Existing patient validation remains in `schemas.py`.

## Vapi setup

See [RUNBOOK.md](RUNBOOK.md). Keep the existing medical assistant ID in `VAPI_ASSISTANT_ID`; use a **different** `VAPI_HVAC_ASSISTANT_ID` for home services. Do not replace your medical assistant with the HVAC configuration.

```powershell
# Preview locally; no provider changes are made.
.\.venv\Scripts\python.exe configure_assistant.py --business hvac
.\.venv\Scripts\python.exe configure_assistant.py --business medical
# After credentials, saved server authentication and public HTTPS backend are configured:
.\.venv\Scripts\python.exe configure_assistant.py --business hvac --apply
```

The script creates a separate assistant when that business has no configured ID and prints its resulting ID. Store it in your private settings and restart the backend. It requires a Vapi custom Bearer credential whose token equals `VAPI_WEBHOOK_SECRET`. Saved assistant server URLs use `credentialId`; the browser never supplies server overrides or private webhook headers. For incoming phone calls, assign the corresponding saved assistant to a Vapi phone number in the dashboard. Provisioning a phone number and verifying inbound calls require your provider account.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt --progress-spinner off
```

Tests use an isolated temporary SQLite database. `tests/browser_smoke.py` checks an already-running **isolated test server** on port 8000 using installed Microsoft Edge. See the runbook before running it: it writes fictional records and expects test-only credentials. Browser screenshots and databases go into ignored `artifacts/`. The Vapi browser test mocks the SDK; it does not test actual speech, provider credentials, audio quality or external webhook delivery. No live AI provider, hosted PostgreSQL or real Vapi call could be verified without credentials.

## Deployment and remaining work

The preferred demo target is now **PythonAnywhere + persistent SQLite + Groq**. See [PythonAnywhere setup](deployment/PYTHONANYWHERE.md). ASGI access needs verification on the free account. Render remains an alternative with PostgreSQL; its free service cannot safely persist a SQLite database.

See [DEPLOYMENT.md](DEPLOYMENT.md), [SECURITY.md](SECURITY.md) and [DEVELOPMENT_REPORT.md](DEVELOPMENT_REPORT.md). `render.yaml`, `Dockerfile` and the existing Railway setup are provided. No hosting was provisioned and no Git changes were pushed.

`HVAC_demo_for_E_voice_agent_2026-10-25.zip` was not present locally. The referenced ChatGPT chat was found by title but its content loader timed out repeatedly. The implemented fictional HVAC profile is independent work, **not an integration of that unrecovered ZIP**. Replace the profile with approved facts if the package is recovered.

The official Vapi Web SDK is bundled locally in `static/vendor/vapi.js`; starting a call does not require a JavaScript CDN. Rebuild after SDK updates with `npm ci` and `npm run build:voice`. Deployment uses the checked-in bundle and needs no Node build step.
