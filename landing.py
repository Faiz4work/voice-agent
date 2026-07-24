"""Landing page at / — a full UI where a visitor can call the agent in-browser.

Uses Vapi's official web widget (loaded from their CDN) to place a WebRTC call
straight to the assistant, so a reviewer can test the agent with one click — no
phone, no dialing, no Twilio trial message. The endpoint details and links sit
alongside so the page doubles as the project's front door.

The public Vapi key is injected from the VAPI_PUBLIC_KEY environment variable.
Vapi public keys are designed to be exposed in client-side code; even so we keep
it in an env var rather than committing it to the public repo.
"""
import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "60f2a788-a8e6-4271-bf17-05c03ef34dee")
PHONE_NUMBER = os.getenv("AGENT_PHONE_NUMBER", "+1 (262) 360-4601")


def _page() -> str:
    public_key = os.getenv("VAPI_PUBLIC_KEY", "")
    # If the key isn't configured, the button explains what to do rather than
    # silently failing.
    call_enabled = "true" if public_key else "false"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CareCloud — Patient Registration Voice Agent</title>
<style>
:root{{
  --bg:#0a0e13; --panel:#111923; --panel2:#0d141d; --line:#1e2b38;
  --text:#e8eef5; --muted:#8b98a5; --accent:#3ddc97;
  --accent2:#2bb37f; --ring:rgba(61,220,151,.35);
}}
*{{box-sizing:border-box}}
html,body{{margin:0}}
body{{background:radial-gradient(1200px 600px at 50% -10%,#132030 0%,var(--bg) 55%);
  color:var(--text);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  min-height:100vh}}
.wrap{{max-width:1080px;margin:0 auto;padding:2.5rem 1.25rem 4rem}}
header{{display:flex;align-items:center;gap:.7rem;margin-bottom:2.5rem}}
.logo{{width:38px;height:38px;border-radius:10px;flex:0 0 auto;
  background:linear-gradient(135deg,var(--accent),#1f7d5a);display:grid;place-items:center;
  color:#04140d;font-weight:800}}
.brand{{font-weight:700;letter-spacing:.2px}}
.brand small{{display:block;color:var(--muted);font-weight:400;font-size:.8rem}}
.live{{margin-left:auto;font-size:.8rem;color:var(--accent);border:1px solid var(--line);
  padding:.25rem .6rem;border-radius:999px}}
.live .d{{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--accent);
  margin-right:.4rem;box-shadow:0 0 0 0 var(--ring);animation:pulse 2s infinite}}
@keyframes pulse{{0%{{box-shadow:0 0 0 0 var(--ring)}}70%{{box-shadow:0 0 0 8px transparent}}
  100%{{box-shadow:0 0 0 0 transparent}}}}

.hero{{display:grid;grid-template-columns:1.1fr .9fr;gap:1.5rem;align-items:stretch}}
@media(max-width:800px){{.hero{{grid-template-columns:1fr}}}}

.card{{background:linear-gradient(180deg,var(--panel),var(--panel2));
  border:1px solid var(--line);border-radius:18px;padding:2rem}}
h1{{font-size:2rem;line-height:1.2;margin:.2rem 0 .6rem}}
h1 span{{color:var(--accent)}}
.lead{{color:var(--muted);margin:0 0 1.5rem}}

.callcard{{display:flex;flex-direction:column;align-items:center;justify-content:center;
  text-align:center;gap:1rem}}
.orb{{width:104px;height:104px;border-radius:50%;display:grid;place-items:center;
  background:radial-gradient(circle at 50% 35%,#1c3a2c,#0f1a15);border:1px solid var(--line);
  transition:.3s}}
.orb svg{{width:44px;height:44px;color:var(--accent)}}
body.in-call .orb{{border-color:var(--accent);box-shadow:0 0 0 6px var(--ring);
  animation:breathe 1.6s ease-in-out infinite}}
@keyframes breathe{{0%,100%{{box-shadow:0 0 0 6px var(--ring)}}50%{{box-shadow:0 0 0 14px transparent}}}}
.agent-name{{font-weight:700;font-size:1.15rem}}
.agent-role{{color:var(--muted);font-size:.9rem;margin-top:-.6rem}}

.btn{{appearance:none;border:none;cursor:pointer;font:inherit;font-weight:700;
  padding:.9rem 1.6rem;border-radius:12px;display:inline-flex;align-items:center;gap:.6rem;
  background:linear-gradient(135deg,var(--accent),var(--accent2));color:#04140d;
  transition:.15s;font-size:1.05rem}}
.btn:hover{{transform:translateY(-1px);filter:brightness(1.05)}}
.btn:disabled{{opacity:.5;cursor:not-allowed;transform:none}}
.btn.end{{background:linear-gradient(135deg,#ff6b6b,#d9433f);color:#fff}}
.status{{min-height:1.2em;color:var(--muted);font-size:.9rem}}
.status.err{{color:#ff8f8f}}
.hint{{font-size:.82rem;color:var(--muted)}}

.section-title{{font-size:.72rem;text-transform:uppercase;letter-spacing:.09em;
  color:var(--muted);margin:2.4rem 0 .8rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:.9rem}}
.tile{{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:1.1rem 1.2rem;
  text-decoration:none;color:inherit;display:block;transition:.15s}}
.tile:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.tile h3{{margin:0 0 .25rem;font-size:1rem}}
.tile p{{margin:0;color:var(--muted);font-size:.86rem}}
.tile code{{color:var(--accent)}}

.meta{{display:flex;flex-wrap:wrap;gap:.6rem 1.4rem;margin-top:1.2rem;
  color:var(--muted);font-size:.86rem}}
.meta b{{color:var(--text)}}
a{{color:var(--accent)}}
footer{{margin-top:2.5rem;color:var(--muted);font-size:.8rem;text-align:center}}
</style></head>
<body>
<div class="wrap">
  <header>
    <div class="logo">C</div>
    <div class="brand">CareCloud Medical<small>Patient Registration Voice Agent</small></div>
    <div class="live"><span class="d"></span>live</div>
  </header>

  <div class="hero">
    <div class="card">
      <h1>Register a new patient <span>by voice</span>.</h1>
      <p class="lead">Speak naturally with Savannah, our AI intake coordinator.
      She collects your demographic details, confirms them back to you, and saves
      your record — all over a normal conversation. Try it right now in your
      browser, or call the number.</p>

      <div class="meta">
        <div>📞 <b>{PHONE_NUMBER}</b></div>
        <div>🗂️ <a href="/dashboard">View registered patients →</a></div>
      </div>
      <p class="hint" style="margin-top:1.2rem">Tip: try correcting yourself
      mid-sentence, or give an unusual spelling — the agent handles it.</p>
    </div>

    <div class="card callcard">
      <div class="orb">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0
          1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0
          1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7
          2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1
          2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
      </div>
      <div>
        <div class="agent-name">Savannah</div>
        <div class="agent-role">Patient Intake Coordinator</div>
      </div>
      <button id="callBtn" class="btn">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round"><path d="M22 16.92v3a2 2 0 0 1-2.18
          2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2
          2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0
          1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339
          1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
        <span id="callLabel">Talk to Savannah</span>
      </button>
      <div class="status" id="status"></div>
      <div class="hint">Uses your microphone · no phone needed</div>
    </div>
  </div>

  <div class="section-title">Explore the system</div>
  <div class="grid">
    <a class="tile" href="/dashboard">
      <h3>🗂️ Patient Dashboard</h3>
      <p>Browse, search, add, and edit patient records in a table.</p></a>
    <a class="tile" href="/patients">
      <h3>🔌 <code>GET /patients</code></h3>
      <p>JSON REST API. Also POST, PUT, DELETE. Filter by name, DOB, phone.</p></a>
    <a class="tile" href="/docs">
      <h3>📖 API Docs</h3>
      <p>Interactive OpenAPI documentation — try every endpoint.</p></a>
    <a class="tile" href="/health">
      <h3>💚 <code>GET /health</code></h3>
      <p>Liveness probe used by the host and uptime checks.</p></a>
  </div>

  <footer>CareCloud Patient Registration · FastAPI · Vapi · PostgreSQL · Railway</footer>
</div>

<script>
const CALL_ENABLED = {call_enabled};
const PUBLIC_KEY = "{public_key}";
const ASSISTANT_ID = "{ASSISTANT_ID}";

const btn = document.getElementById('callBtn');
const label = document.getElementById('callLabel');
const status = document.getElementById('status');
let vapi = null, inCall = false, starting = false;

function setStatus(msg, err){{ status.textContent = msg; status.className = 'status' + (err ? ' err' : ''); }}

if(!CALL_ENABLED){{
  btn.disabled = true;
  setStatus('In-browser calling not configured — dial the number above, or set VAPI_PUBLIC_KEY.');
}}

// Load the official Vapi web SDK on demand, then start/stop calls.
function loadSDK(){{
  return new Promise((resolve, reject) => {{
    if(window.vapiSDK) return resolve(window.vapiSDK);
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/gh/VapiAI/html-script-tag@latest/dist/assets/index.js';
    s.async = true;
    s.onload = () => resolve(window.vapiSDK);
    s.onerror = () => reject(new Error('Could not load the voice SDK'));
    document.head.appendChild(s);
  }});
}}

async function initVapi(){{
  const sdk = await loadSDK();
  // run() returns a Vapi instance we can drive and subscribe to.
  vapi = sdk.run({{ apiKey: PUBLIC_KEY, assistant: ASSISTANT_ID, config: {{ hideButton: true }} }});
  vapi.on('call-start', () => {{ inCall = true; starting = false;
    document.body.classList.add('in-call');
    label.textContent = 'End call'; btn.classList.add('end');
    setStatus('Connected — say hello to Savannah.'); }});
  vapi.on('call-end', () => {{ inCall = false;
    document.body.classList.remove('in-call');
    label.textContent = 'Talk to Savannah'; btn.classList.remove('end');
    setStatus('Call ended.'); }});
  vapi.on('error', (e) => {{ starting = false;
    setStatus((e && e.message) ? e.message : 'Call error — please try again.', true); }});
}}

btn.addEventListener('click', async () => {{
  if(!CALL_ENABLED || starting) return;
  try{{
    if(inCall){{ vapi && vapi.stop(); return; }}
    starting = true; setStatus('Connecting… allow microphone access.');
    if(!vapi) await initVapi();
    await vapi.start(ASSISTANT_ID);
  }}catch(err){{
    starting = false;
    setStatus(err.message || 'Could not start the call.', true);
  }}
}});
</script>
</body></html>"""


@router.get("/", response_class=HTMLResponse)
async def landing() -> str:
    return _page()
