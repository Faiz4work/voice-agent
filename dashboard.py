"""Bonus: a small read/write web UI over the patient records.

Deliberately kept separate from the JSON API — this module only serves HTML at
/dashboard, while /patients stays a pure JSON REST surface. The page is a
single self-contained file (no build step, no CDN) that talks to the same
public API a reviewer would use with curl, so nothing here is a private
back-channel into the database.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CareCloud — Registered Patients</title>
<style>
:root{
  --bg:#0b0f14; --panel:#111820; --line:#1f2b38; --text:#e6edf3;
  --muted:#8b98a5; --accent:#3ddc97; --danger:#ff6b6b; --input:#0c1218;
}
@media (prefers-color-scheme: light){
  :root{--bg:#f6f8fa;--panel:#fff;--line:#d8dee4;--text:#1f2328;
        --muted:#636c76;--accent:#1a7f5a;--danger:#c93c37;--input:#fff}
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
     font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;padding:2rem 1.25rem}
.wrap{max-width:1200px;margin:0 auto}
header{display:flex;flex-wrap:wrap;gap:.75rem;align-items:baseline;
       justify-content:space-between;margin-bottom:.35rem}
h1{font-size:1.5rem;margin:0}
.sub{color:var(--muted);font-size:.9rem;margin-bottom:1.5rem}
.bar{display:flex;flex-wrap:wrap;gap:.6rem;margin-bottom:1rem}
input,select,button{font:inherit;padding:.5rem .7rem;border-radius:8px;
  border:1px solid var(--line);background:var(--input);color:var(--text)}
input:focus,select:focus{outline:2px solid var(--accent);outline-offset:1px}
button{cursor:pointer;background:var(--panel)}
button.primary{background:var(--accent);color:#04150e;border-color:transparent;
               font-weight:600}
button.link{background:none;border:none;color:var(--accent);padding:.25rem .4rem}
button.link.danger{color:var(--danger)}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:12px;
        background:var(--panel)}
table{border-collapse:collapse;width:100%;min-width:900px}
th,td{padding:.65rem .75rem;text-align:left;border-bottom:1px solid var(--line);
      white-space:nowrap}
th{font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;
   color:var(--muted);position:sticky;top:0;background:var(--panel)}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:rgba(127,127,127,.07)}
tr.deleted{opacity:.45;text-decoration:line-through}
.count{color:var(--muted);font-size:.85rem}
.empty{padding:3rem 1rem;text-align:center;color:var(--muted)}
dialog{border:1px solid var(--line);border-radius:14px;background:var(--panel);
       color:var(--text);padding:0;width:min(560px,94vw)}
dialog::backdrop{background:rgba(0,0,0,.6)}
.dlg-body{padding:1.25rem;max-height:70vh;overflow:auto}
.dlg-foot{display:flex;gap:.6rem;justify-content:flex-end;padding:1rem 1.25rem;
          border-top:1px solid var(--line)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
.grid label{display:flex;flex-direction:column;gap:.25rem;font-size:.78rem;
            color:var(--muted)}
.grid input,.grid select{width:100%}
.full{grid-column:1/-1}
.err{color:var(--danger);font-size:.85rem;margin:.5rem 0 0;white-space:pre-wrap}
.toast{position:fixed;bottom:1.25rem;left:50%;transform:translateX(-50%);
  background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
  padding:.7rem 1.1rem;border-radius:10px;opacity:0;transition:opacity .25s;
  pointer-events:none;max-width:90vw}
.toast.show{opacity:1}
.toast.bad{border-left-color:var(--danger)}
</style></head><body><div class="wrap">

<header>
  <h1>Registered Patients</h1>
  <span class="count" id="count"></span>
</header>
<p class="sub">Reads and writes through the same public REST API
(<code>/patients</code>). Records can be created and corrected here
independently of the voice agent.</p>

<div class="bar">
  <input id="q-last" placeholder="Last name">
  <input id="q-phone" placeholder="Phone number">
  <input id="q-dob" placeholder="DOB (MM/DD/YYYY)">
  <button onclick="load()">Search</button>
  <button onclick="clearFilters()">Clear</button>
  <label style="display:flex;align-items:center;gap:.4rem;color:var(--muted)">
    <input type="checkbox" id="q-del" onchange="load()" style="width:auto">
    show deleted
  </label>
  <button class="primary" onclick="openForm()">+ New patient</button>
</div>

<div class="scroll">
  <table>
    <thead><tr>
      <th>Name</th><th>DOB</th><th>Sex</th><th>Phone</th><th>Address</th>
      <th>Email</th><th>Insurance</th><th>Registered</th><th></th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <div class="empty" id="empty" hidden>No patients yet — call the agent or add one.</div>
</div>

<dialog id="dlg">
  <form method="dialog" onsubmit="return false">
    <div class="dlg-body">
      <h3 id="dlg-title" style="margin:0 0 1rem">New patient</h3>
      <div class="grid">
        <label>First name*<input id="f-first_name"></label>
        <label>Last name*<input id="f-last_name"></label>
        <label>Date of birth*<input id="f-date_of_birth" placeholder="MM/DD/YYYY"></label>
        <label>Sex*<select id="f-sex">
          <option>Male</option><option>Female</option>
          <option>Other</option><option>Decline to Answer</option></select></label>
        <label>Phone*<input id="f-phone_number" placeholder="10 digits"></label>
        <label>Email<input id="f-email"></label>
        <label class="full">Address line 1*<input id="f-address_line_1"></label>
        <label class="full">Address line 2<input id="f-address_line_2"></label>
        <label>City*<input id="f-city"></label>
        <label>State*<input id="f-state" maxlength="2" placeholder="CA"></label>
        <label>ZIP*<input id="f-zip_code"></label>
        <label>Preferred language<input id="f-preferred_language"></label>
        <label>Insurance provider<input id="f-insurance_provider"></label>
        <label>Member ID<input id="f-insurance_member_id"></label>
        <label>Emergency contact<input id="f-emergency_contact_name"></label>
        <label>Emergency phone<input id="f-emergency_contact_phone"></label>
      </div>
      <p class="err" id="err"></p>
    </div>
    <div class="dlg-foot">
      <button onclick="dlg.close()">Cancel</button>
      <button class="primary" onclick="save()">Save</button>
    </div>
  </form>
</dialog>

<div class="toast" id="toast"></div>
</div>

<script>
const $ = id => document.getElementById(id);
const dlg = $('dlg');
const FIELDS = ['first_name','last_name','date_of_birth','sex','phone_number',
  'email','address_line_1','address_line_2','city','state','zip_code',
  'preferred_language','insurance_provider','insurance_member_id',
  'emergency_contact_name','emergency_contact_phone'];
let editingId = null;

const esc = s => String(s ?? '').replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function toast(msg, bad){
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast show' + (bad ? ' bad' : '');
  setTimeout(() => t.className = 'toast', 3200);
}

function fmtPhone(p){
  return p && p.length === 10 ? `(${p.slice(0,3)}) ${p.slice(3,6)}-${p.slice(6)}` : (p || '');
}
function fmtDate(d){
  if(!d) return '';
  const [y,m,dd] = d.split('-');
  return m ? `${m}/${dd}/${y}` : d;
}

async function load(){
  const p = new URLSearchParams();
  if($('q-last').value.trim())  p.set('last_name',    $('q-last').value.trim());
  if($('q-phone').value.trim()) p.set('phone_number', $('q-phone').value.trim());
  if($('q-dob').value.trim())   p.set('date_of_birth',$('q-dob').value.trim());
  if($('q-del').checked)        p.set('include_deleted','true');

  let json;
  try{
    const r = await fetch('/patients?' + p);
    json = await r.json();
    if(json.error){ toast(json.error.message, true); return; }
  }catch(e){ toast('Could not reach the API', true); return; }

  const rows = json.data || [];
  $('count').textContent = rows.length + (rows.length === 1 ? ' patient' : ' patients');
  $('empty').hidden = rows.length > 0;
  $('rows').innerHTML = rows.map(r => `
    <tr class="${r.deleted_at ? 'deleted' : ''}">
      <td><strong>${esc(r.first_name)} ${esc(r.last_name)}</strong></td>
      <td>${esc(fmtDate(r.date_of_birth))}</td>
      <td>${esc(r.sex)}</td>
      <td>${esc(fmtPhone(r.phone_number))}</td>
      <td>${esc([r.address_line_1, r.address_line_2, r.city, r.state, r.zip_code]
                .filter(Boolean).join(', '))}</td>
      <td>${esc(r.email)}</td>
      <td>${esc(r.insurance_provider)}</td>
      <td>${esc(new Date(r.created_at).toLocaleString())}</td>
      <td style="text-align:right">
        ${r.deleted_at ? '<span class="count">deleted</span>' : `
          <button class="link" onclick='openForm(${JSON.stringify(r)})'>Edit</button>
          <button class="link danger" onclick="del('${r.patient_id}')">Delete</button>`}
      </td>
    </tr>`).join('');
}

function clearFilters(){
  $('q-last').value = $('q-phone').value = $('q-dob').value = '';
  $('q-del').checked = false;
  load();
}

function openForm(rec){
  editingId = rec ? rec.patient_id : null;
  $('dlg-title').textContent = rec ? 'Edit patient' : 'New patient';
  $('err').textContent = '';
  FIELDS.forEach(f => {
    const el = $('f-' + f);
    if(!el) return;
    el.value = rec ? (f === 'date_of_birth' ? fmtDate(rec[f]) : (rec[f] ?? '')) : '';
  });
  if(!rec) $('f-preferred_language').value = 'English';
  dlg.showModal();
}

async function save(){
  const body = {};
  FIELDS.forEach(f => {
    const v = ($('f-' + f)?.value || '').trim();
    if(v) body[f] = v;
  });
  const url = editingId ? '/patients/' + editingId : '/patients';
  const r = await fetch(url, {
    method: editingId ? 'PUT' : 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });
  const j = await r.json();
  if(!r.ok){
    // Surface the API's own field-level validation messages.
    const f = j.error?.fields;
    $('err').textContent = f
      ? f.map(x => `• ${x.field}: ${x.reason}`).join('\\n')
      : (j.error?.message || 'Save failed');
    return;
  }
  dlg.close();
  toast(editingId ? 'Patient updated' : 'Patient created');
  load();
}

async function del(id){
  if(!confirm('Soft-delete this patient? The record is retained, not erased.')) return;
  const r = await fetch('/patients/' + id, {method:'DELETE'});
  toast(r.ok ? 'Patient soft-deleted' : 'Delete failed', !r.ok);
  load();
}

load();
</script></body></html>"""


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> str:
    return PAGE
