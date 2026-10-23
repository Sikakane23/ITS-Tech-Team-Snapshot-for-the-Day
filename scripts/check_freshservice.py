#!/usr/bin/env python3
"""Read-only Freshservice diagnostics: ticket filters and Status choice IDs.

Never prints API credentials, tickets, requesters, or full API responses.
"""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

DOMAIN = 'northfieldhospitalhelpdesk.freshservice.com'
KEY = os.getenv('FRESHSERVICE_API_KEY', '').strip()
AGENTS = ['31000582795', '31000589835', '31000569854', '31000569666', '31000567881', '31000054955']
if not KEY:
    raise SystemExit('Missing FRESHSERVICE_API_KEY secret')
AUTH = 'Basic ' + base64.b64encode((KEY + ':X').encode()).decode('ascii')


def get_json(path, params=None):
    url = 'https://' + DOMAIN + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': AUTH, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def request_count(label, path, params):
    try:
        obj = get_json(path, params)
        total = obj.get('total', 'not supplied') if isinstance(obj, dict) else 'not supplied'
        print(f'{label}: HTTP 200; total={total}', flush=True)
    except urllib.error.HTTPError as err:
        print(f'{label}: HTTP {err.code}', flush=True)
    except Exception as err:
        print(f'{label}: {type(err).__name__}', flush=True)


def filter_probe(name, expr):
    request_count(name, '/api/v2/tickets/filter', {'query': '"' + expr + '"', 'page': 1})


print('Read-only diagnostics: counts and ticket STATUS field definitions only', flush=True)
filter_probe('1. Priority only', 'priority:1')
filter_probe('2. Open status', 'status:2')
filter_probe('3. Pending status', 'status:3')
filter_probe('4. One team agent', 'agent_id:' + AGENTS[0])
filter_probe('5. Unassigned', 'agent_id:null')
cutoff = (datetime.now(timezone.utc) - timedelta(days=183)).strftime('%Y-%m-%d')
filter_probe('6. Recent creation', "created_at:>'" + cutoff + "'")
filter_probe('7. Combined status + agent', '(status:2 OR status:3) AND (agent_id:' + AGENTS[0] + ' OR agent_id:null)')
request_count('8. Ticket list workspace 2', '/api/v2/tickets', {'workspace_id': 2, 'per_page': 1, 'page': 1})

print('9. Reading ticket-form STATUS field (labels and IDs only):', flush=True)
try:
    obj = get_json('/api/v2/ticket_form_fields')
    fields = obj if isinstance(obj, list) else (obj.get('ticket_fields') or obj.get('ticket_form_fields') or [])
    matches = [f for f in fields if isinstance(f, dict) and (
        str(f.get('name', '')).lower() == 'status' or
        str(f.get('field_type', '')).lower() == 'default_status' or
        str(f.get('label', '')).lower() == 'status'
    )]
    if not matches:
        print('  Status field not identified in API response. No other fields printed.', flush=True)
    for f in matches:
        print('  Status field identified; field ID=' + str(f.get('id', 'not supplied')), flush=True)
        options = f.get('choices') or f.get('field_options') or f.get('options') or []
        if isinstance(options, dict):
            options = options.get('choices') or options.get('statuses') or options.get('options') or []
        if isinstance(options, dict):
            options = [{'label': k, 'value': v} for k, v in options.items()]
        if not isinstance(options, list) or not options:
            print('  No status choices found in known API response fields; numeric status IDs still unverified.', flush=True)
        else:
            allowed = {'assigned', 'closed', 'hold', 'in process', 'open', 'pending', 'resolved', 'waiting on vendor'}
            for choice in options:
                if not isinstance(choice, dict):
                    continue
                label = str(choice.get('label') or choice.get('name') or choice.get('text') or '')
                if label.strip().lower() not in allowed:
                    continue
                value = choice.get('value', choice.get('id', choice.get('key', 'not supplied')))
                print(f'  {label}: status value={value}', flush=True)
except urllib.error.HTTPError as err:
    print('  Ticket form fields endpoint returned HTTP ' + str(err.code) + '; may need ticket-field read permission.', flush=True)
except Exception as err:
    print('  Ticket form fields lookup: ' + type(err).__name__, flush=True)
print('Diagnostic complete. No ticket or dashboard records modified.', flush=True)

