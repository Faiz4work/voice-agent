import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from main import app
from models import SessionLocal, Patient
from reception import now_for, availability, BookingInput, book
from reception_models import Appointment, Inquiry
import chatbot
import tools

ADMIN={'Authorization':'Bearer test-admin-key'}
VAPI={'Authorization':'Bearer test-webhook-key'}
PATIENT={'first_name':'Demo','last_name':"O'Example",'date_of_birth':'1990-01-02','sex':'Other','phone_number':'5125550198','address_line_1':'123 Example Lane','city':'Austin','state':'TX','zip_code':'78701'}

def opening(business='hvac'):
    service='ac-repair' if business=='hvac' else 'consultation'
    for n in range(1,8):
        result=availability(business,now_for(business).date()+timedelta(days=n),service)
        if result['slots']:return service,result['slots'][0]
    raise AssertionError('Expected a future opening')

def booking(business='hvac',key='test-booking-0001'):
    service,stamp=opening(business)
    return {'service_id':service,'starts_at':stamp,'customer_name':'Demo Customer','phone':'5125550199','address':'123 Demo Street','email':None,'confirmed':True,'idempotency_key':key}

def tool_event(name,args,kind='toolCallList'):
    return {'message':{'type':'tool-calls',kind:[{'id':'tool-1','function':{'name':name,'arguments':args}}]}}

def test_health_pages_and_no_secret_exposure(client,monkeypatch):
    assert client.get('/health').json()=={'status':'ok'}
    for path in ('/','/medical','/hvac','/staff','/dashboard'):
        r=client.get(path)
        assert r.status_code==200
        assert 'test-admin-key' not in r.text and 'test-webhook-key' not in r.text
        assert r.headers['cache-control']=='no-store'
        assert r.headers['x-content-type-options']=='nosniff'
    config=client.get('/api/config/hvac').json()['data']
    assert config['chat_mode']=='guided' and not config['voice_enabled']
    monkeypatch.setenv('VAPI_PUBLIC_KEY','public-demo')
    monkeypatch.setenv('VAPI_HVAC_ASSISTANT_ID','hvac-demo')
    assert client.get('/api/config/hvac').json()['data']['voice_enabled']

@pytest.mark.parametrize('method,path', [('GET','/patients'),('POST','/patients'),('PUT','/patients/demo'),('DELETE','/patients/demo'),('GET','/api/admin/hvac/bookings'),('GET','/api/admin/medical/inquiries'),('POST','/webhook'),('POST','/webhook/hvac'),('POST','/chat/completions')])
def test_private_routes_reject_anonymous(client,method,path):
    assert client.request(method,path,json={}).status_code==401

