# PythonAnywhere + SQLite + Groq demo

Recommended for the requested low-traffic demonstration, subject to confirming ASGI availability on the actual free account. No account or hosted site has been created in this session.

## Verified constraints on 25 October 2026

- PythonAnywhere's free-account allowlist includes `api.groq.com`.
- Free accounts have restricted outbound HTTP(S), one web app and limited private storage. `api.vapi.ai` is not currently listed. That does not prevent this architecture: browser voice connects directly to Vapi, and Vapi sends incoming HTTPS requests to the app. Run Vapi assistant-management commands locally instead of on the free host.
- PythonAnywhere documents FastAPI through its experimental ASGI service. API/command-line setup is required and long-term ASGI pricing is not final. Confirm access in the newly created account before relying on this host.
- SQLite must live on the account's persistent private storage, outside the source checkout. Keep one worker and make private backups. Do not upload the existing local patient database.
- Groq's free tier has per-model rate limits. It is not unlimited. The website handles provider 429 responses without exposing keys or silently switching to a paid provider.
- Vapi voice still consumes credits for platform, transcription, voice and any managed model usage. A Groq key only changes the model component. No purchase or auto-reload was enabled during testing.

## Local Groq setup first

Create a free Groq account and API key at [Groq Console](https://console.groq.com/keys). Save it in the private local `.env`:

```dotenv
CHAT_PROVIDER=groq
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
```

Use your actual key after `GROQ_API_KEY=`. The default model is listed in Groq's free-plan limits and supports local function/tool calling. It is an open-weight model served by Groq; it does not require an OpenAI account or API key. Restart the app after editing settings.

To use the same Groq account for the HVAC voice model after verifying the key:

```powershell
.\.venv\Scripts\python.exe configure_assistant.py --business hvac --model-provider groq
.\.venv\Scripts\python.exe configure_assistant.py --business hvac --model-provider groq --apply
```

Preview does not change Vapi. Apply registers a Groq provider key if none exists, then updates only the separate HVAC assistant. Existing Groq credentials are reused without overwriting them; verify that the desired Groq organization is connected in Vapi. Medical intake keeps its OpenAI model. This switch has not been applied yet because `GROQ_API_KEY` is absent.

## Create the free PythonAnywhere account

Use [PythonAnywhere's Beginner account](https://www.pythonanywhere.com/pricing/). Record the username and whether it is on the US or EU site. Then enable an API token in the account settings for the documented `pa` ASGI setup. Do not post private tokens in chat.

## Upload clean source and create a virtual environment

The updated project is staged locally and has not been pushed. Cloning the current GitHub remote will not retrieve the new changes until the user commits and pushes manually. Upload reviewed source, excluding `.env`, `.git`, all databases, `.venv`, `node_modules`, `artifacts` and private backups.

In the PythonAnywhere Bash console, using the real username and a supported Python version:

```bash
mkvirtualenv voice-agent --python=python3.12
cd /home/YOURUSERNAME/voice_agent
pip install -r requirements.txt
pip install --upgrade pythonanywhere
mkdir -p /home/YOURUSERNAME/private_data
chmod 700 /home/YOURUSERNAME/private_data
```

Create a private `.env` in the project, using real private values rather than committing them:

```dotenv
APP_ENV=production
DATABASE_URL=sqlite:////home/YOURUSERNAME/private_data/reception.db
SQLITE_PERSISTENT=true
CHAT_PROVIDER=groq
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
ADMIN_API_KEY=
VAPI_WEBHOOK_SECRET=
VAPI_PUBLIC_KEY=
VAPI_HVAC_ASSISTANT_ID=
```

Use the webhook secret that matches the Vapi saved credential. Staff/admin and provider private keys stay server-side. The hosted database starts empty. The app refuses production SQLite unless its path is absolute and persistent storage is explicitly acknowledged. Do not enable this override on an ephemeral filesystem such as Render's free service.

## Start the experimental ASGI web app

After checking account support and generating its API token:

```bash
pa website create --domain YOURUSERNAME.pythonanywhere.com --command '/bin/bash /home/YOURUSERNAME/voice_agent/deployment/pythonanywhere_start.sh'
```

Use the EU domain if the account is on the EU service. The startup script uses the host-provided `DOMAIN_SOCKET`, the `voice-agent` virtual environment and one Uvicorn worker. The app serves its own static assets; no ASGI static-file mapping is required.

Verify `/health`, Groq chat, a fictional form booking, staff access and callback persistence. Check that anonymous `/patients` requests return 401. Confirm the database survives a web-app restart before sharing the demo.

## Connect Vapi from the local computer

Replace local `SERVER_URL` with the hosted HTTPS URL. Keep `VAPI_CREDENTIAL_ID` and the matching secret. Run the local HVAC assistant configuration command above, then allow the hosted origin and HVAC assistant ID on the public Vapi key. Test a complete spoken conversation and verify an explicitly confirmed booking in `/staff`.

The current temporary Cloudflare connection exposes only the authenticated HVAC webhook, not patient routes or staff screens. It will stop working when the local gateway or tunnel stops and is not permanent hosting.

## Sources

- [Groq free-plan limits](https://console.groq.com/docs/rate-limits)
- [Groq tool calling](https://console.groq.com/docs/tool-use/overview)
- [PythonAnywhere free-account allowlist](https://www.pythonanywhere.com/whitelist/)
- [PythonAnywhere ASGI setup and limitations](https://help.pythonanywhere.com/pages/ASGICommandLine/)
- [PythonAnywhere account plans](https://www.pythonanywhere.com/pricing/)
- [Vapi provider-key billing](https://docs.vapi.ai/customization/provider-keys)
