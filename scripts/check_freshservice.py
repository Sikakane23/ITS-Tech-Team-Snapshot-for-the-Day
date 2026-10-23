#!/usr/bin/env python3
"""Read-only Freshservice filter diagnostics. Prints only HTTP status and aggregate counts."""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

DOMAIN = 'northfieldhospitalhelpdesk.freshservice.com'
API_KEY = os.getenv('FRESHSERVICE_API_KEY', '').strip()
WORKSPACE = os.getenv('FRESHSERVICE_WORKSPACE_ID', '').strip()
STATUSES = [s.strip() for s in os.getenv('FRESHSERVICE_UNRESOLVED_STATUSES', '2,3').split(',') if s.strip()]

if not API_KEY:
    raise SystemExit('Missing GitHub secret FRESHSERVICE_API_KEY')

def probe(label, expression, workspace):
    params = {'query': '"' + expression + '"', 'page': '1'}
    if workspace != '':
        params['workspace_id'] = workspace
    url = 'https://' + DOMAIN + '/api/v2/tickets/filter?' + urllib.parse.urlencode(params)
    creds = base64.b64encode((API_KEY + ':X').encode()).decode('ascii')
    req = urllib.request.Request(url, headers={'Authorization': 'Basic ' + creds, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.load(response)
        count = data.get('total')
        print(f'{label}: HTTP 200; total={count if isinstance(count,int) else "not supplied"}', flush=True)
        return True
    except urllib.error.HTTPError as ex:
        print(f'{label}: HTTP {ex.code}', flush=True)
        # Only print validation error names and descriptions; not URLs, requests, headers, or ticket data.
        try:
            body = json.loads(ex.read(8192).decode('utf-8', 'replace'))
            if isinstance(body, dict):
                for err in body.get('errors', [])[:3]:
                    if isinstance(err, dict):
                        print('  field=' + str(err.get('field', 'unknown'))[:60] + ' code=' + str(err.get('code', 'unknown'))[:60], flush=True)
                if isinstance(body.get('message'), str):
                    print('  error category=' + body['message'][:140], flush=True)
        except Exception:
            pass
        return False
    except Exception as ex:
        print(f'{label}: {type(ex).__name__}', flush=True)
        return False

print('Freshservice filter diagnostics (read-only; no ticket records output)')
print('Configured workspace:', WORKSPACE or '(not set)')
probe('A: priority only / no workspace', 'priority:1', '')
if WORKSPACE:
    probe('B: priority only / configured workspace', 'priority:1', WORKSPACE)
    if WORKSPACE != '2':
        probe('C: priority only / ITS workspace 2', 'priority:1', '2')
else:
    probe('B: priority only / ITS workspace 2', 'priority:1', '2')
for name, expr in [
    ('status only', f'status:{STATUSES[0] if STATUSES else "2"}'),
    ('unassigned only', 'agent_id:null'),
    ('creation-date only', "created_at:>'2026-04-23'"),
    ('priority and status', f'priority:1 AND status:{STATUSES[0] if STATUSES else "2"}'),
]:
    probe(name + ' / workspace 2', expr, '2')
print('Diagnostic finished. No dashboard data was changed.')

