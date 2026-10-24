#!/usr/bin/env python3
"""Read-only Freshservice cutoff comparison for 'Open Tickets by Tech Team'.

Compares current six-calendar-month created-after date to the prior calendar day.
Only aggregate counts are printed; does not modify tickets or dashboard files.
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
    return dt.date(year, month, day)


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
    statuses = [s.strip() for s in os.getenv('FRESHSERVICE_UNRESOLVED_STATUSES', '').split(',') if s.strip()]
    if set(statuses) != {'2', '3', '6', '7', '8', '9'}:
        raise SystemExit('Expected FRESHSERVICE_UNRESOLVED_STATUSES = 2,3,6,7,8,9')

    auth = base64.b64encode((key + ':X').encode()).decode('ascii')
    current_cutoff = six_month_cutoff()
    earlier_cutoff = current_cutoff - dt.timedelta(days=1)
    status_expr = '(' + ' OR '.join('status:' + s for s in statuses) + ')'
    totals = {day: {name: 0 for name in PRIORITIES} for day in (earlier_cutoff, current_cutoff)}

    print('Freshservice date-boundary comparison (READ ONLY)', flush=True)
    print('Current created-after date: {} UTC'.format(current_cutoff), flush=True)
    print('One-day-earlier created-after date: {} UTC'.format(earlier_cutoff), flush=True)
    print('Six unresolved statuses; six verified responder user IDs and unassigned', flush=True)
    print('No workspace_id in filter queries', flush=True)

    for person, responder_id in RESPONDERS.items():
        agent_expr = 'agent_id:null' if responder_id is None else 'agent_id:' + responder_id
        line = []
        for cutoff in (earlier_cutoff, current_cutoff):
            counts = {}
            for priority_name, priority_id in PRIORITIES.items():
                expr = (agent_expr + ' AND ' + status_expr +
                        " AND created_at:>'" + cutoff.isoformat() + "'" +
                        ' AND priority:' + str(priority_id))
                try:
                    counts[priority_name] = fetch_total(expr, auth)
                except RuntimeError as exc:
                    raise SystemExit('{} / {} / {}: {}'.format(person, cutoff, priority_name, exc))
                totals[cutoff][priority_name] += counts[priority_name]
                time.sleep(0.2)
            line.append('{} total={}'.format(cutoff, sum(counts.values())))
        print('{}: {}'.format(person, ' | '.join(line)), flush=True)

    print('--- PRIORITY COMPARISON ---', flush=True)
    print('Priority | Earlier cutoff | Current cutoff | Added by earlier cutoff', flush=True)
    for name in PRIORITIES:
        a, b = totals[earlier_cutoff][name], totals[current_cutoff][name]
        print('{} | {} | {} | +{}'.format(name, a, b, a - b), flush=True)
    a = sum(totals[earlier_cutoff].values())
    b = sum(totals[current_cutoff].values())
    print('TOTAL | {} | {} | +{}'.format(a, b, a - b), flush=True)
    print('Compare with Freshservice saved view at the same time; API requests may span several seconds.', flush=True)
    print('No Freshservice tickets or GitHub dashboard files were modified.', flush=True)


if __name__ == '__main__':
    main()


