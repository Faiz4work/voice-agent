"""Fail-closed private routes and bounded, per-process abuse protection."""
import hmac
import time
from collections import OrderedDict, deque
from threading import Lock
from fastapi import HTTPException, Request
from config import setting

def _authenticate(request: Request, name: str, legacy: str = ''):
    expected = setting(name)
    if not expected:
        raise HTTPException(503, 'This private service has not been configured.')
    provided = request.headers.get('authorization', '')
    provided = provided[7:] if provided.lower().startswith('bearer ') else ''
    if not provided and legacy:
        provided = request.headers.get(legacy, '')
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(401, 'Authentication required', headers={'WWW-Authenticate': 'Bearer'})

def require_admin(request: Request):
    _authenticate(request, 'ADMIN_API_KEY')

def require_vapi(request: Request):
    _authenticate(request, 'VAPI_WEBHOOK_SECRET', 'x-vapi-secret')

_buckets = OrderedDict()
_lock = Lock()

def rate_limit(request: Request, scope: str, limit: int = 30):
    # Do not trust forwarded IP headers supplied by visitors.
    ip = request.client.host if request.client else 'unknown'
    key = (ip, scope)
    now = time.monotonic()
    with _lock:
        bucket = _buckets.setdefault(key, deque())
        _buckets.move_to_end(key)
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, 'Please wait a minute before trying again.', headers={'Retry-After': '60'})
        bucket.append(now)
        while len(_buckets) > 4096:
            _buckets.popitem(last=False)
