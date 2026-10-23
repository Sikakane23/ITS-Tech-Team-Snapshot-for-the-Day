#!/usr/bin/env python3
"""Read-only Freshservice ticket endpoint diagnostics. No ticket data output."""
import base64, json, os, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

DOMAIN = 'northfieldhospitalhelpdesk.freshservice.com'
KEY = os.getenv('FRESHSERVICE_API_KEY', '').strip()
STATUSES = [s.strip() for s in os.getenv('FRESHSERVICE_UNRESOLVED_STATUSES', '2,3').split(',') if s.strip()]
AGENTS = ['31000582795','31000589835','31000569854','31000569666','31000567881','31000054955']
if not KEY: raise SystemExit('Missing FRESHSERVICE_API_KEY secret')
AUTH = 'Basic ' + base64.b64encode((KEY + ':X').encode()).decode('ascii')

def request(label, path, params):
    url = 'https://' + DOMAIN + path + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': AUTH, 'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp: obj=json.load(resp)
        count = obj.get('total', 'not supplied') if isinstance(obj, dict) else 'not supplied'
        print(f'{label}: HTTP 200; total={count}', flush=True)
    except urllib.error.HTTPError as ex:
        print(f'{label}: HTTP {ex.code}', flush=True)
        try:
            data=json.loads(ex.read(4096))
            for e in (data.get('errors') or [])[:2]:
                print('  field=' + str(e.get('field','unknown'))[:50] + ' code=' + str(e.get('code','unknown'))[:50], flush=True)
        except Exception: pass
    except Exception as ex:
        print(f'{label}: {type(ex).__name__}', flush=True)

def filter_probe(name, expr):
    request(name, '/api/v2/tickets/filter', {'query':'"'+expr+'"','page':1})

print('Read-only Freshservice diagnostic: HTTP statuses and aggregate counts only')
filter_probe('1. Priority only (baseline)', 'priority:1')
filter_probe('2. Status only (Open)', 'status:2')
filter_probe('3. Status only (Pending)', 'status:3')
filter_probe('4. One team agent', 'agent_id:'+AGENTS[0])
filter_probe('5. Unassigned agent', 'agent_id:null')
cutoff=(datetime.now(timezone.utc)-timedelta(days=183)).strftime('%Y-%m-%d')
filter_probe('6. Recent creation', "created_at:>'"+cutoff+"'")
filter_probe('7. Combined status and agent', '(status:2 OR status:3) AND (agent_id:'+AGENTS[0]+' OR agent_id:null)')
request('8. Ticket LIST scoped to workspace 2', '/api/v2/tickets', {'workspace_id':2,'per_page':1,'page':1})
request('9. Ticket LIST scoped to all workspaces', '/api/v2/tickets', {'workspace_id':0,'per_page':1,'page':1})
print('Diagnostics complete; no dashboard files or ticket data modified.')

