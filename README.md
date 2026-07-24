# Voice AI Agent — Patient Registration System

A voice agent reachable at a real US phone number that collects standard US
patient demographics through natural conversation, validates them, reads them
back for confirmation, persists them to PostgreSQL, and exposes them through a
REST API.

## Live demo

| | |
|---|---|
| **Phone number** | **+1 (262) 360-4601** — call to register a patient |
| **API base URL** | https://voice-agent-production-23aa.up.railway.app |
| **Status page** | https://voice-agent-production-23aa.up.railway.app/ |
| **Interactive API docs** | https://voice-agent-production-23aa.up.railway.app/docs |
| **Repository** | https://github.com/Faiz4work/voice-agent |

Quick check:
```bash
curl https://voice-agent-production-23aa.up.railway.app/patients
```

## Architecture

```
 ┌────────────┐   PSTN    ┌──────────────┐   tool calls   ┌────────────────────┐
 │   Caller   │──────────▶│  Vapi        │───────────────▶│  FastAPI backend   │
 │  (phone)   │◀──────────│  telephony   │◀───────────────│  (Railway)         │
 └────────────┘   voice   │  STT/TTS/LLM │   spoken result└─────────┬──────────┘
                          └──────────────┘                         │
                                                                   ▼
   REST clients ────────────────────────────────────────▶  ┌───────────────┐
   GET/POST/PUT/DELETE /patients                           │  PostgreSQL   │
                                                           └───────────────┘
```

**Separation of concerns** — the design decision this project is built around:

| Layer | File | Responsibility |
|---|---|---|
| Telephony / STT / TTS | Vapi (managed) | Audio, turn-taking, barge-in |
| Prompt / conversation design | `prompt.md` | Agent persona, correction handling, read-back |
| Tool adapters | `tools.py` | Translate LLM tool calls ↔ service layer, spoken error text |
| HTTP API | `api.py` | REST endpoints, status codes, response envelope |
| Validation | `schemas.py` | Pydantic rules — the single source of truth |
| Service layer | `crud.py` | All data access; shared by voice **and** API |
| Persistence | `models.py` | SQLAlchemy models, constraints, indexes |

The key property: **the voice agent and the REST API share the same validation
and service layer.** A patient registered by phone goes through byte-identical
validation to one created with `POST /patients`. The phone path is never a
shortcut around the rules.

## Tech stack & justification

| Layer | Choice | Why |
|---|---|---|
| Telephony + Voice | **Vapi** | Managed STT/TTS/turn-taking and a Twilio number import. Building Twilio+Deepgram+ElevenLabs glue by hand would have consumed most of the 3 hours for no evaluative gain. |
| LLM | **GPT-4o-mini** (via Vapi) | Low latency matters more than raw reasoning for form-filling dialogue; strong tool-calling. Billed through Vapi credits, so no second key to manage. |
| Backend | **Python / FastAPI** | Pydantic gives declarative validation that doubles as OpenAPI docs — high output per minute under time pressure. |
| Database | **PostgreSQL** (Railway) | Real constraints and types. Chosen over SQLite because Railway's filesystem is ephemeral — SQLite would lose data on redeploy, breaking the "data survives" requirement. |
| ORM | **SQLAlchemy 2.0** | Same models run on SQLite locally and Postgres in production, so local dev needs no database server. |
| Hosting | **Railway** | Git-push deploys, managed Postgres in the same project, free TLS domain. |

## Data model

Table `patients` — the standard US minimum demographic dataset.

