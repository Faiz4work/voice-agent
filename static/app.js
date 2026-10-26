/* No API secrets or customer details are persisted in browser storage. */
'use strict';
const $ = id => document.getElementById(id);
let profiles=[], current, config={}, sessionId=null, generation=0, pending=false, bookingKey=null;
let vapi=null, callState='idle', muted=false, voiceGeneration=0;
async function api(path, options={}) {
  const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...options.headers}});
  const body=await response.json();
  if(!response.ok){const error=new Error(body.error?.fields?.map(x=>`${x.field}: ${x.reason}`).join('; ')||body.error?.message||'Request failed');error.status=response.status;throw error;}
  return body.data;
}
function bubble(text, role='assistant') {
  const node=document.createElement('div');node.className='bubble '+role;node.textContent=text;
  $('messages').appendChild(node);$('messages').scrollTop=$('messages').scrollHeight;return node;
}
function formatTime(stamp){return new Intl.DateTimeFormat('en-US',{hour:'numeric',minute:'2-digit',timeZone:current.timezone}).format(new Date(stamp));}
function fullTime(stamp){return new Intl.DateTimeFormat('en-US',{dateStyle:'medium',timeStyle:'short',timeZone:current.timezone}).format(new Date(stamp))+' · '+current.timezone;}
function localDate(){const parts=new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:current.timezone}).formatToParts(new Date());const values=Object.fromEntries(parts.map(x=>[x.type,x.value]));return `${values.year}-${values.month}-${values.day}`;}
async function chooseBusiness(id){
  if(callState!=='idle') await endCall();
  const mine=++generation;current=profiles.find(x=>x.id===id)||profiles[0];sessionId=null;pending=false;
  document.querySelectorAll('[data-business]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.business===current.id)));
  $('business-name').textContent=current.name;$('business-tagline').textContent=current.tagline;$('industry').textContent=current.industry.toUpperCase();$('timezone').textContent=current.timezone;$('service-area').textContent=current.service_area;$('business-symbol').textContent=current.id==='medical'?'+':'⌁';
  $('assistant-name').textContent=(current.id==='medical'?'Savannah':'Alex')+' · Your receptionist';
  $('messages').replaceChildren();bubble(current.greeting);$('send').disabled=false;$('message').disabled=false;
  $('service').replaceChildren(...current.services.map(s=>new Option(s.name,s.id)));
  $('date').min=localDate();const maxDate=new Date($('date').min+'T12:00:00Z');maxDate.setUTCDate(maxDate.getUTCDate()+current.booking_days);$('date').max=maxDate.toISOString().slice(0,10);$('date').value=$('date').min;
  $('booking-form').reset();$('date').value=$('date').min;$('booking-result').textContent='';$('inquiry-result').textContent='';$('inquiry-form').reset();clearSlots();
  $('address-field').hidden=current.id!=='hvac';$('address').required=current.id==='hvac';$('voice-button').disabled=true;$('voice-consent').checked=false;config={};
  try{const result=await api('/api/config/'+current.id);if(mine!==generation)return;config=result;$('chat-mode').textContent=config.chat_mode==='ai'?'AI conversation · Business context connected':'Guided preview · Business context connected';$('voice-status').textContent=config.voice_message;$('voice-button').disabled=!config.voice_enabled;}
  catch(error){if(mine===generation){$('voice-status').textContent='Connection unavailable. Please refresh.';$('chat-mode').textContent='Connection unavailable';}}
}
async function sendMessage(text){
  if(pending||!current)return;const mine=generation;pending=true;$('send').disabled=true;$('message').disabled=true;bubble(text,'user');$('message').value='';const thinking=bubble('One moment…');
  try{const data=await api(`/api/${current.id}/chat`,{method:'POST',body:JSON.stringify({message:text,session_id:sessionId})});if(mine!==generation)return;sessionId=data.session_id;thinking.textContent=data.reply;
    for(const action of data.actions||[]){if(action.result?.id){const result=document.createElement('div');result.className='action';result.textContent=`Saved ${action.tool==='book_appointment'?'appointment':'callback'} · Reference ${action.result.id}`;thinking.appendChild(result);}}
  }catch(error){if(mine===generation){thinking.textContent=error.message;if(error.status===410)sessionId=null;}}
  finally{if(mine===generation){pending=false;$('send').disabled=false;$('message').disabled=false;$('message').focus();$('messages').scrollTop=$('messages').scrollHeight;}}
}
$('chat-form').addEventListener('submit',event=>{event.preventDefault();const text=$('message').value.trim();if(text)sendMessage(text);});
document.querySelectorAll('[data-question]').forEach(button=>button.addEventListener('click',()=>sendMessage(button.dataset.question)));
$('reset-chat').addEventListener('click',()=>{generation++;sessionId=null;pending=false;$('messages').replaceChildren();bubble(current.greeting);$('send').disabled=false;$('message').disabled=false;});
document.querySelectorAll('[data-business]').forEach(button=>button.addEventListener('click',()=>chooseBusiness(button.dataset.business)));
function clearSlots(){bookingKey=null;$('slots').replaceChildren();$('selected-slot').value='';$('slot-status').textContent='';$('contact-fields').hidden=true;$('confirm-booking').checked=false;}
$('service').addEventListener('change',clearSlots);$('date').addEventListener('change',clearSlots);
$('find-times').addEventListener('click',async()=>{
  if(!$('date').reportValidity())return;const mine=generation;const service=$('service').value,day=$('date').value;clearSlots();$('slot-status').textContent='Finding a good time…';$('find-times').disabled=true;
  try{const data=await api(`/api/${current.id}/availability?date=${encodeURIComponent(day)}&service_id=${encodeURIComponent(service)}`);if(mine!==generation||service!==$('service').value||day!==$('date').value)return;
    $('slot-status').textContent=data.slots.length?`Times shown in ${data.timezone}. Select one to continue.`:'No openings this day. Please try another day.';
    data.slots.forEach(stamp=>{const button=document.createElement('button');button.type='button';button.textContent=formatTime(stamp);button.setAttribute('aria-pressed','false');button.addEventListener('click',()=>{document.querySelectorAll('#slots button').forEach(x=>x.setAttribute('aria-pressed','false'));button.setAttribute('aria-pressed','true');$('selected-slot').value=stamp;bookingKey=crypto.randomUUID();$('contact-fields').hidden=false;$('confirm-booking').checked=false;$('booking-summary').textContent=current.services.find(x=>x.id===$('service').value).name+' · '+fullTime(stamp);});$('slots').appendChild(button);});
  }catch(error){if(mine===generation)$('slot-status').textContent=error.message;}finally{$('find-times').disabled=false;}
});
$('booking-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!$('selected-slot').value)return;const mine=generation;$('book-button').disabled=true;$('booking-result').textContent='Saving your demo appointment…';
  const payload={service_id:$('service').value,starts_at:$('selected-slot').value,customer_name:$('customer-name').value,phone:$('phone').value,email:$('email').value||null,address:current.id==='hvac'?$('address').value:null,confirmed:$('confirm-booking').checked,idempotency_key:bookingKey};
  try{const data=await api(`/api/${current.id}/bookings`,{method:'POST',body:JSON.stringify(payload)});if(mine!==generation)return;$('booking-result').textContent=`Demo appointment ${data.status}: ${fullTime(data.starts_at)}. Reference: ${data.id}. No email or SMS has been sent.`;clearSlots();$('customer-name').value='';$('phone').value='';$('email').value='';$('address').value='';}
  catch(error){if(mine===generation){$('booking-result').textContent=error.message;if(error.status===409)clearSlots();}}
  finally{$('book-button').disabled=false;}
});
$('inquiry-form').addEventListener('submit',async event=>{event.preventDefault();const mine=generation;const button=event.submitter;button.disabled=true;
  try{const data=await api(`/api/${current.id}/inquiries`,{method:'POST',body:JSON.stringify({customer_name:$('inquiry-name').value,phone:$('inquiry-phone').value,message:$('inquiry-message').value,consent:$('inquiry-consent').checked})});if(mine===generation){$('inquiry-result').textContent=data.message+' Reference: '+data.id;$('inquiry-form').reset();}}
  catch(error){if(mine===generation)$('inquiry-result').textContent=error.message;}finally{button.disabled=false;}
});
function voiceReset(message){callState='idle';muted=false;$('voice-button').textContent='Start a voice call ↗';$('voice-button').disabled=!config.voice_enabled;$('mute-button').hidden=true;$('mute-button').textContent='Mute microphone';$('voice-status').textContent=message||'Call ended. Thanks for trying the demo.';}
async function endCall(){voiceGeneration++;try{if(vapi)await vapi.stop();}catch{}finally{voiceReset();}}
$('voice-button').addEventListener('click',async()=>{
  if(callState!=='idle'){await endCall();return;}
  if(!$('voice-consent').checked){$('voice-status').textContent='Please agree to microphone processing before starting.';return;}
  if(!window.isSecureContext||!navigator.mediaDevices){$('voice-status').textContent='Voice requires HTTPS or localhost and a browser with microphone support.';return;}
  const attempt=++voiceGeneration;callState='connecting';$('voice-button').disabled=true;$('voice-status').textContent='Connecting to your receptionist…';
  try{const {default:Vapi}=await import('/static/vendor/vapi.js');if(attempt!==voiceGeneration)return;
    if(vapi)await vapi.stop();vapi=new Vapi(config.vapi_public_key, undefined, {avoidEval:true});const callClient=vapi;
    vapi.on('call-start',()=>{if(attempt!==voiceGeneration)return;callState='active';$('voice-button').disabled=false;$('voice-button').textContent='End voice call';$('mute-button').hidden=false;$('voice-status').textContent='Connected · You can speak now.';});
    vapi.on('call-end',()=>{if(attempt===voiceGeneration)voiceReset();});
    vapi.on('speech-start',()=>{if(attempt===voiceGeneration)$('voice-status').textContent='Your receptionist is speaking…';});
    vapi.on('speech-end',()=>{if(attempt===voiceGeneration)$('voice-status').textContent='Listening…';});
    vapi.on('message',message=>{if(attempt===voiceGeneration&&message.type==='transcript'&&message.transcriptType==='final')bubble(message.transcript,message.role==='user'?'user':'assistant');});
    vapi.on('error',()=>{if(attempt===voiceGeneration){voiceGeneration++;Promise.resolve(callClient.stop()).catch(()=>{});voiceReset('The call could not connect. Check microphone access and Vapi configuration, then try again.');}});
    // Saved assistant holds the authenticated server URL. Never put webhook secrets or server overrides in browser code.
    $('voice-button').disabled=false;$('voice-button').textContent='Cancel connection';
    await callClient.start(config.assistant_id);
    if(attempt!==voiceGeneration)await callClient.stop();
  }catch(error){if(attempt===voiceGeneration)voiceReset('Voice connection unavailable. Check microphone permissions, connectivity and Vapi setup.');}
});
$('mute-button').addEventListener('click',()=>{muted=!muted;vapi.setMuted(muted);$('mute-button').textContent=muted?'Unmute microphone':'Mute microphone';});
window.addEventListener('pagehide',()=>{if(vapi)vapi.stop();});
(async()=>{try{profiles=await api('/api/businesses');await chooseBusiness(location.pathname==='/medical'?'medical':'hvac');}catch(error){$('chat-mode').textContent='Server unavailable';$('voice-status').textContent=error.message;}})();