def test_auth_fails_closed_without_secrets(client,monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY','')
    monkeypatch.setenv('VAPI_WEBHOOK_SECRET','')
    assert client.get('/patients').status_code==503
    assert client.post('/webhook',json={}).status_code==503

def test_patient_crud_and_validation_preserved(client):
    assert client.post('/patients',headers=ADMIN,json={**PATIENT,'date_of_birth':'2999-01-01'}).status_code==422
    r=client.post('/patients',headers=ADMIN,json=PATIENT)
    assert r.status_code==201
    pid=r.json()['data']['patient_id']
    assert client.get('/patients/'+pid,headers=ADMIN).json()['data']['last_name']=="O'Example"
    assert client.put('/patients/'+pid,headers=ADMIN,json={'city':'Round Rock'}).json()['data']['city']=='Round Rock'
    assert client.delete('/patients/'+pid,headers=ADMIN).status_code==200
    assert client.get('/patients/'+pid,headers=ADMIN).status_code==404
    assert client.get('/patients',headers=ADMIN).json()['data']==[]

def test_medical_voice_intake_and_identity_verification(client,caplog):
    result=client.post('/webhook',headers=VAPI,json=tool_event('register_patient',PATIENT)).json()['results'][0]['result']
    assert result.startswith('SUCCESS')
    assert 'Demo' not in caplog.text and '5125550198' not in caplog.text
    assert tools.lookup_patient({'phone_number':PATIENT['phone_number']}).startswith('UNVERIFIED')
    verified=tools.lookup_patient({k:PATIENT[k] for k in ('phone_number','last_name','date_of_birth')})
    assert verified.startswith('FOUND')
    with SessionLocal() as db:pid=db.scalar(select(Patient.patient_id))
    assert tools.update_patient({'patient_id':pid,'city':'Houston'}).startswith('UNVERIFIED')
    assert tools.update_patient({'patient_id':pid,'verify_last_name':PATIENT['last_name'],'verify_date_of_birth':PATIENT['date_of_birth'],'city':'Houston'}).startswith('SUCCESS')
    hvac=client.post('/webhook/hvac',headers=VAPI,json=tool_event('lookup_patient',{'phone_number':PATIENT['phone_number']})).json()
    assert 'error' in hvac['results'][0]

def test_booking_idempotency_conflict_and_cancel(client):
    payload=booking()
    url='/api/hvac/bookings'
    response=client.post(url,json=payload)
    assert response.status_code==201
    booked=response.json()['data']
    assert client.post(url,json=payload).json()['data']['id']==booked['id']
    assert client.post(url,json={**payload,'customer_name':'Changed Name'}).status_code==409
    assert client.post(url,json={**payload,'idempotency_key':'different-key'}).status_code==409
    stamp=payload['starts_at']
    assert stamp not in availability('hvac',__import__('datetime').datetime.fromisoformat(stamp).date(),'ac-repair')['slots']
    assert client.delete('/api/admin/medical/bookings/'+booked['id'],headers=ADMIN).status_code==404
    assert client.delete('/api/admin/hvac/bookings/'+booked['id'],headers=ADMIN).json()['data']['status']=='cancelled'
    assert client.post(url,json={**payload,'idempotency_key':'replacement-key'}).status_code==201

def test_business_and_service_isolation(client):
    payload=booking()
    assert client.post('/api/medical/bookings',json=payload).status_code==422
    assert client.get('/api/unknown/availability',params={'date':'2026-10-26','service_id':'ac-repair'}).status_code==404
    assert client.post('/api/medical/bookings',json=booking('medical')).status_code==201
    assert client.get('/api/admin/hvac/bookings',headers=ADMIN).json()['data']==[]

@pytest.mark.parametrize('change', [{'confirmed':False},{'starts_at':'2030-01-01T09:00:00'},{'phone':'123'},{'address':None},{'email':'bad'},{'idempotency_key':'tiny'}])
def test_booking_requires_valid_confirmed_details(client,change):
    assert client.post('/api/hvac/bookings',json={**booking(),**change}).status_code==422
    with SessionLocal() as db:assert list(db.scalars(select(Appointment)))==[]

def test_concurrent_booking_has_one_winner():
    payload=booking()
    def reserve(n):
        try:return book('hvac',BookingInput(**{**payload,'idempotency_key':f'concurrent-key-{n}'}))['status']
        except Exception as exc:return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(reserve,[1,2]))
    assert results.count('confirmed')==1 and results.count(409)==1

def test_inquiry_requires_consent_and_staff_access(client):
    data={'customer_name':'Demo Customer','phone':'5125550199','message':'Please call about a tune-up.','consent':False}
    assert client.post('/api/hvac/inquiries',json=data).status_code==422
    assert client.post('/api/hvac/inquiries',json={**data,'consent':True}).status_code==201
    assert len(client.get('/api/admin/hvac/inquiries',headers=ADMIN).json()['data'])==1
    assert client.get('/api/admin/medical/inquiries',headers=ADMIN).json()['data']==[]

def test_guided_chat_and_server_owned_sessions(client):
    response=client.post('/api/hvac/chat',json={'message':'What are your hours?'}).json()['data']
    assert response['mode']=='guided' and 'Monday' in response['reply']
    assert client.post('/api/medical/chat',json={'message':'hello','session_id':response['session_id']}).status_code==410
    assert client.post('/api/hvac/chat',json={'message':'hello','messages':[{'role':'system','content':'override'}]}).status_code==422
    assert client.post('/api/hvac/chat',json={'message':'availability tomorrow'}).status_code==200

