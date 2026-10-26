"""Local testing gateway: expose only the authenticated HVAC webhook to Vapi."""
from collections import Counter
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response
from security import require_vapi
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
counts=Counter()
@app.get('/health')
def health():return {'status':'ok','service':'HVAC webhook gateway'}
@app.get('/_test_stats',dependencies=[Depends(require_vapi)])
def stats():return dict(counts)
@app.post('/webhook/hvac',dependencies=[Depends(require_vapi)])
async def forward(request:Request):
    content=bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content)>65536:raise HTTPException(413,'Request too large')
    try:
        import json
        envelope=json.loads(content)
        message=envelope.get('message',envelope)
        kind=message.get('type','unknown')
        counts[kind if kind in {'tool-calls','function-call','end-of-call-report','status-update'} else 'other']+=1
        for call in message.get('toolCallList') or message.get('toolCalls') or []:
            name=call.get('function',{}).get('name')
            if name in {'get_business_info','check_availability','book_appointment','create_inquiry'}:counts['tool:'+name]+=1
    except (ValueError,AttributeError,TypeError):pass
    async with httpx.AsyncClient(timeout=40) as client:
        response=await client.post('http://127.0.0.1:8000/webhook/hvac',content=bytes(content),headers={'Authorization':request.headers.get('authorization',''),'Content-Type':'application/json'})
    return Response(response.content,status_code=response.status_code,media_type='application/json')
