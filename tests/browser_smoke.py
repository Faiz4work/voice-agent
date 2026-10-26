"""End-to-end checks against a running isolated demo server at localhost:8000."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'artifacts'
OUTPUT.mkdir(exist_ok=True)
BASE='http://127.0.0.1:8000'

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE)
    expect(page.locator('#chat-mode')).to_contain_text('Guided preview')
    expect(page.locator('#voice-button')).to_be_disabled()
    # Load the actual SDK and verify packaging without connecting to a provider.
    assert page.evaluate("async()=>typeof (await import('/static/vendor/vapi.js')).default")== 'function'
    page.get_by_role('button',name='Opening hours').click()
    expect(page.locator('#messages')).to_contain_text('Monday')
    page.locator('#message').fill('What does it cost?')
    page.locator('#send').click()
    expect(page.locator('#messages')).to_contain_text('quote after diagnosis')

    # Find a future opening via the same live API the interface uses.
    from datetime import datetime,timedelta
    from zoneinfo import ZoneInfo
    first=datetime.now(ZoneInfo('America/Chicago')).date()+timedelta(days=1)
    day=None
    for offset in range(7):
        candidate=(first+timedelta(days=offset)).isoformat()
        response=page.request.get(BASE+'/api/hvac/availability',params={'date':candidate,'service_id':'ac-repair'}).json()['data']
        if response['slots']:day=candidate;break
    assert day
    page.locator('#date').fill(day)
    page.locator('#find-times').click()
    expect(page.locator('#slots button').first).to_be_visible()
    page.locator('#slots button').first.click()
    page.locator('#customer-name').fill('Browser Demo')
    page.locator('#phone').fill('5125550199')
    page.locator('#address').fill('123 Fictional Demo Lane, Austin TX')
    page.locator('#confirm-booking').check()
    page.locator('#book-button').click()
    expect(page.locator('#booking-result')).to_contain_text('Demo appointment confirmed')
    page.locator('details.callback summary').click()
    page.locator('#inquiry-name').fill('Browser Callback')
    page.locator('#inquiry-phone').fill('5125550199')
    page.locator('#inquiry-message').fill('Please call about fictional HVAC maintenance.')
    page.locator('#inquiry-consent').check()
    page.locator('#inquiry-form button').click()
    expect(page.locator('#inquiry-result')).to_contain_text('callback request is saved')
    page.screenshot(path=str(OUTPUT/'desktop-hvac.png'),full_page=True)
    page.locator('[data-business=medical]').click()
    expect(page.locator('#business-name')).to_have_text('CareCloud Medical')
    expect(page.locator('#address-field')).to_be_hidden()
    page.get_by_role('button',name='Opening hours').click()
    expect(page.locator('#messages')).to_contain_text('Monday')

    page.goto(BASE+'/staff')
    page.locator('#key').fill('browser-test-admin')
    page.locator('#access button[type=submit], #access button:not([type])').first.click()
    expect(page.locator('#bookings')).to_contain_text('Browser Demo')
    expect(page.locator('#inquiries')).to_contain_text('Browser Callback')
    # Browser confirmation is intentionally handled only for this explicit test action.
    page.once('dialog',lambda dialog:dialog.accept())
    page.get_by_role('button',name='Cancel appointment').click()
    expect(page.locator('#bookings')).to_contain_text('cancelled')
    page.locator('#lock').click()
    expect(page.locator('#bookings')).to_be_empty()

    # Patient dashboard: authentication and escaped apostrophes in original edit flow.
    patient={'first_name':'Demo','last_name':"O'Example",'date_of_birth':'1990-01-02','sex':'Other','phone_number':'5125550198','address_line_1':'123 Example Lane','city':'Austin','state':'TX','zip_code':'78701'}
    result=page.request.post(BASE+'/patients',data=patient,headers={'Authorization':'Bearer browser-test-admin'})
    assert result.status==201
    page.goto(BASE+'/dashboard')
    page.locator('#staff-key').fill('browser-test-admin')
    page.locator('#unlock').click()
    expect(page.locator('#rows')).to_contain_text("O'Example")
    page.get_by_role('button',name='Edit',exact=True).click()
    expect(page.locator('#f-last_name')).to_have_value("O'Example")

    for width,label in [(390,'mobile'),(768,'tablet')]:
        responsive=browser.new_page(viewport={'width':width,'height':844},device_scale_factor=1,is_mobile=width<500,has_touch=width<500)
        responsive.on('pageerror',lambda error:errors.append(str(error)))
        responsive.goto(BASE)
        expect(responsive.locator('#chat-mode')).to_contain_text('Guided preview')
        assert responsive.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),label+' layout overflow'
        responsive.get_by_role('button',name='Opening hours').click()
        expect(responsive.locator('#messages')).to_contain_text('Monday')
        responsive.screenshot(path=str(OUTPUT/(label+'-hvac.png')),full_page=True)
        responsive.close()

    # Simulate only the Vapi browser SDK to verify UI state transitions without a billable call.
    voice=browser.new_page(viewport={'width':1200,'height':900})
    voice.on('pageerror',lambda error:errors.append(str(error)))
    voice.route('**/api/config/*',lambda route:route.fulfill(json={'data':{'chat_mode':'guided','voice_enabled':True,'vapi_public_key':'mock-public-key','assistant_id':'mock-assistant','voice_message':'Ready to connect'}}))
    sdk="""export default class Vapi { constructor(){this.events={};globalThis.testVapi=this;} on(name,fn){this.events[name]=fn;} async start(id){globalThis.startedAssistant=id;this.events['call-start']();this.events.message({type:'transcript',transcriptType:'final',role:'assistant',transcript:'Simulated Vapi greeting'});} async stop(){this.events['call-end']?.();} setMuted(value){globalThis.mockMuted=value;} }"""
    voice.route('**/static/vendor/vapi.js',lambda route:route.fulfill(body=sdk,content_type='application/javascript'))
    voice.goto(BASE)
    expect(voice.locator('#voice-button')).to_be_enabled()
    voice.locator('#voice-button').click()
    expect(voice.locator('#voice-status')).to_contain_text('Please agree')
    voice.locator('#voice-consent').check()
    voice.locator('#voice-button').click()
    expect(voice.locator('#voice-status')).to_contain_text('Connected')
    assert voice.evaluate('globalThis.startedAssistant')=='mock-assistant'
    expect(voice.locator('#messages')).to_contain_text('Simulated Vapi greeting')
    voice.locator('#mute-button').click()
    assert voice.evaluate('globalThis.mockMuted') is True
    voice.locator('#voice-button').click()
    expect(voice.locator('#voice-status')).to_contain_text('Call ended')
    assert not errors,errors
    browser.close()
print(json.dumps({'status':'passed','checks':['guided chat','business switching','live availability','booking confirmation','callback inquiry','staff authentication','staff cancellation','patient dashboard apostrophe edit','mobile layout','tablet layout','Vapi consent/start/transcript/mute/end (mock SDK)'],'screenshots':str(OUTPUT),'real_voice_tested':False},indent=2))
