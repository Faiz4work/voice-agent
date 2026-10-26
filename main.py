"""AI receptionist: original medical intake plus isolated business demos."""
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any
import config  # environment must load before database and routers
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
from api import router as patients_router
from dashboard import router as dashboard_router
from landing import router as landing_router
from staff import router as staff_router
from llm import router as llm_router
from reception_api import router as reception_router
from models import init_db
from tools import TOOL_REGISTRY
from reception import run_tool
from security import require_vapi

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
log = logging.getLogger('voice-agent')

@asynccontextmanager
async def lifespan(app):
    if config.setting('APP_ENV') == 'production':
        if not config.setting('ADMIN_API_KEY') or not config.setting('VAPI_WEBHOOK_SECRET'):
            raise RuntimeError('Production requires ADMIN_API_KEY and VAPI_WEBHOOK_SECRET.')
        database_url=config.setting('DATABASE_URL')
        persistent_sqlite=False
        if database_url.startswith('sqlite') and config.setting('SQLITE_PERSISTENT').lower()=='true':
            from pathlib import Path
            from sqlalchemy.engine import make_url
            database_path=make_url(database_url).database
            persistent_sqlite=bool(database_path and database_path!=':memory:' and Path(database_path).is_absolute())
        if not database_url.startswith(('postgres://','postgresql://','postgresql+')) and not persistent_sqlite:
            raise RuntimeError('Production requires persistent PostgreSQL DATABASE_URL or explicitly acknowledged SQLite with an absolute path.')
    init_db()
    yield

app = FastAPI(title='Reception Studio', version='2.0.0', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=config.ROOT / 'static'), name='static')
for router in (landing_router, patients_router, dashboard_router, llm_router, reception_router, staff_router):
    app.include_router(router)

@app.middleware('http')
async def boundaries(request: Request, call_next):
    if request.method in ('POST','PUT','PATCH'):
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 65536:
                return JSONResponse({'error':{'message':'Request too large'}}, status_code=413)
        request._body = bytes(content)
    try:
        response = await call_next(request)
    except Exception as exc:
        # Catch here as well: Starlette's generic error handler re-raises to the
        # server, which would otherwise print sensitive exception strings.
        log.error('Request failed: %s', type(exc).__name__)
        response = JSONResponse(status_code=500, content={'data':None,'error':{'message':'Internal server error'}})
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'microphone=(self "https://*.daily.co"), camera=()'
    response.headers['Cache-Control'] = 'no-store'
    # The bundled Vapi SDK uses Daily audio transport; it loads only after a voice click.
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' blob: 'wasm-unsafe-eval' https://c.daily.co; style-src 'self' 'unsafe-inline'; connect-src 'self' https: wss:; img-src 'self' data:; media-src 'self' blob: https:; frame-src https://*.daily.co; worker-src 'self' blob: https://c.daily.co; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    if request.url.path not in ('/', '/hvac', '/medical'):
        response.headers['Content-Security-Policy'] = response.headers['Content-Security-Policy'].replace(" blob: 'wasm-unsafe-eval' https://c.daily.co", '')
    if config.setting('APP_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return JSONResponse(status_code=exc.status_code, content={'data':None,'error':{'message':exc.detail}}, headers=exc.headers)

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={'data':None,'error':{'message':'Validation failed','fields':[{'field':'.'.join(str(p) for p in e['loc'][1:]),'reason':e['msg']} for e in exc.errors()]}})

@app.exception_handler(Exception)
async def unhandled_error(request, exc):
    # Exception strings/SQL parameters can contain patient information.
    log.error('Request failed: %s', type(exc).__name__)
    return JSONResponse(status_code=500, content={'data':None,'error':{'message':'Internal server error'}})

@app.get('/health')
def health():
    from sqlalchemy import text
    from models import engine
    with engine.connect() as connection:
        connection.execute(text('SELECT 1'))
    return {'status':'ok'}

@app.post('/webhook', dependencies=[Depends(require_vapi)])
async def medical_webhook(request: Request):
    return await webhook(request, 'medical')

@app.post('/webhook/{business_id}', dependencies=[Depends(require_vapi)])
async def business_webhook(business_id: str, request: Request):
    from reception import business
    business(business_id)
    return await webhook(request, business_id)

async def webhook(request, business_id):
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, 'Invalid JSON') from None
    if not isinstance(body, dict) or not isinstance(body.get('message', body), dict):
        raise HTTPException(400, 'Invalid webhook envelope')
    message = body.get('message', body)
    if message.get('type') in ('tool-calls','function-call'):
        return await handle_tool_calls(message, business_id)
    # Never log transcripts, summaries, caller IDs, phone numbers or tool arguments.
    return {'received':True}

async def handle_tool_calls(message: dict[str, Any], business_id='medical'):
    calls = message.get('toolCallList') or message.get('toolCalls') or []
    if not calls and message.get('functionCall'):
        calls = [{'id':'legacy','function':message['functionCall']}]
    if not isinstance(calls, list) or len(calls) > 10:
        raise HTTPException(400, 'Invalid tool call list')
    results = []
    from starlette.concurrency import run_in_threadpool
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get('function'), dict) or not isinstance(call.get('id'), str):
            raise HTTPException(400, 'Invalid tool call')
        name = call['function'].get('name')
        args = call['function'].get('arguments', {})
        try:
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict):
                raise ValueError()
            if business_id == 'medical' and name in TOOL_REGISTRY:
                result = await run_in_threadpool(TOOL_REGISTRY[name], args.copy())
            else:
                result = await run_in_threadpool(run_tool, business_id, name, args)
            results.append({'toolCallId':call['id'],'result':result if isinstance(result,str) else json.dumps(result)})
        except HTTPException as exc:
            results.append({'toolCallId':call['id'],'error':str(exc.detail)})
        except (ValueError, ValidationError, TypeError, KeyError):
            results.append({'toolCallId':call['id'],'error':'Invalid arguments. Ask for corrected details.'})
        except Exception as exc:
            log.error('Tool failed: %s', type(exc).__name__)
            results.append({'toolCallId':call['id'],'error':'The action could not be completed. Please try again.'})
    return {'results':results}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='127.0.0.1', port=int(os.getenv('PORT','8000')), access_log=False)
