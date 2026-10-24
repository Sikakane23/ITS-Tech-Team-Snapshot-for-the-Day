#!/usr/bin/env python3
"""Publish only aggregate Freshservice counts. Never output or store ticket details."""
import base64
import calendar
import datetime as dt
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

DOMAIN = 'northfieldhospitalhelpdesk.freshservice.com'
RESPONDERS = {'Jake':'31002265863','Carter':'31002831368','Alex':'31003211115',
              'Narith':'31002265840','Scott':'31002265627','Tony':'31000194430',
              'Unassigned':None}
PRIORITIES = {'Urgent':4,'High':3,'Medium':2,'Low':1}
OUTPUT = Path('ticket-stats.json')

def cutoff():
    now=dt.datetime.now(dt.timezone.utc).date()
    index=now.year*12+now.month-1-6
    year,month=divmod(index,12)
    month+=1
    return dt.date(year,month,min(now.day,calendar.monthrange(year,month)[1])).isoformat()

def count(expr, auth):
    url=f'https://{DOMAIN}/api/v2/tickets/filter?'+urllib.parse.urlencode({'query':'"'+expr+'"','page':1})
    req=urllib.request.Request(url,headers={'Authorization':'Basic '+auth,'Accept':'application/json'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req,timeout=35) as resp:
                body=json.load(resp)
            n=body.get('total') if isinstance(body,dict) else None
            if not isinstance(n,int) or isinstance(n,bool) or n<0:
                raise RuntimeError('Invalid aggregate count response')
            return n
        except urllib.error.HTTPError as e:
            if e.code in (429,502,503,504) and attempt<3:
                time.sleep(3*(attempt+1));continue
            raise RuntimeError(f'Freshservice HTTP {e.code}') from None
        except urllib.error.URLError:
            if attempt<3:
                time.sleep(2*(attempt+1));continue
            raise RuntimeError('Freshservice network error') from None

def main():
    key=os.environ.get('FRESHSERVICE_API_KEY','').strip()
    if not key: raise SystemExit('Missing FRESHSERVICE_API_KEY')
    statuses=[x.strip() for x in os.environ.get('FRESHSERVICE_UNRESOLVED_STATUSES','').split(',') if x.strip()]
    if set(statuses)!={'2','3','6','7','8','9'}: raise SystemExit('Incorrect unresolved status configuration')
    auth=base64.b64encode((key+':X').encode()).decode()
    status_expr='('+' OR '.join('status:'+x for x in statuses)+')'
    date_expr="created_at:>'"+cutoff()+"'"
    counts={x:0 for x in PRIORITIES}
    for person,user_id in RESPONDERS.items():
        agent='agent_id:null' if user_id is None else 'agent_id:'+user_id
        for priority,number in PRIORITIES.items():
            expr=agent+' AND '+status_expr+' AND '+date_expr+' AND priority:'+str(number)
            counts[priority]+=count(expr,auth)
            time.sleep(.15)
    total=sum(counts.values())
    if total<1: raise SystemExit('Refusing to publish zero tickets without review')
    if OUTPUT.exists():
        try:
            previous=json.loads(OUTPUT.read_text()).get('total',0)
            if previous and total<previous*.5:
                raise SystemExit('Refusing to publish suspicious decrease of over 50%')
        except (ValueError,TypeError,OSError):
            raise SystemExit('Existing snapshot unreadable; publication stopped')
    payload={'total':total,'priorities':counts,'updated_at':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'),
             'source':'Freshservice Open Tickets by Tech Team (API approximation)'}
    OUTPUT.write_text(json.dumps(payload,indent=2)+'\n')
    print('Aggregate snapshot verified:', 'total='+str(total), ', '.join(f'{p}={n}' for p,n in counts.items()))

if __name__=='__main__':main()
