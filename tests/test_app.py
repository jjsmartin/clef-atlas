import base64
import io
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from PIL import Image
from app import main

client=TestClient(main.app)

def test_offline_and_reveal():
    cfg=client.get('/api/config').json()
    assert 'country' not in cfg['scenarios'][0]
    res=client.post('/api/predict',json={'clue':cfg['scenarios'][0]['clue'],'candidates':['portugal','spain']}).json()
    assert res['choice']=='portugal' and res['latency_ms'] is None
    assert abs(sum(res['probabilities'].values())-1)<1e-8
    reveal=client.post('/api/reveal',json={'scenario':'tram','guess':'portugal','lat':38.713,'lon':-9.139}).json()
    assert reveal['human_correct'] and reveal['distance_km']==0

def test_invalid_candidates_and_image():
    assert client.post('/api/predict',json={'clue':'road','candidates':['bad','spain']}).status_code==400
    assert client.post('/api/predict',json={'clue':'road','candidates':['spain','spain']}).status_code==400
    assert client.post('/api/image',files={'file':('bad.jpg',b'not an image','image/jpeg')}).status_code==400

def test_reencode_strips_metadata():
    img=Image.new('RGB',(20,20)); exif=Image.Exif(); exif[270]='SECRET LOCATION'
    out=io.BytesIO(); img.save(out,format='JPEG',exif=exif)
    res=client.post('/api/image',files={'file':('x.jpg',out.getvalue(),'image/jpeg')}).json()
    cleaned=Image.open(io.BytesIO(base64.b64decode(res['image'].split(',')[1])))
    assert not cleaned.getexif()

def test_live_payload_and_hierarchy(monkeypatch):
    monkeypatch.setenv('CLOUDFLARE_ACCOUNT_ID','test');monkeypatch.setenv('CLOUDFLARE_AUTH_TOKEN','test')
    calls=[]
    async def fake(url,token,payload):
        calls.append(payload)
        options=payload['questions']['location']['criteria']
        choice='Europe' if 'Europe' in options else 'portugal'
        return {'success':True,'result':{'answers':{'location':{'choice':choice,'probabilities':{k:1.0 if k==choice else 0.0 for k in options}}},'usage':{'input_tokens':100}}}
    monkeypatch.setattr(main,'post_json',fake)
    result=client.post('/api/predict',json={'mode':'live','strategy':'hierarchical','clue':'road','candidates':['portugal','spain','japan']})
    assert result.status_code==200
    data=result.json();assert data['choice']=='portugal' and data['input_tokens']==200
    assert len(calls)==2 and 'country' not in calls[0]['state']
    assert data['estimated_cost_usd']==.000048

def test_missing_credentials_and_provider_failure(monkeypatch):
    monkeypatch.delenv('CLOUDFLARE_ACCOUNT_ID',raising=False);monkeypatch.delenv('CLOUDFLARE_AUTH_TOKEN',raising=False)
    assert client.post('/api/predict',json={'mode':'live','clue':'road'}).status_code==400
    monkeypatch.setenv('CLOUDFLARE_ACCOUNT_ID','test');monkeypatch.setenv('CLOUDFLARE_AUTH_TOKEN','test')
    monkeypatch.setattr(main,'post_json',AsyncMock(return_value={'success':False}))
    assert client.post('/api/predict',json={'mode':'live','clue':'road'}).status_code==502

def test_page_and_assets():
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
