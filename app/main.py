"""Local presentation app. Run from the project root with uvicorn app.main:app."""
import asyncio
import base64
import io
import json
import math
import os
import time
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / '.env')
app = FastAPI(title='Clef Atlas')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
# Representative candidate points, NOT country centroids or exact photo predictions.
COUNTRIES = {
 'portugal': ('Portugal','Europe','Southern Europe',38.72,-9.14),
 'spain': ('Spain','Europe','Southern Europe',40.42,-3.70),
 'italy': ('Italy','Europe','Southern Europe',41.90,12.50),
 'france': ('France','Europe','Western Europe',48.86,2.35),
 'uk': ('United Kingdom','Europe','Western Europe',51.51,-0.13),
 'germany': ('Germany','Europe','Western Europe',52.52,13.40),
 'japan': ('Japan','Asia','Eastern Asia',35.68,139.69),
 'thailand': ('Thailand','Asia','Southeastern Asia',13.76,100.50),
 'india': ('India','Asia','Southern Asia',28.61,77.21),
 'usa': ('United States','Americas','Northern America',38.91,-77.04),
 'mexico': ('Mexico','Americas','Central America',19.43,-99.13),
 'brazil': ('Brazil','Americas','South America',-15.79,-47.88),
 'south_africa': ('South Africa','Africa','Southern Africa',-25.75,28.19),
 'kenya': ('Kenya','Africa','Eastern Africa',-1.29,36.82),
 'morocco': ('Morocco','Africa','Northern Africa',34.02,-6.84),
 'australia': ('Australia','Oceania','Australasia',-35.28,149.13),
 'new_zealand': ('New Zealand','Oceania','Australasia',-41.29,174.78),
}
SCENARIOS = [
 {'id':'tram','clue':'A narrow cobblestone street, yellow trams, Portuguese signs and tiled facades.','country':'portugal','lat':38.713,'lon':-9.139},
 {'id':'lanes','clue':'Left-hand traffic, Japanese writing, overhead cables and compact cars on a dense urban street.','country':'japan','lat':35.676,'lon':139.650},
 {'id':'cape','clue':'Left-hand traffic, English and Afrikaans signs, dry hills and a distant flat-topped mountain.','country':'south_africa','lat':-33.925,'lon':18.424},
 {'id':'ambiguous','clue':'A quiet road through green rolling hills. Cars drive on the left. No readable signs.','country':'new_zealand','lat':-41.286,'lon':174.776},
]
RATES = {'clef':.240, 'clef-flash':.038}

class Predict(BaseModel):
    model: Literal['clef','clef-flash','llm'] = 'clef'
    strategy: Literal['direct','hierarchical'] = 'direct'
    mode: Literal['live','offline'] = 'offline'
    clue: str = Field(default='', max_length=12000)
    image: str | None = Field(default=None, max_length=6000000)
    candidates: list[str] = Field(default_factory=lambda:list(COUNTRIES), min_length=2,max_length=100)

class Reveal(BaseModel):
    scenario: str
    guess: str
    predicted: str | None = None
    lat: float | None = Field(default=None,ge=-90,le=90)
    lon: float | None = Field(default=None,ge=-180,le=180)

@app.get('/')
def index():
    return FileResponse(ROOT / 'static' / 'index.html')

@app.get('/api/config')
def config():
    return {'countries':{k:{'name':v[0],'continent':v[1],'region':v[2],'lat':v[3],'lon':v[4]} for k,v in COUNTRIES.items()},
            'scenarios':[{'id':s['id'],'clue':s['clue']} for s in SCENARIOS],
            'cloudflare_ready':bool(os.getenv('CLOUDFLARE_ACCOUNT_ID') and os.getenv('CLOUDFLARE_AUTH_TOKEN')),
            'llm_ready':bool(os.getenv('OPENAI_API_KEY'))}

def clean_image(raw: bytes) -> str:
    if len(raw)>4*1024*1024:
        raise HTTPException(413,'Image must be smaller than 4 MiB.')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in {'PNG','JPEG','WEBP'} or im.width*im.height>16000000:
                raise HTTPException(400,'Use PNG, JPEG or WebP, up to 16 megapixels.')
            im = ImageOps.exif_transpose(im).convert('RGB')
            im.thumbnail((1280,1280))
            out=io.BytesIO(); im.save(out,format='JPEG',quality=85)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400,'Cannot decode this image.')
    # Fresh encoding strips EXIF/GPS metadata before inference.
    return 'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()

@app.post('/api/image')
async def image(file: UploadFile = File(...)):
    return {'image':clean_image(await file.read(4*1024*1024+1))}

def validate(req):
    if len(set(req.candidates))!=len(req.candidates) or any(k not in COUNTRIES for k in req.candidates):
        raise HTTPException(400,'Choose at least two distinct supported countries.')
    if not req.clue.strip() and not req.image:
        raise HTTPException(400,'Supply a photo or a clue.')
    if req.image:
        try:
            prefix, encoded=req.image.split(',',1)
            if prefix not in {'data:image/jpeg;base64','data:image/png;base64','data:image/webp;base64'}:
                raise ValueError()
            req.image=clean_image(base64.b64decode(encoded,validate=True))
        except (ValueError,TypeError):
            raise HTTPException(400,'Invalid embedded image.')

async def post_json(url, token, payload):
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.post(url,headers={'Authorization':f'Bearer {token}'},json=payload)
        if response.status_code>=400:
            raise HTTPException(502,f'Provider returned HTTP {response.status_code}. Check credentials, account permissions and model availability.')
        return response.json()
    except (httpx.HTTPError,ValueError):
        raise HTTPException(502,'Provider request failed or returned invalid JSON.')

