"""Authenticated optional medical custom-LLM proxy for Vapi."""
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from config import setting
from security import require_vapi, rate_limit

router = APIRouter(dependencies=[Depends(require_vapi)])

@router.post('/chat/completions')
async def chat_completions(request: Request):
    rate_limit(request, 'llm', 30)
    key = setting('OPENAI_API_KEY')
    if not key:
        raise HTTPException(503, 'AI provider is not configured.')
    body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get('messages'), list) or len(body['messages']) > 100:
        raise HTTPException(422, 'Invalid messages')
    try:
        max_tokens = min(max(int(body.get('max_tokens',500)),1),1000)
    except (TypeError, ValueError):
        raise HTTPException(422, 'max_tokens must be an integer') from None
    payload = {'model':setting('LLM_MODEL','gpt-4o-mini'),'messages':[{'role':'system','content':'You are CareCloud Medical’s receptionist. Confirm before writes. Never provide medical advice or reveal patient information to unverified callers.'}] + body['messages'], 'stream':bool(body.get('stream',True)), 'max_tokens':max_tokens}
    for field in ('tools','tool_choice'):
        if field in body:
            payload[field] = body[field]
    headers = {'Authorization':'Bearer ' + key}
    if payload['stream']:
        return StreamingResponse(stream(payload, headers), media_type='text/event-stream')
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post('https://api.openai.com/v1/chat/completions', json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, 'AI provider unavailable') from None

async def stream(payload, headers):
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            async with client.stream('POST','https://api.openai.com/v1/chat/completions',json=payload,headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    yield line + '\n'
    except httpx.HTTPError:
        yield 'data: ' + json.dumps({'error':{'message':'AI provider unavailable'}}) + '\n\ndata: [DONE]\n\n'
