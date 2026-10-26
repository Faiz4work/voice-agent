import os
import tempfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL']='sqlite:///'+str(Path(tempfile.mkdtemp(prefix='reception-tests-'))/'test.db')
os.environ['ADMIN_API_KEY']='test-admin-key'
os.environ['VAPI_WEBHOOK_SECRET']='test-webhook-key'
os.environ['OPENAI_API_KEY']=''
os.environ['GROQ_API_KEY']=''
os.environ['CHAT_PROVIDER']='openai'
os.environ['APP_ENV']='development'
os.environ['SQLITE_PERSISTENT']='false'
for key in ['VAPI_API_KEY','VAPI_PUBLIC_KEY','VAPI_ASSISTANT_ID','VAPI_HVAC_ASSISTANT_ID','VAPI_CREDENTIAL_ID','SERVER_URL']:
    os.environ[key]=''
import pytest
from fastapi.testclient import TestClient
from main import app
from models import Base, engine
import chatbot
import security

@pytest.fixture(autouse=True)
def clean():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    chatbot.sessions.clear()
    security._buckets.clear()
    yield

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
