#!/usr/bin/env python3
"""Read-only Freshservice count verification; does not publish or alter tickets.

Matches the shared 'Open Tickets by Tech Team' view by assignee (six agents
plus unassigned), six unresolved status IDs, and a rolling six-month window.
Prints aggregate priority totals only. GitHub Actions supplies API key in secret.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DOMAIN = 'northfieldhospitalhelpdesk.freshservice.com'
AGENTS = {
    'Carter': '31000582795', 'Alex': '31000589835',
    'Jake': '31000569854', 'Narith': '31000569666',
    'Scott': '31000567881', 'Tony': '31000054955',
    'Unassigned': None,
}
PRIORITY_IDS = {'Urgent': 4, 'High': 3, 'Medium': 2, 'Low': 1}
EXPECTED_STATUSES = {'2', '3', '6', '7', '8', '9'}
KEY = os.getenv('FRESHSERVICE_API_KEY', '').strip()
STATUSES = {s.strip() for s in os.getenv('FRESHSERVICE_UNRESOLVED_STATUSES', '').split(',') if s.strip()}
if not KEY:
    sys.exit('ERROR: FRESHSERVICE_API_KEY secret is missing.')
if STATUSES != EXPECTED_STATUSES:
    sys.exit('ERROR: Set FRESHSERVICE_UNRESOLVED_STATUSES to 2,3,6,7,8,9 before running.')

# Freshservice view uses a calendar six-month lookback, not 183 days.
def months_ago(date, months):
    year = date.year
    month = date.month - months
    while month < 1:
        month += 12
        year -= 1
    import calendar
    day = min(date.day, calendar.monthrange(year, month)[1])
    return date.replace(year=year, month=month, day=day)

cutoff = months_ago(datetime.now(timezone.utc), 6).strftime('%Y-%m-%d')
status_clause = '(' + ' OR '.join(f'status:{s}' for s in sorted(STATUSES, key=int)) + ')'
auth = 'Basic ' + base64.b64encode((KEY + ':X').encode()).decode('ascii')


def count(expression):
    params = urllib.parse.urlencode({'query': '"' + expression + '"', 'page': 1})
    url = f'https://{DOMAIN}/api/v2/tickets/filter?{params}'
    req = urllib.request.Request(url, headers={'Authorization': auth, 'Accept': 'application/json'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                data = json.load(response)
            result = data.get('total') if isinstance(data, dict) else None
            if not isinstance(result, int):
                raise ValueError('API response missing integer total')
            return result
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 2:
                time.sleep(4 * (attempt + 1))
                continue
            # Print no raw response body (may include sensitive information).
            raise RuntimeError(f'Freshservice HTTP {exc.code}; inspect filter syntax or API permissions') from None
        except urllib.error.URLError:
            raise RuntimeError('Freshservice connection failed') from None

print('Freshservice ticket count verification (read-only)', flush=True)
print(f'Created on/after: {cutoff} UTC (rolling six calendar months)', flush=True)
print('Statuses included: 2,3,6,7,8,9; Resolved 4 and Closed 5 excluded.', flush=True)
print('Agents: six named ITS technicians plus Unassigned.', flush=True)
print('Priority counts are computed from mutually exclusive agent and priority filters.', flush=True)

totals = {p: 0 for p in PRIORITY_IDS}
try:
    for name, agent_id in AGENTS.items():
        agent_clause = 'agent_id:null' if agent_id is None else f'agent_id:{agent_id}'
        per_agent = {}
        for priority, p_id in PRIORITY_IDS.items():
            expression = f'{status_clause} AND {agent_clause} AND created_at:>\'{cutoff}\' AND priority:{p_id}'
            per_agent[priority] = count(expression)
            totals[priority] += per_agent[priority]
        print(f'{name}: {sum(per_agent.values())} (aggregate count only)', flush=True)
except (RuntimeError, ValueError) as exc:
    print(f'VERIFICATION FAILED: {exc}', flush=True)
    print('No dashboard changes were made.', flush=True)
    sys.exit(1)

print('--- ITS Team Unresolved Ticket Snapshot ---', flush=True)
for label, n in totals.items():
    print(f'{label}: {n}', flush=True)
print(f'Total Unresolved: {sum(totals.values())}', flush=True)
print('Compare to Freshservice Open Tickets by Tech Team. No dashboard changes were made.', flush=True)



