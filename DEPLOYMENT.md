# Free-tier deployment preparation

The user now prefers SQLite. The prepared preferred route is [PythonAnywhere + SQLite + Groq](deployment/PYTHONANYWHERE.md), pending account creation and verification of its experimental ASGI access. The Render instructions below remain an alternative when PostgreSQL is acceptable.

The app is prepared for a free **demonstration** deployment, not provisioned. Use Render's free Python web service with persistent PostgreSQL from a separate provider such as Supabase's free project. AI inference, voice usage and phone numbers can incur their own provider charges; free hosting does not make these services free.

## Render plus PostgreSQL

1. Review the prepared Git changes and handle historical patient-data exposure in `SECURITY.md`. Push manually when ready.
2. Create a free Supabase project (or another PostgreSQL database). Obtain its direct or session-pooler PostgreSQL connection URL. For an IPv4-only host use the provider's compatible session pooler. Require TLS with `sslmode=require` in the URL. Use database credentials, not a Supabase anon key or HTTP API key.
3. In Render, create a Blueprint from this repo using `render.yaml`, or create a free Python Web Service manually. Build: `pip install -r requirements.txt`; start: `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log`; health: `/health`. Auto-deploy is disabled in the prepared configuration.
4. Set persistent `DATABASE_URL`. Render generates separate admin and webhook secrets from the Blueprint. Preserve them in a password manager. Set `OPENAI_API_KEY` to enable AI; leave it blank for guided preview. Configure Vapi public key and distinct saved assistant IDs when available.
5. Deploy. Startup refuses `APP_ENV=production` with missing private secrets or unacknowledged/relative-path SQLite, preventing accidental use of ephemeral local data. The app creates missing tables on startup. It does not upload the existing local patient database.
6. For Supabase, run `deployment/supabase_security.sql` after table creation. This removes Data API access for public/client roles and enables RLS. The server's privileged database role retains access. No browser should query patient/appointment tables directly.
7. Put the deployed HTTPS URL in local `SERVER_URL`, configure saved Vapi assistants with a matching Bearer credential, and update hosting assistant IDs. Verify a real call creates a fictional appointment. `/health` also checks database connectivity.
8. Confirm patient APIs return 401 without a staff key, and callback/booking lists remain staff-only. Review Vapi retention and domain/assistant restrictions before sharing the demo URL.

## Free-tier constraints checked on 25 October 2026

- Render free web services sleep after 15 idle minutes and can take roughly a minute to wake. An asleep backend can miss Vapi webhook deadlines; open the demo and wait for `/health` before a demonstration. A reliable always-on receptionist needs suitable hosting.
- Render free service filesystems are ephemeral. Never persist appointments in SQLite on that host.
- Free Render PostgreSQL expires after 30 days. It is not the long-term database choice in this setup.
- Supabase's free plan lists a 500 MB database. Verify its current inactivity, retention and usage constraints when provisioning.
- This implementation deliberately uses one web worker: chat sessions and rate limits are in memory. Multi-instance scaling requires shared session/rate-limit storage. Database uniqueness still protects scheduling across workers, but conversations do not follow users between workers.

Official sources:
- https://render.com/docs/free
- https://render.com/docs/web-services
- https://supabase.com/pricing
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/database/postgres/row-level-security
- https://docs.vapi.ai/server-url/server-authentication

## Other deployment options

The Dockerfile runs as a non-root user and excludes `.env`, databases, Git metadata and local artifacts through `.dockerignore`. Supply environment variables at runtime and use external PostgreSQL. Existing `railway.json`/`Procfile` remain usable with a suitable Railway account; the expired trial was not renewed.

No deployment, DNS changes, phone-number provisioning, Git push or billable voice test was performed in this session.
