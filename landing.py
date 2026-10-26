"""Serve the responsive demo interface with no build step."""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from config import ROOT
router = APIRouter()
@router.get('/', include_in_schema=False)
@router.get('/medical', include_in_schema=False)
@router.get('/hvac', include_in_schema=False)
def landing():
    return FileResponse(ROOT / 'static' / 'index.html')