| Field | Type | Validation | Required |
|---|---|---|---|
| `patient_id` | UUID | auto-generated | auto |
| `first_name` / `last_name` | String(50) | 1–50 chars, letters + hyphen/apostrophe | yes |
| `date_of_birth` | Date (ISO string) | valid, not future, not pre-1900 | yes |
| `sex` | Enum | Male / Female / Other / Decline to Answer | yes |
| `phone_number` | String(10) | 10 US digits, area code not 0/1 | yes |
| `address_line_1` | String(200) | non-empty | yes |
| `city` | String(100) | 1–100 chars | yes |
| `state` | String(2) | valid 2-letter US state/territory | yes |
| `zip_code` | String(10) | 5-digit or ZIP+4 | yes |
| `email` | String(254) | RFC email format | no |
| `address_line_2` | String(200) | — | no |
| `insurance_provider` | String(120) | — | no |
| `insurance_member_id` | String(60) | — | no |
| `preferred_language` | String(50) | default `English` | no |
| `emergency_contact_name` | String(120) | — | no |
| `emergency_contact_phone` | String(10) | 10 US digits | no |
| `created_at` / `updated_at` | Timestamp (UTC) | auto | auto |
| `deleted_at` | Timestamp (UTC) | set by soft delete | auto |

**Normalization on write:** phone numbers are stripped to 10 digits (`(415)
555-0134` → `4155550134`), states upper-cased, dates converted to ISO. This
matters for a voice agent, where the same value arrives differently every call.

## REST API

All responses use the envelope `{"data": ..., "error": ...}`.

| Method | Endpoint | Description | Codes |
|---|---|---|---|
| GET | `/patients` | List; filters `?last_name=` `?date_of_birth=` `?phone_number=` `?include_deleted=` | 200, 400 |
| GET | `/patients/{id}` | Fetch by UUID | 200, 404 |
| POST | `/patients` | Create | 201, 422 |
| PUT | `/patients/{id}` | Partial update | 200, 404, 422 |
| DELETE | `/patients/{id}` | **Soft** delete (sets `deleted_at`) | 200, 404 |

Supporting endpoints: `GET /health`, `GET /` (status page), `GET /docs`
(OpenAPI), `POST /webhook` (Vapi tool calls).

### Examples

```bash
BASE=https://voice-agent-production-23aa.up.railway.app

# Create
curl -X POST $BASE/patients -H 'Content-Type: application/json' -d '{
  "first_name":"Jane","last_name":"Doe","date_of_birth":"03/14/1985",
  "sex":"Female","phone_number":"(415) 555-0134",
  "address_line_1":"12 Market St","city":"San Francisco",
  "state":"CA","zip_code":"94103"}'

# Find by phone
curl "$BASE/patients?phone_number=4155550134"

# Partial update
curl -X PUT $BASE/patients/<id> -H 'Content-Type: application/json' \
  -d '{"city":"Oakland"}'

# Soft delete
curl -X DELETE $BASE/patients/<id>
```

Validation failures return `422` with per-field reasons:
```json
{"data":null,"error":{"message":"Validation failed","fields":[
  {"field":"date_of_birth","reason":"date of birth cannot be in the future"},
  {"field":"state","reason":"ZZ is not a valid 2-letter US state code"}]}}
```

## Conversation design

The full system prompt lives in [`prompt.md`](prompt.md) — version-controlled
rather than buried in a dashboard, so prompt engineering is reviewable.

Design decisions:

- **Grouped questions, not an IVR.** "First and last name?" then "Street,
  city, state, and ZIP?" — fewer turns, more natural.
- **Corrections are first-class.** The agent accepts corrections to any field
  at any point, prefers spelled-out letters over what it heard, and supports
  "start over" mid-call.
- **Mandatory read-back.** The agent may not call `register_patient` until the
  caller confirms a spoken summary. Dates are spoken as words, phone numbers
  in groups.
- **Status-prefixed tool results.** Tools return `SUCCESS` / `INVALID` /
  `DUPLICATE` / `NOT_FOUND` / `ERROR` so the model follows a deterministic
  recovery branch instead of improvising. `INVALID` names the exact fields to
  re-ask, so the agent never re-collects fields that were already fine.
- **Failures are spoken honestly.** On a database error the caller is told
  plainly their information was *not* saved — never a false confirmation.
- **Sex is asked, never inferred** from voice.

### Voice tools

