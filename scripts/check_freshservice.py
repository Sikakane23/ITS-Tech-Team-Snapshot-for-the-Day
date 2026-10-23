#!/usr/bin/env python3
"""Read-only Freshservice ticket #10574 assignment verification.

Prints only numeric ticket metadata, never ticket contents or credentials.
"""
import base64
import json
import os
import urllib.error
import urllib.request

DOMAIN = "northfieldhospitalhelpdesk.freshservice.com"
TICKET_ID = 10574
JAKE_AGENT_ID = 31000569854


def main():
    key = os.environ.get("FRESHSERVICE_API_KEY", "").strip()
    if not key:
        raise SystemExit("Missing FRESHSERVICE_API_KEY GitHub Actions secret")

    auth = base64.b64encode(f"{key}:X".encode("utf-8")).decode("ascii")
    url = f"https://{DOMAIN}/api/v2/tickets/{TICKET_ID}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        print(f"Freshservice ticket lookup returned HTTP {error.code}")
        raise SystemExit(1)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"Ticket lookup failed ({type(error).__name__}).")
        raise SystemExit(1)

    ticket = payload.get("ticket", {})
    if not isinstance(ticket, dict) or not ticket:
        raise SystemExit("Response did not contain a ticket object")
    responder = ticket.get("responder_id")
    print("Freshservice ticket assignment verification (read-only)")
    print(f"Ticket ID: {ticket.get('id')}")
    print(f"Ticket responder_id: {responder}")
    print(f"Jake agent ID provided: {JAKE_AGENT_ID}")
    print(f"IDs match: {str(responder == JAKE_AGENT_ID)}")
    print(f"Ticket status ID: {ticket.get('status')}")
    print(f"Ticket priority ID: {ticket.get('priority')}")
    print("No ticket content, API credentials, or dashboard files were modified or printed.")


if __name__ == "__main__":
    main()


