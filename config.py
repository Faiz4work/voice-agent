"""Load local settings before importing database or routers."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')

def setting(name: str, default: str = '') -> str:
    value = os.getenv(name, default).strip()
    if value.lower() in {'...', 'sk-...', 'changeme', 'your-key', 'replace-me'}:
        return ''
    return value