| Tool | Purpose |
|---|---|
| `lookup_patient(phone_number)` | Duplicate detection for returning callers |
| `register_patient(...)` | Validate + persist after confirmation |
| `update_patient(patient_id, ...)` | Partial update of an existing record |

## Edge cases handled

| Scenario | Behavior |
|---|---|
| Invalid DOB (future / pre-1900) | Field-specific re-prompt; never stored |
| Phone too short, or area code 0/1 | Rejected at the schema, agent re-asks that field only |
| Unknown state or malformed ZIP | Rejected with a spoken reason |
| Caller corrects an earlier field | Accepted mid-stream; only the corrected part is re-confirmed |
| Caller says "start over" | Prompt instructs a full reset |
| Returning caller (same phone) | `DUPLICATE` → agent offers to update instead |
| Database write fails | Caller hears an honest apology, not silence or a false success |
| Malformed tool arguments from the LLM | Caught per-tool; the call continues |
| Unhandled server exception | Global handler returns a `500` envelope; the call is never left hanging |
| Call drops mid-registration | Nothing is written — the record is only saved after confirmation, so no partial patients |

## Running locally

```bash
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env
python main.py            # http://localhost:8000
```

With no `DATABASE_URL` set it uses a local SQLite file (`patients.db`), so no
database server is needed for development.

Expose to Vapi for local testing:
```bash
ngrok http 8000
# set the assistant's Server URL to https://<id>.ngrok-free.app/webhook
```

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | production | Postgres connection string. Falls back to SQLite locally. |
| `PORT` | no | Injected by Railway. Defaults to 8000. |
| `OPENAI_API_KEY` | no | Only for the optional custom-LLM mode (see below). |
| `LLM_MODEL` | no | Defaults to `gpt-4o-mini`. |

No secrets are committed; `.env` is gitignored.

## Vapi configuration

[`vapi_assistant.json`](vapi_assistant.json) holds the full assistant config —
first message, tool JSON schemas, voice, and transcriber. To reproduce:

1. Create an inbound assistant in Vapi.
2. Paste the system prompt from `prompt.md`.
3. Add the three tools from `vapi_assistant.json`.
4. Set **Server URL** to `<BASE>/webhook`.
5. Import a Twilio number and attach the assistant to it.

## Trade-offs and known limitations

- **Vapi over raw Twilio+Deepgram+ElevenLabs.** Faster to a working system;
  the cost is less control over audio and a vendor dependency.
- **`date_of_birth` stored as an ISO string, not a `DATE` column.** Keeps
  SQLite and Postgres behavior identical and avoids driver-specific date
  coercion. In production this should be a real `DATE`.
- **No authentication on the API.** Out of scope for the assessment, and the
  spec says not to store real patient data. Any real deployment needs
  authn/authz, TLS-only access, audit logging, and encryption at rest.
- **Not HIPAA compliant** — explicitly out of scope per the brief.
- **Duplicate detection keys on phone number alone.** Two family members
  sharing a landline would collide; production should match on name + DOB too.
- **No rate limiting** on the public API.
- **Soft-deleted records are still returned** via `?include_deleted=true` with
  no auth — fine for review, wrong for production.
- **Conversation state lives in the LLM context**, not server-side. If a call
  drops mid-registration, progress is lost by design (nothing partial is
  written). Resumable intake would need a server-side session store.

## Next steps (with more time)

1. **API authentication** — API keys or JWT, plus per-key rate limits.
2. **Server-side conversation state** so a dropped call can resume.
3. **Store call transcripts** linked to `patient_id` (the schema already has a
   `call_summary` column reserved for this).
4. **Smarter duplicate matching** on name + DOB + phone with a confidence score.
5. **Automated test suite** — the service layer is already isolated enough to
   test without the telephony stack.
6. **Real `DATE` / `CITEXT` column types** and a migration tool (Alembic).
7. **Multi-language support** — Vapi supports it; the prompt would need
   localized read-back formatting for dates and numbers.
8. **Structured audit log** of every read/write for compliance.
