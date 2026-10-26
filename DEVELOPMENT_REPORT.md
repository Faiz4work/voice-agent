# Development report — 25 October 2026

## Update after live Vapi testing and Groq selection

- Newly supplied Vapi private/public keys were validated. A separate HVAC assistant and authenticated webhook credential were created. The two existing assistants, including medical intake, were unchanged.
- Real WebRTC calls connected, played assistant speech, recognized a synthetic “Hello”, and invoked live availability through the authenticated public webhook. This was not a physical-microphone test. The bounded full-booking attempt repeated read-back confirmation and did not produce a confirmed booking; complete spoken booking still needs verification.
- Fixed real Vapi schema incompatibility for nullable fields, upgraded the official browser SDK from 2.4.0 to 3.0.1 / Daily 0.94.0, enabled its eval-free loader and audio worklet support, and increased the supported join timeout. Staff pages retain stricter script permissions.
- Vapi text-chat API returned 402 requiring a payment method. No card, purchase or auto-reload was added. Test calls consumed existing Vapi credits.
- User selected Groq’s free API tier. Added Groq chat/provider routing, local tool calling, safe 429/credential errors, and optional Groq HVAC voice configuration. The existing live HVAC assistant remains on its working OpenAI configuration until the Groq key is supplied and applied. `GROQ_API_KEY` is currently absent; live Groq behavior is unverified.
- 49 isolated regression/security tests now pass. npm audit of runtime browser dependencies reports zero vulnerabilities. Test fixtures explicitly ignore the real local provider credentials.
- Prepared PythonAnywhere ASGI startup and explicit persistent/absolute-path SQLite production support. `api.groq.com` is allowlisted; outgoing Vapi management runs locally. No PythonAnywhere account exists yet, so hosted availability/connectivity remains unverified.
- Git remains uncommitted and unpushed. `.env`, audio fixtures, live-call diagnostics and the tunnel binary stay ignored.

The earlier baseline below is historical; current status above supersedes its credential and live-test limitations.


Work was performed directly in `E:\voice_agent`. The starting branch was clean `main`, tracking `origin/main` at `58e44d1`. No commit, push, deployment, existing-assistant update or paid provider call was made.

## Delivered

- Responsive Reception Studio website with fictional HVAC and CareCloud business demos, guided/AI chat, voice controls, live availability, booking confirmation, callback requests and staff screens.
- Shared business context and tool execution across website and Vapi paths; original medical patient registration preserved behind authentication.
- SQLAlchemy appointment/inquiry persistence, time-zone validation, unique active-slot enforcement, booking idempotency, business isolation, staff review and cancellation.
- Patient API/webhook/proxy authentication, privacy-safe logging, caller-detail verification, legacy dashboard injection fix, local private keys, data ignores and dependency security upgrades.
- Local launcher, Vapi preview/apply tooling, Render Blueprint, Docker deployment and setup/security documentation.

## Verified locally

- 37 API/regression/security tests passed after upgrading vulnerable dependencies.
- Dependency audit of runtime requirements: no known vulnerabilities found in the checked advisory database after upgrades.
- Headless Edge end-to-end checks passed: guided chat; business switching; availability; confirmed booking; callback persistence; staff authentication/cancellation; original patient dashboard editing of an apostrophe-containing surname; mobile/tablet layouts without horizontal overflow.
- Vapi browser consent, start, transcript, mute and hang-up UI behavior verified with a mocked SDK. This was not a real voice call.
- Real bundled Vapi SDK import, constructor and call methods verified in headless Edge without making a call. The CDN initially returned an infrastructure error, so the official SDK is now bundled locally with locked dependencies. npm audit found zero vulnerabilities.
- Desktop/mobile/tablet screenshots generated and visually inspected in ignored `artifacts/`.
- Unit/API tests used a temporary SQLite database; browser checks used separate `artifacts/browser-test.db`. Existing local patient rows were not used as fixtures or erased.

## Blocked or unverified

- The named HVAC ZIP was not found in local project, likely user folders or E: search. “AI Chatbot Pricing Plan” was found in the app's chat list, but its content loader repeatedly timed out. A prior review chat supplied general project context, not the missing package. The new fictional HVAC implementation does not claim to reproduce that ZIP.
- Local OpenAI/Vapi entries were placeholders; no usable Vapi public key or assistant IDs were configured in this environment. Real AI output, audio conversations, inbound phone calls, cloud credentials and external webhook delivery remain unverified.
- No hosted database URL or hosting account setup was available. PostgreSQL compatibility uses portable SQLAlchemy constructs, but hosted PostgreSQL connectivity and Supabase RLS execution were not tested here.
- Old GitHub commits may still contain patient data. The next Git tree removes the database, while historical remote cleanup remains outstanding and requires a deliberate coordinated history rewrite.
- No external calendar, EHR, SMS/email notification, emergency dispatch or automatic callback delivery is implemented. All demo appointments use the app database scheduler.

See `RUNBOOK.md` for required credential setup and `DEPLOYMENT.md` for free-tier limitations.

The official Vapi Web SDK is bundled locally in `static/vendor/vapi.js`; starting a call does not require a JavaScript CDN. Rebuild after SDK updates with `npm ci` and `npm run build:voice`. Deployment uses the checked-in bundle and needs no Node build step.
