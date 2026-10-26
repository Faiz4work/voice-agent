# Local and Vapi runbook

## Local demo

1. Open PowerShell in `E:\voice_agent`.
2. Install `requirements.txt` using `.venv\Scripts\python.exe`.
3. Start `run_local.ps1`; visit `http://127.0.0.1:8000`.
4. Ask about hours/services, choose a date, select a time, enter fictional details, confirm and book.
5. In `/staff`, enter the private `ADMIN_API_KEY` from `.env` to review bookings/callbacks or cancel an appointment. `/dashboard` retains patient CRUD.

Do not open `.env` in a screen recording. New local access keys were generated during development without printing their values. Do not place secrets in the address bar or browser storage.

## Enable real AI chat

Set `CHAT_PROVIDER=groq` and `GROQ_API_KEY` in `.env` and restart. Alternatively select `CHAT_PROVIDER=openai` with `OPENAI_API_KEY`. The interface changes from Guided preview to AI conversation. Groq defaults to `GROQ_MODEL=openai/gpt-oss-20b`; OpenAI defaults to `LLM_MODEL=gpt-4o-mini`. The backend executes an allowlist of business tools; patient tools are never exposed to public chat. Tool results determine whether an action completed. Chat sessions expire after 30 minutes and are intentionally held only in one worker's memory.

Try: services → availability tomorrow → provide fictional booking details → read-back → reply `Confirm`. A booking tool call without a separate confirmation turn does not write an appointment. For corrections, provide the corrected detail and confirm the new proposal.

## Enable Vapi browser and inbound phone calls

1. Deploy the backend or run an HTTPS development tunnel to port 8000. Set `SERVER_URL` to its public HTTPS base URL. Vapi cannot call localhost.
2. Set the Vapi private management key as `VAPI_API_KEY` and its browser key as `VAPI_PUBLIC_KEY`. Restrict the browser key in Vapi to approved website origins and assistant IDs.
3. In Vapi Integrations / Server Configuration, create a custom Bearer credential. Its token must equal your private `VAPI_WEBHOOK_SECRET`, with standard `Authorization: Bearer …` enabled. Put its ID in `VAPI_CREDENTIAL_ID`.
4. Keep your existing medical ID in `VAPI_ASSISTANT_ID`. Preview the configuration before applying it. The updated medical payload includes the original intake prompt/tools and the new privacy verification requirements.
5. Run `configure_assistant.py --business hvac --apply` to create a separate HVAC assistant; save the returned ID as `VAPI_HVAC_ASSISTANT_ID`. Use `--business medical --apply` to update the medical assistant's secure webhook and tool schemas when ready. The script rejects identical IDs.
6. Restart the app after changing `.env`. For a hosted app, update the hosting environment and redeploy/restart.
7. In the demo, agree to microphone processing, start a voice call and permit the microphone. Check audio playback, transcript display, mute and hang-up. Request availability and book a fictional appointment, confirming the exact time and timezone. Confirm it appears in `/staff`.
8. For inbound phone service, assign the saved assistant to an owned Vapi number and call it. Verify webhook delivery includes its Bearer credential, a correct tool-call ID, and a stored appointment. This step was not performed without account credentials.

Vapi's current authentication behavior can withhold organization credentials when a transient assistant or client-supplied server URL is used. This implementation starts **saved assistant IDs** and keeps URLs and credential references in saved configuration. Do not put the private secret into frontend overrides. Recordings are disabled in generated configurations; review Vapi's transcript and artifact retention settings separately.

## Automated browser tests

Use a separate shell and an isolated database. The smoke test writes fictional patients, bookings and inquiries; never point it at a live database.

```powershell
New-Item -ItemType Directory -Force artifacts | Out-Null
$env:DATABASE_URL='sqlite:///./artifacts/browser-test.db'
$env:ADMIN_API_KEY='browser-test-admin'
$env:VAPI_WEBHOOK_SECRET='browser-test-webhook'
$env:OPENAI_API_KEY=''
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

In another shell in the project: `.\.venv\Scripts\python.exe tests/browser_smoke.py`. Install `requirements-dev.txt` first. Microsoft Edge is used headlessly. Use a fresh isolated database before each full smoke run. The voice test simulates the browser SDK, never starts a billable call, and cannot establish real voice functionality.

## Troubleshooting

- 401 from private endpoints: send the correct Bearer key. The patient API uses `ADMIN_API_KEY`; Vapi/proxy uses `VAPI_WEBHOOK_SECRET`.
- 503 from private endpoints: the required secret is absent. Do not remove the authentication dependency.
- 409 booking: another request took the slot, details changed under an existing request key, or confirmation is still pending. Refresh availability.
- Guided preview: the selected provider key is absent. For Groq, set `GROQ_API_KEY`, then restart.
- Voice disabled: configure public key, saved assistant ID and webhook secret for that business.
- Voice connects but tools fail: verify the public URL, saved assistant credential reference, endpoint path, tool schemas and provider dashboard delivery logs.
- 410 chat: start a new conversation; the session expired or belongs to the other business.
- On Windows, missing IANA timezones: install pinned `tzdata` from requirements.

Official references: https://docs.vapi.ai/server-url/server-authentication and https://github.com/VapiAI/client-sdk-web

The official Vapi Web SDK is bundled locally in `static/vendor/vapi.js`; starting a call does not require a JavaScript CDN. Rebuild after SDK updates with `npm ci` and `npm run build:voice`. Deployment uses the checked-in bundle and needs no Node build step.

For the requested free-hosting route, see [PythonAnywhere + SQLite + Groq](deployment/PYTHONANYWHERE.md). Groq rate limits and Vapi’s finite credits still apply.
