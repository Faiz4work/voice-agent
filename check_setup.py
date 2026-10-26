"""Report configuration readiness without disclosing credential values."""
import json
from config import setting
from ai_provider import ai_ready,chat_provider
def main():
    required=['ADMIN_API_KEY','VAPI_WEBHOOK_SECRET','OPENAI_API_KEY','GROQ_API_KEY','VAPI_API_KEY','VAPI_PUBLIC_KEY','VAPI_ASSISTANT_ID','VAPI_HVAC_ASSISTANT_ID','VAPI_CREDENTIAL_ID','SERVER_URL']
    print(json.dumps({'configured':{key:bool(setting(key)) for key in required},'database':'postgresql' if setting('DATABASE_URL').startswith(('postgres://','postgresql')) else 'local SQLite','chat_provider':chat_provider()['name'],'chat_mode':'ai' if ai_ready() else 'guided'},indent=2))
if __name__=='__main__':main()
