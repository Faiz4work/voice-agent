"""Preview Vapi assistant configuration; --apply explicitly creates/updates it."""
import argparse
import json
import re
from urllib.parse import urlparse
import httpx
from config import ROOT, setting
from reception import system_prompt, tool_definitions, business

def vapi_schema(value):
    """Vapi requires explicit property types, including nullable fields."""
    if isinstance(value,list):
        return [vapi_schema(item) for item in value]
    if not isinstance(value,dict):
        return value
    result={key:vapi_schema(item) for key,item in value.items()}
    choices=result.get('anyOf')
    if choices and all(isinstance(item,dict) and isinstance(item.get('type'),str) for item in choices):
        result.pop('anyOf')
        result['type']=[item['type'] for item in choices]
        for choice in choices:
            if choice.get('type')!='null':
                for key,item in choice.items():
                    if key!='type':result.setdefault(key,item)
    return result

def build_payload(business_id, server_url, credential_id, model_provider=None):
    profile=business(business_id)
    provider=(model_provider or setting('VAPI_HVAC_MODEL_PROVIDER','openai')) if business_id=='hvac' else 'openai'
    if provider not in {'openai','groq'}:
        raise ValueError('HVAC model provider must be openai or groq.')
    model=setting('GROQ_MODEL','openai/gpt-oss-20b') if provider=='groq' else setting('LLM_MODEL','gpt-4o-mini')
    tools=tool_definitions()
    prompt=system_prompt(business_id)
    if business_id=='medical':
        legacy=json.loads((ROOT/'vapi_assistant.json').read_text(encoding='utf-8'))
        tools=legacy['model']['tools']+tools
        md=(ROOT/'prompt.md').read_text(encoding='utf-8')
        match=re.search(r'```text\r?\n(.*?)```',md,re.S)
        prompt=(match.group(1) if match else md)+'\n\n'+prompt+'\nPrivacy override: before lookup collect caller-provided last_name and date_of_birth. Before updates pass verify_last_name and verify_date_of_birth. Never read records before verification. This rule takes priority over older instructions.'
    return {'name':profile['name']+' — Receptionist','firstMessage':legacy['firstMessage'] if business_id=='medical' else profile['greeting'],'model':{'provider':provider,'model':model,'temperature':0.3,'maxTokens':1024 if provider=='groq' else 500,'messages':[{'role':'system','content':prompt}],'tools':vapi_schema(tools)},'voice':{'provider':'vapi','voiceId':setting('VAPI_VOICE_ID','Savannah')},'transcriber':{'provider':'deepgram','model':'nova-2','language':'en','numerals':True},'server':{'url':server_url.rstrip('/')+('/webhook' if business_id=='medical' else '/webhook/'+business_id),'credentialId':credential_id},'serverMessages':['tool-calls','end-of-call-report','status-update'],'artifactPlan':{'recordingEnabled':False},'maxDurationSeconds':900 if business_id=='medical' else 300,'silenceTimeoutSeconds':35,'customerJoinTimeoutSeconds':60,'endCallFunctionEnabled':True}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business',choices=['hvac','medical'],default='hvac')
    parser.add_argument('--model-provider',choices=['openai','groq'],default=None,help='HVAC model provider; medical intake retains OpenAI')
    parser.add_argument('--apply',action='store_true',help='Write to Vapi; default only previews configuration')
    args=parser.parse_args()
    base=setting('SERVER_URL','https://YOUR_BACKEND')
    credential=setting('VAPI_CREDENTIAL_ID','YOUR_VAPI_CREDENTIAL_ID')
    payload=build_payload(args.business,base,credential,args.model_provider)
    if not args.apply:
        print(json.dumps(payload,indent=2))
        return
    if not setting('VAPI_API_KEY') or not setting('VAPI_WEBHOOK_SECRET') or 'YOUR_' in base or 'YOUR_' in credential:
        parser.error('Configure VAPI_API_KEY, VAPI_WEBHOOK_SECRET, VAPI_CREDENTIAL_ID and SERVER_URL first. Create a Vapi Bearer credential with the same webhook secret.')
    parsed=urlparse(base)
    if parsed.scheme!='https' or not parsed.hostname:
        parser.error('SERVER_URL must be a public HTTPS URL accessible to Vapi.')
    if payload['model']['provider']=='groq' and not setting('GROQ_API_KEY'):
        parser.error('Set GROQ_API_KEY first. The key is needed for Groq free-tier requests and Vapi provider credentials.')
    assistant_id=setting('VAPI_HVAC_ASSISTANT_ID' if args.business=='hvac' else 'VAPI_ASSISTANT_ID')
    # Keep the medical and HVAC assistants separate, including existing IDs.
    if assistant_id and assistant_id == setting('VAPI_ASSISTANT_ID' if args.business=='hvac' else 'VAPI_HVAC_ASSISTANT_ID'):
        parser.error('Medical and HVAC must use different assistant IDs.')
    headers={'Authorization':'Bearer '+setting('VAPI_API_KEY')}
    try:
        with httpx.Client(timeout=30) as client:
            if payload['model']['provider']=='groq':
                listing=client.get('https://api.vapi.ai/credential',headers=headers)
                listing.raise_for_status()
                credentials=listing.json()
                if not any(item.get('provider')=='groq' for item in credentials):
                    provider_key=client.post('https://api.vapi.ai/credential',headers=headers,json={'provider':'groq','apiKey':setting('GROQ_API_KEY'),'name':'Reception Studio Groq'})
                    provider_key.raise_for_status()
            response=client.patch('https://api.vapi.ai/assistant/'+assistant_id,json=payload,headers=headers) if assistant_id else client.post('https://api.vapi.ai/assistant',json=payload,headers=headers)
            response.raise_for_status()
            print('Configured',args.business,'assistant:',response.json()['id'])
    except httpx.HTTPError:
        raise SystemExit('Vapi configuration failed. Check credentials and the Vapi dashboard. Provider response omitted to protect secrets.') from None

if __name__=='__main__':
    main()
