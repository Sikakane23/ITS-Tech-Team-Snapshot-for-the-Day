#!/usr/bin/env python3
"""Read-only Freshservice agent-ID verification. Prints no ticket content or credentials."""
import os, json, base64, urllib.request, urllib.parse, urllib.error

DOMAIN = 'northfieldhospitalhelpdesk.freshservice.com'
KEY = os.environ.get('FRESHSERVICE_API_KEY', '').strip()
if not KEY:
    raise SystemExit('FRESHSERVICE_API_KEY secret missing')
AUTH = 'Basic ' + base64.b64encode((KEY + ':X').encode()).decode()
AGENTS = {
 'Carter':31000582795, 'Alex':31000589835, 'Jake':31000569854,
 'Narith':31000569666, 'Scott':31000567881, 'Tony':31000054955,
}
HEADERS={'Authorization':AUTH,'Accept':'application/json'}

def get(path,params=None):
    url='https://' + DOMAIN + path
    if params:
        url+='?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers=HEADERS)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            return r.status,json.load(r)
    except urllib.error.HTTPError as e:
        return e.code,None
    except Exception as e:
        return type(e).__name__,None

print('READ-ONLY Freshservice agent-ID diagnostic; no names from Freshservice or ticket contents printed.')
print('Test A: Do the six numeric IDs resolve in /api/v2/agents/{id}?')
for name, aid in AGENTS.items():
    code,data=get('/api/v2/agents/'+str(aid))
    returned=(data or {}).get('agent',{}) if isinstance(data,dict) else {}
    match=(str(returned.get('id'))==str(aid))
    print(f'  {name}: HTTP {code}; agent record ID matches supplied ID: {match if code==200 else "not checked"}')

print('Test B: Examine assigned-agent IDs on one page of tickets for workspace 2, without printing ticket data.')
for wid in (2,0):
    code,data=get('/api/v2/tickets',{'workspace_id':wid,'per_page':100,'page':1})
    if code!=200 or not isinstance(data,dict):
        print(f'  workspace {wid}: HTTP {code}')
        continue
    tickets=data.get('tickets',[])
    responder_ids={str(t.get('responder_id')) for t in tickets if t.get('responder_id') is not None}
    counts={name:sum(str(t.get('responder_id'))==str(aid) for t in tickets) for name,aid in AGENTS.items()}
    unassigned=sum(t.get('responder_id') is None for t in tickets)
    print(f'  workspace {wid}: HTTP {code}; page size={len(tickets)}; distinct non-null responder IDs={len(responder_ids)}; unassigned={unassigned}')
    print('  Supplied IDs found on this page (counts only): '+', '.join(f'{n}={v}' for n,v in counts.items()))
    print('  Any supplied ID present among responder IDs: '+str(any(str(v) in responder_ids for v in AGENTS.values())))

print('Diagnostic complete. This does not modify Freshservice or the GitHub dashboard.')