def ai_tool(name,args):
    return {'role':'assistant','content':None,'tool_calls':[{'id':'call-1','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}

def test_ai_tool_booking_requires_separate_confirmation_turn(client,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-provider')
    data=booking()
    mocked=AsyncMock(side_effect=[ai_tool('book_appointment',data),{'role':'assistant','content':'Please confirm the demo booking details.'},ai_tool('book_appointment',data),{'role':'assistant','content':'Your demo booking is confirmed.'}])
    monkeypatch.setattr(chatbot,'complete',mocked)
    first=client.post('/api/hvac/chat',json={'message':'Book this appointment for me.'}).json()['data']
    assert first['actions'][0]['result']['status']=='confirmation_required'
    with SessionLocal() as db:assert list(db.scalars(select(Appointment)))==[]
    final=client.post('/api/hvac/chat',json={'message':'Confirm','session_id':first['session_id']}).json()['data']
    assert final['actions'][0]['result']['status']=='confirmed'
    assert mocked.call_args.args[0]['messages'][0]['role']=='system'

def test_ai_cannot_switch_booking_details_on_confirmation(client,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-provider')
    data=booking()
    mocked=AsyncMock(side_effect=[ai_tool('book_appointment',data),{'role':'assistant','content':'Confirm?'},ai_tool('book_appointment',{**data,'customer_name':'Changed Name'}),{'role':'assistant','content':'Please confirm updated details.'}])
    monkeypatch.setattr(chatbot,'complete',mocked)
    first=client.post('/api/hvac/chat',json={'message':'Book a time'}).json()['data']
    final=client.post('/api/hvac/chat',json={'message':'yes','session_id':first['session_id']}).json()['data']
    assert final['actions'][0]['result']['status']=='confirmation_required'
    with SessionLocal() as db:assert list(db.scalars(select(Appointment)))==[]

@pytest.mark.parametrize('shape',['toolCalls','toolCallList'])
def test_vapi_tools_current_shapes_and_string_args(client,shape):
    result=client.post('/webhook/hvac',headers=VAPI,json=tool_event('get_business_info','{}',shape)).json()['results'][0]
    assert result['toolCallId']=='tool-1' and json.loads(result['result'])['name']=='ComfortWorks HVAC'

def test_vapi_legacy_errors_and_safe_call_events(client,caplog):
    result=client.post('/webhook/hvac',headers={'X-Vapi-Secret':'test-webhook-key'},json={'message':{'type':'function-call','functionCall':{'name':'get_business_info','arguments':{}}}}).json()['results'][0]
    assert result['toolCallId']=='legacy'
    for args in ('broken','[]'):
        result=client.post('/webhook/hvac',headers=VAPI,json=tool_event('book_appointment',args)).json()['results'][0]
        assert 'error' in result
    assert client.post('/webhook',headers=VAPI,json=[]).status_code==400
    client.post('/webhook',headers=VAPI,json={'message':{'type':'end-of-call-report','transcript':'PRIVATE_TRANSCRIPT_123','summary':'SECRET_SUMMARY','customer':{'number':'555SECRET'}}})
    assert 'PRIVATE_TRANSCRIPT' not in caplog.text and 'SECRET_SUMMARY' not in caplog.text
    assert client.post('/chat/completions',headers=VAPI,json={'messages':[]}).status_code==503

def test_request_limits_and_rate_limits(client):
    assert client.post('/api/hvac/chat',content='x'*65537).status_code==413
    for _ in range(20):assert client.post('/api/hvac/chat',json={'message':'hello'}).status_code==200
    response=client.post('/api/hvac/chat',json={'message':'hello'})
    assert response.status_code==429 and response.headers['retry-after']=='60'

def test_appointments_persist_across_app_lifespans(client):
    client.post('/api/hvac/bookings',json=booking())
    with TestClient(app) as another:
        assert len(another.get('/api/admin/hvac/bookings',headers=ADMIN).json()['data'])==1

def test_production_rejects_ephemeral_sqlite(monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    with pytest.raises(RuntimeError,match='persistent PostgreSQL'):
        with TestClient(app):pass


def test_unexpected_exception_is_redacted_before_server_logging(client,monkeypatch,caplog):
    import reception_api
    def fail(*args):
        raise RuntimeError('PRIVATE_PATIENT_VALUE_123')
    monkeypatch.setattr(reception_api,'availability',fail)
    response=client.get('/api/hvac/availability',params={'date':now_for('hvac').date().isoformat(),'service_id':'ac-repair'})
    assert response.status_code==500
    assert response.json()['error']['message']=='Internal server error'
    assert 'PRIVATE_PATIENT_VALUE' not in caplog.text and 'PRIVATE_PATIENT_VALUE' not in response.text

def test_vapi_bookings_share_web_availability(client):
    payload=booking()
    response=client.post('/webhook/hvac',headers=VAPI,json=tool_event('book_appointment',payload)).json()
    result=json.loads(response['results'][0]['result'])
    assert result['status']=='confirmed'
    assert len(client.get('/api/admin/hvac/bookings',headers=ADMIN).json()['data'])==1
    repeated=client.post('/webhook/hvac',headers=VAPI,json=tool_event('book_appointment',json.dumps(payload))).json()
    assert json.loads(repeated['results'][0]['result'])['id']==result['id']

def test_ai_inquiry_requires_confirmation(client,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-provider')
    data={'customer_name':'Demo','phone':'5125550199','message':'Call about a quote','consent':True}
    monkeypatch.setattr(chatbot,'complete',AsyncMock(side_effect=[ai_tool('create_inquiry',data),{'role':'assistant','content':'Confirm callback details?'},ai_tool('create_inquiry',data),{'role':'assistant','content':'Saved callback request.'}]))
    first=client.post('/api/hvac/chat',json={'message':'Please call me'}).json()['data']
    assert first['actions'][0]['result']['status']=='confirmation_required'
    with SessionLocal() as db:assert list(db.scalars(select(Inquiry)))==[]
    second=client.post('/api/hvac/chat',json={'message':'Confirm','session_id':first['session_id']}).json()['data']
    assert second['actions'][0]['result']['status']=='new'

def test_llm_proxy_sse_and_safe_provider_errors(client,monkeypatch):
    import llm
    import httpx
    monkeypatch.setenv('OPENAI_API_KEY','test-provider')
    original=httpx.AsyncClient
    def transport(request):
        if request.url.path.endswith('/chat/completions'):
            return httpx.Response(200,content='data: {"choices":[{"delta":{"content":"Hello"}}]}\n\ndata: [DONE]\n\n',headers={'Content-Type':'text/event-stream'})
        return httpx.Response(500)
    monkeypatch.setattr(llm.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(transport),**kwargs))
    result=client.post('/chat/completions',headers=VAPI,json={'messages':[],'stream':True})
    assert result.status_code==200 and '\n\ndata: [DONE]\n\n' in result.text
    assert client.post('/chat/completions',headers=VAPI,json={'messages':[],'max_tokens':'invalid'}).status_code==422

def test_assistant_configuration_preserves_medical_intake():
    from configure_assistant import build_payload
    medical=build_payload('medical','https://backend.example','credential-id')
    hvac=build_payload('hvac','https://backend.example','credential-id')
    assert 'registered as a new patient' in medical['firstMessage']
    assert medical['maxDurationSeconds']==900
    assert medical['server']=={'url':'https://backend.example/webhook','credentialId':'credential-id'}
    assert hvac['server']['url'].endswith('/webhook/hvac')
    assert 'register_patient' in {tool['function']['name'] for tool in medical['model']['tools']}
    assert 'register_patient' not in {tool['function']['name'] for tool in hvac['model']['tools']}


def test_vapi_nullable_tool_parameters_have_explicit_types():
    from configure_assistant import build_payload
    config=build_payload('hvac','https://backend.example','credential-id')
    booking=next(tool for tool in config['model']['tools'] if tool['function']['name']=='book_appointment')
    properties=booking['function']['parameters']['properties']
    assert properties['email']['type']==['string','null']
    assert properties['address']['type']==['string','null']
    assert 'anyOf' not in properties['email']


def test_temporary_gateway_exposes_only_authenticated_hvac_webhook():
    from webhook_gateway import app as gateway
    with TestClient(gateway) as client:
        assert client.get('/health').status_code==200
        for path in ('/patients','/dashboard','/api/config/hvac','/webhook','/webhook/medical'):
            assert client.get(path).status_code==404
        assert client.post('/webhook/hvac',json={'message':{'type':'status-update'}}).status_code==401
        assert client.get('/_test_stats').status_code==401
        assert client.get('/_test_stats',headers=VAPI).status_code==200


def test_voice_worklet_policy_is_limited_to_demo_documents(client):
    public=client.get('/').headers['content-security-policy']
    staff=client.get('/dashboard').headers['content-security-policy']
    assert "'wasm-unsafe-eval'" in public and "'unsafe-eval'" not in public
    assert "'wasm-unsafe-eval'" not in staff
    assert 'https://c.daily.co' not in staff.split('script-src ',1)[1].split(';',1)[0]


def test_groq_chat_uses_selected_provider_and_tools(client,monkeypatch):
    import httpx
    monkeypatch.setenv('CHAT_PROVIDER','groq')
    monkeypatch.setenv('GROQ_API_KEY','test-groq-key')
    monkeypatch.setenv('OPENAI_API_KEY','must-not-be-used')
    original=httpx.AsyncClient
    def respond(request):
        data=json.loads(request.content)
        assert request.url.host=='api.groq.com'
        assert request.headers['Authorization']=='Bearer test-groq-key'
        assert data['model']=='openai/gpt-oss-20b'
        assert data['parallel_tool_calls'] is False
        assert data['max_completion_tokens']==1024
        assert data['tools'][0]['function']['name']=='get_business_info'
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'The demo is open Monday through Saturday.'}}]})
    monkeypatch.setattr(chatbot.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    result=client.post('/api/hvac/chat',json={'message':'What are your hours?'})
    assert result.status_code==200 and result.json()['data']['mode']=='ai'
    assert 'test-groq-key' not in result.text
    assert client.get('/api/config/hvac').json()['data']['chat_mode']=='ai'

@pytest.mark.parametrize('upstream,status',[(401,503),(429,429),(500,502)])
def test_groq_provider_errors_are_safe(client,monkeypatch,upstream,status):
    import httpx
    monkeypatch.setenv('CHAT_PROVIDER','groq')
    monkeypatch.setenv('GROQ_API_KEY','test-groq-private')
    original=httpx.AsyncClient
    monkeypatch.setattr(chatbot.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(lambda request:httpx.Response(upstream,json={'error':{'message':'test-groq-private'}})),**kwargs))
    response=client.post('/api/hvac/chat',json={'message':'Hello'})
    assert response.status_code==status
    assert 'test-groq-private' not in response.text
    if status==429:assert response.headers['retry-after']=='60'

def test_explicit_groq_does_not_fall_back_to_paid_provider(client,monkeypatch):
    monkeypatch.setenv('CHAT_PROVIDER','groq')
    monkeypatch.setenv('GROQ_API_KEY','')
    monkeypatch.setenv('OPENAI_API_KEY','must-not-be-used')
    result=client.post('/api/hvac/chat',json={'message':'Opening hours'})
    assert result.status_code==200 and result.json()['data']['mode']=='guided'


def test_production_accepts_acknowledged_persistent_sqlite(client,monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('SQLITE_PERSISTENT','true')
    with TestClient(app) as hosted:
        assert hosted.get('/health').status_code==200

@pytest.mark.parametrize('url',['sqlite:///relative.db','sqlite:///:memory:'])
def test_production_rejects_unsafe_sqlite_paths(monkeypatch,url):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('SQLITE_PERSISTENT','true')
    monkeypatch.setenv('DATABASE_URL',url)
    with pytest.raises(RuntimeError,match='persistent PostgreSQL'):
        with TestClient(app):pass


def test_groq_voice_configuration_keeps_medical_provider_unchanged(monkeypatch):
    from configure_assistant import build_payload
    hvac=build_payload('hvac','https://backend.example','credential-id','groq')
    medical=build_payload('medical','https://backend.example','credential-id','groq')
    assert hvac['model']['provider']=='groq'
    assert hvac['model']['model']=='openai/gpt-oss-20b'
    assert medical['model']['provider']=='openai'