async def clef(req, criteria, question):
    account=os.getenv('CLOUDFLARE_ACCOUNT_ID',''); token=os.getenv('CLOUDFLARE_AUTH_TOKEN','')
    if not account or not token:
        raise HTTPException(400,'Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AUTH_TOKEN in .env, then restart.')
    payload={'model':req.model,'state':req.clue or 'Infer the location using only visible clues in the photo.',
             'questions':{'location':{'type':'choice','instructions':question,'criteria':criteria}}}
    if req.image: payload['images']=[req.image]
    data=await post_json(f'https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/cloudflare/{req.model}',token,payload)
    if not data.get('success',False): raise HTTPException(502,'Cloudflare rejected the request. Check your Workers AI configuration.')
    try:
        result=data['result']; a=result['answers']['location']; probs=a['probabilities']; choice=a['choice']
        if choice not in criteria or set(probs)!=set(criteria): raise ValueError()
        if any(not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<=p<=1 for p in probs.values()): raise ValueError()
        return {'choice':choice,'probabilities':probs,'confidence':a.get('confidence'),'usage':result.get('usage',{})}
    except (KeyError,TypeError,ValueError): raise HTTPException(502,'Unexpected Clef answer schema.')

async def llm(req):
    token=os.getenv('OPENAI_API_KEY','')
    if not token: raise HTTPException(400,'Set OPENAI_API_KEY in .env and restart to enable the comparison.')
    prompt='Choose the most likely country from these candidates: '+json.dumps({k:COUNTRIES[k][0] for k in req.candidates})+'. Return JSON with a single country key. No explanations. Clues: '+req.clue
    content=[{'type':'text','text':prompt}]
    if req.image: content.append({'type':'image_url','image_url':{'url':req.image}})
    data=await post_json('https://api.openai.com/v1/chat/completions',token,{'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'messages':[{'role':'user','content':content}], 'response_format':{'type':'json_object'},'max_tokens':100})
    try:
        choice=json.loads(data['choices'][0]['message']['content'])['country']
        if choice not in req.candidates: raise ValueError()
        return {'choice':choice,'probabilities':None,'confidence':None,'usage':data.get('usage',{})}
    except (KeyError,TypeError,ValueError): raise HTTPException(502,'LLM did not return a valid candidate country.')

@app.post('/api/predict')
async def predict(req: Predict):
    validate(req); start=time.perf_counter(); stages=[]
    if req.mode=='offline':
        # Fixed illustrative fixtures, deliberately NOT model measurements.
        target=next((s['country'] for s in SCENARIOS if s['clue']==req.clue),req.candidates[0])
        if target not in req.candidates: target=req.candidates[0]
        p=.42 if 'No readable signs' in req.clue else .82
        answer={'choice':target,'probabilities':{k:(p if k==target else (1-p)/(len(req.candidates)-1)) for k in req.candidates},'confidence':None,'usage':{}}
        stages=[{'stage':'Illustrative fixture',**answer}]
    elif req.model=='llm':
        if req.strategy!='direct': raise HTTPException(400,'LLM comparison uses direct country selection.')
        answer=await llm(req); stages=[{'stage':'Country',**answer}]
    else:
        candidates=req.candidates[:]
        if req.strategy=='hierarchical':
            for field,stage in [(1,'Continent'),(2,'Region')]:
                options={COUNTRIES[k][field]:COUNTRIES[k][field] for k in candidates}
                if len(options)==1: continue
                result=await clef(req,options,f'Which {stage.lower()} most likely contains this location, among the supplied options?')
                stages.append({'stage':stage,**result})
                candidates=[k for k in candidates if COUNTRIES[k][field]==result['choice']]
        if len(candidates)==1:
            answer={'choice':candidates[0],'probabilities':{candidates[0]:1.0},'confidence':None,'usage':{}}
            stages.append({'stage':'Country (forced by branch)',**answer})
        else:
            answer=await clef(req,{k:COUNTRIES[k][0] for k in candidates},'Which country is most likely, among these candidates?')
            stages.append({'stage':'Country',**answer})
    usage=sum(s.get('usage',{}).get('input_tokens',0) for s in stages)
    return {'model':req.model,'strategy':req.strategy,'mode':req.mode, 'choice':answer['choice'],'probabilities':answer['probabilities'],
            'stages':stages,'latency_ms':None if req.mode=='offline' else round((time.perf_counter()-start)*1000),
            'input_tokens':usage,'estimated_cost_usd':usage*RATES[req.model]/1000000 if req.mode=='live' and req.model in RATES else None,
            'note':'Illustrative fixture; no API call or measured performance.' if req.mode=='offline' else ('Final country probabilities are conditional on the selected branch; earlier errors cannot be recovered.' if req.strategy=='hierarchical' else 'Probabilities apply only to the supplied candidates; calibration is not verified.')}

def distance(a,b,c,d):
    x,y=math.radians(c-a),math.radians(d-b)
    h=math.sin(x/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(y/2)**2
    return round(6371*2*math.asin(min(1,math.sqrt(h))))

@app.post('/api/reveal')
def reveal(req:Reveal):
    s=next((s for s in SCENARIOS if s['id']==req.scenario),None)
    if not s or req.guess not in COUNTRIES: raise HTTPException(400,'Unknown round or guess.')
    return {**s,'human_correct':req.guess==s['country'],'ai_correct':req.predicted==s['country'],
            'distance_km':distance(req.lat,req.lon,s['lat'],s['lon']) if req.lat is not None and req.lon is not None else None}
