"""Explicit, billable live Vapi browser test using synthetic microphone input.
Run only after preparing artifacts/voice-input.wav and configuring Vapi.
"""
import argparse
import base64
import json
import time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import setting

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--book',action='store_true',help='Also verify one fictional booking and cancel it afterwards')
parser.add_argument('--run',action='store_true',help='Authorize one live call using Vapi credits')
args=parser.parse_args()
if not args.run:parser.error('Pass --run to start the billable live test.')
root=Path(__file__).resolve().parents[1]
report={'connected':False,'call_id':None,'transcripts':[],'errors':[],'audio_tracks':[],'gateway_stats':{},'public_api_statuses':[],'console_errors':[],'progress':[]}
booking_data=None
if args.book:
    from reception import availability,now_for
    from datetime import timedelta
    for offset in range(1,8):
        slots=availability('hvac',now_for('hvac').date()+timedelta(days=offset),'ac-repair')['slots']
        if slots:
            booking_data={'starts_at':slots[0],'customer_name':'Vapi Integration Test','phone':'5125550197','address':'123 Demo Lane, Austin, TX 78701'}
            break
    assert booking_data
started=time.monotonic()
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--use-file-for-fake-audio-capture='+str(root/'artifacts/voice-input.wav'),'--autoplay-policy=no-user-gesture-required'])
    context=browser.new_context(permissions=['microphone'],viewport={'width':1440,'height':1000})
    page=context.new_page()
    def response_seen(response):
        if response.url.startswith('https://api.vapi.ai/'):
            report['public_api_statuses'].append(response.status)
            if '/call/web' in response.url:
                try:report['call_id']=response.json().get('id')
                except Exception:pass
    page.on('response',response_seen)
    page.on('console',lambda message:report['console_errors'].append(message.text[:700]) if message.type=='error' else None)
    try:
        page.goto('http://127.0.0.1:8000',wait_until='networkidle')
        page.wait_for_function("document.querySelector('#voice-button').disabled === false",timeout=10000)
        # Keep the normal saved assistant and authenticated URL; only cap this test's call duration.
        page.evaluate("""async()=>{const {default:Vapi}=await import('/static/vendor/vapi.js');const original=Vapi.prototype.start;Vapi.prototype.start=function(id,overrides,...rest){return original.call(this,id,{...overrides,maxDurationSeconds:120},...rest);};window.liveProbe={events:[],transcripts:[],errors:[],progress:[]};}""")
        if args.book:
            encoded=base64.b64encode((root/'artifacts/voice-question.wav').read_bytes()).decode()
            page.evaluate("""async encoded=>{const ctx=new AudioContext();await ctx.resume();const destination=ctx.createMediaStreamDestination();const oscillator=ctx.createOscillator();const gain=ctx.createGain();gain.gain.value=0.00001;oscillator.connect(gain);gain.connect(destination);gain.connect(ctx.destination);oscillator.start();const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));const buffer=await ctx.decodeAudioData(bytes.buffer);window.testSpeech={ctx,destination,buffer,oscillator};navigator.mediaDevices.getUserMedia=async()=>destination.stream.clone();}""",encoded)
        page.locator('#voice-consent').check()
        page.locator('#voice-button').click()
        page.wait_for_function("typeof vapi!=='undefined' && vapi!==null",timeout=15000)
        page.evaluate("""()=>{vapi.on('call-start-progress',event=>liveProbe.progress.push({stage:event.stage,status:event.status,duration:event.duration}));vapi.on('call-start',()=>liveProbe.events.push('call-start'));vapi.on('call-end',()=>liveProbe.events.push('call-end'));vapi.on('message',message=>{if(message.type==='transcript'&&message.transcriptType==='final')liveProbe.transcripts.push({role:message.role,text:message.transcript});});vapi.on('error',error=>liveProbe.errors.push({type:error.type||'error',status:error.statusCode||error.status||null,message:error.errorMsg||error.message||error.error?.message||String(error.error||''),stage:error.stage||null}));}""")
        sent_availability=False
        booking_sent_at=None
        confirmation_sent=False
        while time.monotonic()-started < 115:
            page.wait_for_timeout(1000)
            state=page.evaluate('liveProbe')
            if 'call-start' in state['events'] and not report['connected']:
                report['connected']=True
                print('Live browser voice call connected.',flush=True)
                # Inject the synthetic question after joining, so microphone preflight
                # cannot consume the file before the assistant starts listening.
                if args.book:
                    page.evaluate("()=>{const source=testSpeech.ctx.createBufferSource();source.buffer=testSpeech.buffer;source.connect(testSpeech.destination);source.start(testSpeech.ctx.currentTime+2);testSpeech.source=source;vapi.setMuted(false);}")
                else:
                    wav=base64.b64encode((root/'artifacts/voice-question.wav').read_bytes()).decode()
                    page.evaluate("""async encoded=>{const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));const ctx=new AudioContext();await ctx.resume();const buffer=await ctx.decodeAudioData(bytes.buffer);const source=ctx.createBufferSource();source.buffer=buffer;const destination=ctx.createMediaStreamDestination();source.connect(destination);window.testSpeech={ctx,source,destination};source.start(ctx.currentTime+2);await Promise.race([vapi.setInputDevicesAsync({audioSource:destination.stream.getAudioTracks()[0]}),new Promise(resolve=>setTimeout(resolve,8000))]);}""",wav)
                print('Injected synthetic speech into the live microphone track.',flush=True)
            if state['errors']:
                report['errors']=state['errors'];break
            # First turn is an actual synthetic microphone question through speech recognition.
            if report['connected'] and not sent_availability and time.monotonic()-started > 27:
                page.evaluate("vapi.send({type:'add-message',message:{role:'user',content:'Please check your live availability for AC repair tomorrow. Do not book anything.'},triggerResponseEnabled:true})")
                sent_availability=True
                print('Requested live appointment availability.',flush=True)
            if args.book and report['connected'] and booking_sent_at is None and time.monotonic()-started > 43:
                message='Please book a fictional AC repair visit for '+booking_data['starts_at']+' America/Chicago. My name is '+booking_data['customer_name']+', phone '+booking_data['phone']+', service address '+booking_data['address']+'. No email. First read all details back and ask me to confirm before saving it.'
                page.evaluate("message=>vapi.send({type:'add-message',message:{role:'user',content:message},triggerResponseEnabled:true})",message)
                booking_sent_at=time.monotonic()
                print('Requested a fictional booking with read-back confirmation.',flush=True)
            if args.book and booking_sent_at and not confirmation_sent and time.monotonic()-booking_sent_at > 26:
                rows=httpx.get('http://127.0.0.1:8000/api/admin/hvac/bookings',headers={'Authorization':'Bearer '+setting('ADMIN_API_KEY')}).json()['data']
                report['no_booking_before_confirmation']=not any(row['customer_name']==booking_data['customer_name'] and row['status']=='confirmed' for row in rows)
                page.evaluate("vapi.send({type:'add-message',message:{role:'user',content:'Yes, I confirm those exact details. Please save this fictional demo appointment now.'},triggerResponseEnabled:true})")
                confirmation_sent=True
                print('Confirmed the fictional booking.',flush=True)
            if args.book and confirmation_sent:
                rows=httpx.get('http://127.0.0.1:8000/api/admin/hvac/bookings',headers={'Authorization':'Bearer '+setting('ADMIN_API_KEY')}).json()['data']
                created=next((row for row in rows if row['customer_name']==booking_data['customer_name'] and row['status']=='confirmed'),None)
                if created:
                    report['confirmed_booking']={key:created[key] for key in ['id','starts_at','service_id','status']}
                    cleanup=httpx.delete('http://127.0.0.1:8000/api/admin/hvac/bookings/'+created['id'],headers={'Authorization':'Bearer '+setting('ADMIN_API_KEY')})
                    report['test_booking_cancelled']=cleanup.is_success
                    print('Confirmed booking found in database and cancelled after verification.',flush=True)
                    break
            if not args.book and sent_availability and time.monotonic()-started > 75:
                break
            if 'call-end' in state['events']:break
        state=page.evaluate('liveProbe');report['transcripts']=state['transcripts'];report['errors']=state['errors']
        report['progress']=state['progress']
        report['ui_status']=page.locator('#voice-status').inner_text()
        report['audio_tracks']=page.evaluate("Array.from(document.querySelectorAll('audio')).map(a=>({readyState:a.readyState,paused:a.paused,currentTime:a.currentTime,tracks:a.srcObject?.getAudioTracks().map(t=>({readyState:t.readyState,enabled:t.enabled}))||[]}))")
        page.screenshot(path=str(root/'artifacts/vapi-live-browser.png'),full_page=True)
    except Exception as exc:
        report['test_error']=type(exc).__name__+': '+str(exc).splitlines()[0][:180]
    finally:
        try:page.evaluate("async()=>{if(typeof vapi!=='undefined'&&vapi)await vapi.stop();}")
        except Exception:pass
        browser.close()
try:
    response=httpx.get('http://127.0.0.1:8001/_test_stats',headers={'Authorization':'Bearer '+setting('VAPI_WEBHOOK_SECRET')},timeout=10)
    if response.is_success:report['gateway_stats']=response.json()
except httpx.HTTPError:pass
if report['call_id']:
    try:
        response=httpx.get('https://api.vapi.ai/call/'+report['call_id'],headers={'Authorization':'Bearer '+setting('VAPI_API_KEY')},timeout=20)
        if response.is_success:
            data=response.json()
            report['provider_call']={key:data.get(key) for key in ['status','endedReason','cost','startedAt','endedAt']}
    except httpx.HTTPError:pass
# Strip the browser key from diagnostics if a provider includes it in an error URL.
for key in ['VAPI_PUBLIC_KEY','VAPI_API_KEY','VAPI_WEBHOOK_SECRET']:
    value=setting(key)
    if value:report=json.loads(json.dumps(report).replace(value,'[REDACTED]'))
(root/('artifacts/vapi-live-booking-report.json' if args.book else 'artifacts/vapi-live-report.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
