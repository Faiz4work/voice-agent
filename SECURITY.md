# Security changes and remaining exposure

## Implemented

- Every `/patients` operation requires a server-side staff Bearer key. Appointment/inquiry lists and cancellation are also staff-only. Missing keys fail closed with 503; wrong/missing credentials return 401.
- All medical/HVAC Vapi webhook tool execution and the optional custom-LLM proxy require `VAPI_WEBHOOK_SECRET`. The server also accepts the legacy `X-Vapi-Secret` header for existing credential migrations.
- Public chat exposes scheduling/FAQ/callback tools only; HVAC voice cannot invoke medical record tools.
- Original patient lookup requires caller-supplied last name and DOB before returning stored identity details. Updates require existing last name and DOB verification. These are knowledge checks, not a substitute for stronger identity verification in a real clinic.
- Application logs exclude patient payloads, names, phone numbers, transcripts, summaries and raw database/provider exception messages. SQLAlchemy hides bound SQL parameters. Local/Render launch commands disable URL access logs, which could otherwise record patient search parameters.
- The legacy patient dashboard now uses a private key held in tab memory and escapes record JSON in HTML event attributes, fixing the apostrophe/injection issue.
- Chat history is server-owned and bounded. Explicit separate-turn confirmation guards chat bookings. Body sizes, chat lengths, tool iterations, sessions and common public mutation rates are bounded. Rate limits are per process and do not constitute a distributed abuse defense.
- Security headers, safe DOM text rendering, confirmation/consent controls and a non-root container are included.
- Dependency pins were upgraded after the original audit found known vulnerabilities. Re-run the audit before deployment; the report only describes the database checked during this session.
- `.env` and local databases, browser artifacts and backups are ignored by Git and Docker.

## Patient data in old Git commits

`patients.db` was already tracked when this work began. It was removed **from the Git index only**, preserving the local database and the original medical records on disk. A normal commit of these changes prevents that file appearing in the new tree but **does not erase older GitHub commits, cached objects, forks or clones**.

No historical rewrite or remote operation was performed. The user requested manual pushing. Before sharing this repository publicly again, verify whether those records were fictional. If potentially real, coordinate a history cleanup and relevant data-handling response. The clean-up requires a deliberate history rewrite and a forced remote update, followed by coordination with anyone holding a clone. Merely making a deletion commit is insufficient.

For a planned cleanup, use a fresh mirror and the official `git-filter-repo`/GitHub sensitive-data removal procedure to remove all historical database paths (including renamed paths), verify the resulting history, then update the remote deliberately. Keep any necessary backup private and out of Git. This work does not certify that prior public copies have been removed.

Do not commit the private `.env`, including unrelated account recovery material already present locally. The development process did not print secret values or test placeholder keys against external services.

## Demo boundaries

This is a fictional demo. Do not collect real medical details through public chat. There is no healthcare compliance assessment, strong patient identity verification, data-at-rest encryption layer, staff SSO, audit trail, distributed rate limiter, scheduled retention purge or calendar/EHR synchronization. Use a reviewed identity, storage, audit, retention and provider configuration before expanding to real clinical use.

Vapi browser keys must be restricted in the provider account to approved origins/assistant IDs. The server cannot secure a misconfigured public provider key on the provider's behalf. Recordings are disabled in generated assistant configurations; transcript retention still needs account review.

If Supabase is used, apply the provided RLS/revocation SQL. Backend authentication does not protect a separate misconfigured public database Data API.
