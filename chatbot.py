"""Server-owned chat history; tools share the web and voice service layer."""
import asyncio
import json
import secrets
import time
from collections import OrderedDict
from datetime import timedelta
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from config import setting
from ai_provider import ai_ready, chat_provider, provider_payload
from reception import business, now_for, availability, system_prompt, tool_definitions, run_tool

class ChatInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=100)

sessions = OrderedDict()
SESSION_TTL = 1800

def session_for(business_id, session_id):
    now = time.monotonic()
    for key in list(sessions):
        if sessions[key]['at'] < now - SESSION_TTL and not sessions[key]['lock'].locked():
            del sessions[key]
    if session_id:
        current = sessions.get(session_id)
        if not current or current['business'] != business_id:
            raise HTTPException(410, 'This conversation expired. Start a new chat.')
    else:
        if len(sessions) >= 128:
            raise HTTPException(503, 'The demo is busy. Please try again shortly.')
        session_id = secrets.token_urlsafe(32)
        sessions[session_id] = {'business':business_id,'turns':[], 'at':now, 'lock':asyncio.Lock(), 'pending':None}
    sessions.move_to_end(session_id)
    sessions[session_id]['at'] = now
    return session_id, sessions[session_id]

def guided_reply(business_id, message):
    profile = business(business_id)
    lower = message.lower()
    if any(word in lower for word in ('available', 'availability', 'appointment', 'book', 'tomorrow')):
        day = now_for(business_id).date() + timedelta(days=1)
        for offset in range(7):
            result = availability(business_id, day + timedelta(days=offset), profile['services'][0]['id'])
            if result['slots']:
                return ('For ' + profile['services'][0]['name'] + ', the next demo opening is ' + result['slots'][0] + ' (' + profile['timezone'] + '). Choose a service and date in the booking panel to reserve a time. Nothing has been booked.')
        return 'No demo openings are available this week. Please leave a callback request.'
    for key, text in profile['faqs'].items():
        aliases = {'pricing':['price','cost','fee','charge'], 'hours':['hour','open','closed'], 'emergency':['gas','emergency','danger'], 'coverage':['area','serve','location'], 'registration':['register','patient','insurance'], 'cancellation':['cancel','reschedule']}
        if key in lower or any(word in lower for word in aliases.get(key, [])):
            return text
    if any(word in lower for word in ('service', 'repair', 'heating', 'cooling')):
        return 'Our demo services are: ' + '; '.join(s['name'] + ' — ' + s['description'] for s in profile['services'])
    return profile['greeting'] + ' You can ask about hours, services, pricing, or availability. This guided preview uses saved business information; AI conversation becomes available when the provider key is configured.'

async def complete(payload):
    provider=chat_provider()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(provider['url'], json=provider_payload(payload,provider), headers={'Authorization':'Bearer ' + provider['key']})
            if response.status_code==429:
                raise HTTPException(429, 'The AI provider rate limit was reached. Please wait a minute or use the booking panel.',headers={'Retry-After':'60'})
            if response.status_code in (401,403):
                raise HTTPException(503, 'The AI provider key was not accepted. Please check the private server settings.')
            response.raise_for_status()
            return response.json()['choices'][0]['message']
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        raise HTTPException(502, 'The AI provider is unavailable. Please try again or use the booking panel.') from None

async def chat(business_id, payload):
    business(business_id)
    sid, session = session_for(business_id, payload.session_id)
    if session['lock'].locked():
        raise HTTPException(409, 'Please wait for the current response.')
    async with session['lock']:
        if not ai_ready():
            return {'session_id':sid, 'mode':'guided', 'reply':guided_reply(business_id, payload.message), 'actions':[]}
        messages = [{'role':'system','content':system_prompt(business_id)}]
        for turn in session['turns'][-8:]:
            messages.extend(turn)
        turn = [{'role':'user','content':payload.message}]
        actions = []
        pending_at_start = session['pending']
        confirmation = payload.message.lower().strip(' .!') in {'yes','confirm','confirmed','yes please','yes, please','yes book it','book it','yes, book it','i confirm'}
        # Any changed details invalidate the prior proposal until a new proposal is read back.
        session['pending'] = None
        for _ in range(5):
            reply = await complete({'model':chat_provider()['model'], 'messages':messages + turn, 'tools':tool_definitions(), 'temperature':0.3, 'max_tokens':500})
            calls = reply.get('tool_calls') or []
            if len(calls) > 6:
                raise HTTPException(502, 'The assistant requested too many actions.')
            turn.append({k:reply[k] for k in ('role','content','tool_calls') if k in reply})
            if not calls:
                session['turns'].append(turn)
                session['turns'] = session['turns'][-8:]
                return {'session_id':sid,'mode':'ai','reply':reply.get('content') or 'How else can I help?', 'actions':actions}
            for call in calls:
                name = call.get('function', {}).get('name','')
                try:
                    args = json.loads(call['function'].get('arguments','{}'))
                    if name == 'book_appointment':
                        from reception import BookingInput
                        validated = BookingInput.model_validate(args)
                        details = validated.model_dump(mode='json', exclude={'confirmed','idempotency_key'})
                        if not confirmation or not pending_at_start or details != pending_at_start.get('details'):
                            # No write takes place until a subsequent explicit confirmation turn.
                            session['pending'] = {'details':details, 'key':validated.idempotency_key}
                            result = {'status':'confirmation_required', 'details':details, 'instruction':'Read these exact details back, including timezone, and ask the customer to reply Confirm. No appointment has been booked.'}
                        else:
                            args['idempotency_key'] = pending_at_start['key']
                            args['confirmed'] = True
                            result = run_tool(business_id, name, args)
                            pending_at_start = None
                    elif name == 'create_inquiry':
                        if not confirmation or not pending_at_start or pending_at_start.get('inquiry') != args:
                            session['pending'] = {'inquiry':args}
                            result = {'status':'confirmation_required','details':args,'instruction':'Read back the callback details and ask the customer to reply Confirm. No request has been saved.'}
                        else:
                            result = run_tool(business_id, name, args)
                            pending_at_start = None
                    else:
                        result = run_tool(business_id, name, args)
                    actions.append({'tool':name, 'result':result})
                except HTTPException as exc:
                    result = {'error':exc.detail}
                except (ValueError, ValidationError, KeyError, TypeError):
                    result = {'error':'Invalid tool arguments. Ask for the missing or corrected information.'}
                turn.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result)})
        session['turns'].append(turn)
        session['turns'] = session['turns'][-8:]
        return {'session_id':sid,'mode':'ai','reply':'I could not complete this conversation. Check the results below; you can also use the booking panel.', 'actions':actions}
