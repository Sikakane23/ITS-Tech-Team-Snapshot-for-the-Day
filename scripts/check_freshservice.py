#!/usr/bin/env python3
"""Read-only verification of Freshservice ticket view counts. No ticket records are saved."""
import base64, calendar, datetime as dt, json, os, sys, time, urllib.error, urllib.parse, urllib.request

DOMAIN = "northfieldhospitalhelpdesk.freshservice.com"
API_KEY = os.environ.get("FRESHSERVICE_API_KEY", "")
# Configurable numeric agent IDs, obtained from Freshservice agent profiles/API.
AGENT_IDS = [int(x.strip()) for x in os.environ.get("FRESHSERVICE_AGENT_IDS", "").split(",") if x.strip()]
# Freshservice default unresolved statuses: Open=2, Pending=3. Custom status codes may require additions.
STATUS_IDS = [int(x.strip()) for x in os.environ.get("FRESHSERVICE_UNRESOLVED_STATUSES", "2,3").split(",") if x.strip()]
WORKSPACE_ID = os.environ.get("FRESHSERVICE_WORKSPACE_ID", "").strip()

def six_months_ago(now):
    year, month = now.year, now.month - 6
    while month <= 0: year, month = year - 1, month + 12
    day = min(now.day, calendar.monthrange(year, month)[1])
    return now.replace(year=year, month=month, day=day)

def api(endpoint, params):
    url = f"https://{DOMAIN}/api/v2/{endpoint}?" + urllib.parse.urlencode(params)
    auth = base64.b64encode((API_KEY + ':X').encode()).decode()
    request = urllib.request.Request(url, headers={"Authorization": "Basic " + auth, "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt + 1); continue
            print(f"Freshservice API returned HTTP {e.code} for {endpoint}; verify role/scope/filter settings.", file=sys.stderr)
            sys.exit(1)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 3: time.sleep(2 ** attempt + 1); continue
            print(f"Network request failed: {type(e).__name__}", file=sys.stderr)
            sys.exit(1)

def main():
    if not API_KEY:
        sys.exit("Missing FRESHSERVICE_API_KEY GitHub Actions secret.")
    if not AGENT_IDS or len(set(AGENT_IDS)) != 6:
        sys.exit("Set FRESHSERVICE_AGENT_IDS to the six unique numeric agent IDs, separated by commas. No API query was run.")
    if not STATUS_IDS:
        sys.exit("Provide at least one unresolved status ID.")
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = six_months_ago(now).strftime('%Y-%m-%d')
    # Query individually by priority/assignee to keep queries short and avoid filter query limits.
    # Unassigned means agent_id:null across ALL groups, exactly as the saved view describes.
    counts = {"Urgent":0,"High":0,"Medium":0,"Low":0}
    priorities={1:'Low',2:'Medium',3:'High',4:'Urgent'}
    assignees = ['null'] + [str(x) for x in AGENT_IDS]
    for priority, name in priorities.items():
        for assigned in assignees:
            for status in STATUS_IDS:
                expression = f"created_at:>'{cutoff}' AND agent_id:{assigned} AND status:{status} AND priority:{priority}"
                args={'query':f'"{expression}"','page':1}
                if WORKSPACE_ID: args['workspace_id']=WORKSPACE_ID
                result=api('tickets/filter', args)
                count=result.get('total')
                if not isinstance(count, int):
                    sys.exit('No numeric total returned by Freshservice; cannot safely publish.')
                counts[name]+=count
    total=sum(counts.values())
    print(f"Freshservice count verification (created on/after {cutoff}; UTC):")
    print(f"Urgent: {counts['Urgent']} | High: {counts['High']} | Medium: {counts['Medium']} | Low: {counts['Low']} | Total: {total}")
    print('Compare this with Open Tickets by Tech Team. This verification does NOT update GitHub Pages.')
    print('Note: match exact six-month cutoff and any custom unresolved status codes before enabling publishing.')

if __name__=='__main__': main()
