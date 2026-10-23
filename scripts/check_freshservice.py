#!/usr/bin/env python3
"""Read-only Freshservice filter isolation. Outputs aggregate counts only; no ticket records."""
import base64, calendar, json, os, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

DOMAIN = 'northfieldhospitalhelpdesk.freshservice.com'
KEY = os.getenv('FRESHSERVICE_API_KEY', '').strip()
if not KEY:
    raise SystemExit('Missing FRESHSERVICE_API_KEY GitHub secret')
HEADERS = {'Authorization': 'Basic '+base64.b64encode((KEY+':X').encode()).decode(), 'Accept':'application/json'}
AGENTS = {'Carter':'31000582795','Alex':'31000589835','Jake':'31000569854',
          'Narith':'31000569666','Scott':'31000567881','Tony':'31000054955',
          'Unassigned':None}
STATUSES = sorted({int(s.strip()) for s in os.getenv('FRESHSERVICE_UNRESOLVED_STATUSES','2,3,6,7,8,9').split(',') if s.strip()})

def six_months_ago():
    today = datetime.now(timezone.utc).date()
    y, m = today.year, today.month - 6
    if m <= 0: y, m = y-1, m+12
    return f'{y:04d}-{m:02d}-{min(today.day,calendar.monthrange(y,m)[1]):02d}'

def count(label, query):
    url = 'https://'+DOMAIN+'/api/v2/tickets/filter?'+urllib.parse.urlencode({'query':'"'+query+'"','page':1})
    req=urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req,timeout=30) as res: payload=json.load(res)
        total=payload.get('total')
        print(f'{label}: HTTP 200, total={total}',flush=True)
    except urllib.error.HTTPError as exc:
        field=code=''
        try:
            err=json.loads(exc.read(4096))
            fields=err.get('errors',[])
            if fields: field=str(fields[0].get('field',''))[:40];code=str(fields[0].get('code',''))[:40]
        except Exception: pass
        print(f'{label}: HTTP {exc.code}, field={field or "unknown"}, code={code or "unknown"}',flush=True)
    except Exception as exc:
        print(f'{label}: error={type(exc).__name__}',flush=True)

print('Freshservice ASSIGNEE filter diagnostics (read-only; counts only)',flush=True)
print('No dashboard updates and no ticket records printed.',flush=True)
for name,aid in AGENTS.items():
    count('Agent only - '+name, 'agent_id:null' if aid is None else 'agent_id:'+aid)
status_clause='('+' OR '.join(f'status:{s}' for s in STATUSES)+')'
cutoff=six_months_ago()
print('Statuses configured: '+','.join(map(str,STATUSES))+'; six-month cutoff: '+cutoff,flush=True)
count('Unresolved statuses only',status_clause)
count('Created in last 6 months only',"created_at:>'"+cutoff+"'")
for name in ('Carter','Alex','Unassigned'):
    aid=AGENTS[name]
    ac='agent_id:null' if aid is None else 'agent_id:'+aid
    count(name+' + unresolved statuses', ac+' AND '+status_clause)
    count(name+' + recent creation', ac+" AND created_at:>'"+cutoff+"'")
    count(name+' + both filters', ac+' AND '+status_clause+" AND created_at:>'"+cutoff+"'")
print('Done. Compare diagnostic totals with Freshservice. No changes made.',flush=True)
