#!/usr/bin/env python3
"""Read-only Freshservice verification for 'Open Tickets by Tech Team'.

Counts only aggregate tickets; prints no ticket bodies, names, requester information,
or credentials. Does not modify Freshservice or GitHub Pages.
"""
import base64
import calendar
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

DOMAIN = 'northfieldhospitalhelpdesk.freshservice.com'
# These are agent *user_id* values, which match ticket responder_id, NOT agent profile IDs.
RESPONDERS = {
    'Jake': '31002265863',
    'Carter': '31002831368',
    'Alex': '31003211115',
    'Narith': '31002265840',
    'Scott': '31002265627',
    'Tony': '31000194430',
    'Unassigned': None,
}
PRIORITIES = {'Urgent': 4, 'High': 3, 'Medium': 2, 'Low': 1}


def six_month_cutoff():
    today = dt.datetime.now(dt.timezone.utc).date()
    month_index = today.year * 12 + (today.month - 1) - 6
    year, month = divmod(month_index, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day).isoformat()


def fetch_total(expression, auth):
    url = 'https://' + DOMAIN + '/api/v2/tickets/filter?' + urllib.parse.urlencode({
        'query': '"' + expression + '"', 'page': 1
    })
    req = urllib.request.Request(url, headers={
        'Authorization': 'Basic ' + auth, 'Accept': 'application/json'
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                obj = json.load(response)
            if not isinstance(obj, dict) or not isinstance(obj.get('total'), int):
                raise RuntimeError('The ticket filter response did not contain a numeric total')
            return obj['total']
        except urllib.error.HTTPError as error:
            if error.code in (429, 502, 503, 504) and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            # Do not print potentially sensitive API response bodies.
            raise RuntimeError('Freshservice rejected a filtered count (HTTP {})'.format(error.code)) from None
        except urllib.error.URLError:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError('Freshservice network request failed') from None


def main():
    key = os.getenv('FRESHSERVICE_API_KEY', '').strip()
    if not key:
        raise SystemExit('Missing FRESHSERVICE_API_KEY secret')
    status_raw = os.getenv('FRESHSERVICE_UNRESOLVED_STATUSES', '').strip()
    statuses = [s.strip() for s in status_raw.split(',') if s.strip()]
    if set(statuses) != {'2', '3', '6', '7', '8', '9'}:
        raise SystemExit('Expected FRESHSERVICE_UNRESOLVED_STATUSES = 2,3,6,7,8,9')
    auth = base64.b64encode((key + ':X').encode()).decode('ascii')
    cutoff = six_month_cutoff()
    status_expr = '(' + ' OR '.join('status:' + s for s in statuses) + ')'
    date_expr = "created_at:>'" + cutoff + "'"
    grand = {name: 0 for name in PRIORITIES}
    print('Freshservice Open Tickets by Tech Team (verification only)', flush=True)
    print('Created after ' + cutoff + ' (UTC); six unresolved statuses; all six responders plus unassigned', flush=True)
    print('No workspace_id included in filter queries (known invalid_field)', flush=True)
    for person, responder_id in RESPONDERS.items():
        agent_expr = 'agent_id:null' if responder_id is None else 'agent_id:' + responder_id
        counts = {}
        for name, priority in PRIORITIES.items():
            expr = agent_expr + ' AND ' + status_expr + ' AND ' + date_expr + ' AND priority:' + str(priority)
            try:
                counts[name] = fetch_total(expr, auth)
            except RuntimeError as e:
                raise SystemExit('{} / {}: {}'.format(person, name, e))
            grand[name] += counts[name]
            time.sleep(0.2)
        print('{}: {}'.format(person, ', '.join('{}={}'.format(k, v) for k, v in counts.items())) +
              '; total={}'.format(sum(counts.values())), flush=True)
    print('--- FINAL AGGREGATE COUNTS ---', flush=True)
    for name, count in grand.items():
        print('{}: {}'.format(name, count), flush=True)
    print('Total unresolved: {}'.format(sum(grand.values())), flush=True)
    print('Compare these numbers with Freshservice saved view before enabling any publishing.', flush=True)
    print('NO ticket records or dashboard files changed.', flush=True)


if __name__ == '__main__':
    main()


