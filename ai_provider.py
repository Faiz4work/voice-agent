"""Server-side AI provider configuration. Secrets never enter public responses."""
from config import setting

def chat_provider():
    name=setting('CHAT_PROVIDER','auto').lower()
    if name=='auto':
        name='groq' if setting('GROQ_API_KEY') else 'openai'
    if name=='groq':
        return {'name':'groq','key':setting('GROQ_API_KEY'),'model':setting('GROQ_MODEL','openai/gpt-oss-20b'),'url':'https://api.groq.com/openai/v1/chat/completions'}
    if name=='openai':
        return {'name':'openai','key':setting('OPENAI_API_KEY'),'model':setting('LLM_MODEL','gpt-4o-mini'),'url':'https://api.openai.com/v1/chat/completions'}
    raise ValueError('CHAT_PROVIDER must be auto, groq or openai.')

def ai_ready():
    return bool(chat_provider()['key'])

def provider_payload(payload, provider):
    result=dict(payload,model=provider['model'])
    if provider['name']=='groq':
        result['max_completion_tokens']=result.pop('max_tokens',500)
        result['parallel_tool_calls']=False
        if provider['model'].startswith('openai/gpt-oss-'):
            result['reasoning_effort']='low'
            result['max_completion_tokens']=max(1024,result['max_completion_tokens'])
    return result
