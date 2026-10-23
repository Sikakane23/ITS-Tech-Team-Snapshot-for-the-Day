#!/usr/bin/env python3
"""Read-only Freshservice diagnostics: ticket filters and safe status-field metadata."""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

DOMAIN = 'northfieldhospitalhelpdesk.freshservice.com'
KEY = os.getenv('FRESHSERVICE_API_KEY', '').strip()
AGENTS = ['31000582795', '31000589835', '31000569854', '31000569666', '31000567881', '31000054955']
if not KEY:
    raise SystemExit('Missing FRESHSERVICE_API_KEY secret')
AUTH = 'Basic ' + base64.b64encode((KEY + ':X').encode()).decode('ascii')


def get(path, params=None):
    url = 'https://' + DOMAIN + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': AUTH, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def probe(label, expression):
    try:
        obj = get('/api/v2/tickets/filter', {'query': '"' + expression + '"', 'page': 1})
        print(f'{label}: HTTP 200; total={obj.get("total", "not supplied")}', flush=True)
    except urllib.error.HTTPError as ex:
        print(f'{label}: HTTP {ex.code}', flush=True)
    except Exception as ex:
        print(f'{label}: {type(ex).__name__}', flush=True)


def find_status_field(obj):
    if isinstance(obj, dict):
        if str(obj.get('name', '')).lower() == 'status' or str(obj.get('label', '')).lower() == 'status':
            return obj
        for value in obj.values():
            result = find_status_field(value)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = find_status_field(item)
            if result is not None:
                return result
    return None


def inspect_choice_tree(node, depth=0):
    """Print limited status option labels/IDs, never ticket content."""
    if depth > 5:
        return 0
    found = 0
    if isinstance(node, list):
        for item in node[:100]:
            found += inspect_choice_tree(item, depth + 1)
    elif isinstance(node, dict):
        label = next((node[k] for k in ('label', 'name', 'display_name', 'text') if isinstance(node.get(k), str)), None)
        value = next((node[k] for k in ('value', 'id', 'code', 'status_id') if isinstance(node.get(k), (int, str))), None)
        if label and value is not None:
            print(f'  Choice: {str(label)[:65]} | value={str(value)[:30]}', flush=True)
            found += 1
        for k, v in node.items():
            if isinstance(v, (list, dict)):
                found += inspect_choice_tree(v, depth + 1)
    return found


print('Freshservice read-only status diagnostics (no ticket records or secrets printed)', flush=True)
probe('1. Priority baseline', 'priority:1')
probe('2. Open status', 'status:2')
probe('3. Pending status', 'status:3')
probe('4. One team agent', 'agent_id:' + AGENTS[0])
probe('5. Unassigned', 'agent_id:null')
cutoff = (datetime.now(timezone.utc) - timedelta(days=183)).strftime('%Y-%m-%d')
probe('6. Created in last ~6 months', "created_at:>'" + cutoff + "'")
probe('7. Combined status and agent', '(status:2 OR status:3) AND (agent_id:' + AGENTS[0] + ' OR agent_id:null)')
print('8. Inspect Status field choices and sections (structure only):', flush=True)
try:
    obj = get('/api/v2/ticket_form_fields')
    field = find_status_field(obj)
    if field is None:
        print('  Status field not found in ticket_form_fields.', flush=True)
    else:
        print('  Status field ID: ' + str(field.get('id', 'not supplied')), flush=True)
        def describe(obj, prefix, depth=0):
            """Inspect metadata keys and nested primitive structure without dumping raw data."""
            if depth > 5: return
            if isinstance(obj, list):
                print(f'  {prefix}: list length={len(obj)}', flush=True)
                for i, item in enumerate(obj[:12]):
                    describe(item, f'{prefix}[{i}]', depth+1)
            elif isinstance(obj, dict):
                print(f'  {prefix}: object keys={",".join(sorted(obj.keys()))[:500]}', flush=True)
                # Only emit primitive values for tightly-scoped, status-related metadata
                for key in ('id','value','code','status_id','label','name','display_name','text'):
                    v = obj.get(key)
                    if isinstance(v, (str,int,float,bool)):
                        print(f'    {key}={str(v)[:80]}', flush=True)
                for key, v in obj.items():
                    if isinstance(v, (dict,list)):
                        describe(v, f'{prefix}.{key}', depth+1)
            else:
                print(f'  {prefix}: {type(obj).__name__}', flush=True)
        for key in ('choices','sections'):
            if key in field:
                describe(field[key], 'status.'+key)
            else:
                print('  status.'+key+' missing', flush=True)
except urllib.error.HTTPError as ex:
    print(f'  Ticket form fields HTTP {ex.code}', flush=True)
except Exception as ex:
    print(f'  Ticket form fields error: {type(ex).__name__}', flush=True)
print('Diagnostic complete. No Freshservice tickets or dashboard files modified.', flush=True)


