"""Output: write leads to a CSV and/or append new ones to a Google Sheet (deduped by place ID)."""

import csv
import json
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger(__name__)

HEADER = ["Date Found", "Business", "Category", "Phone", "Address", "Web Presence",
          "Social Link", "Rating", "Reviews", "Map Link", "Place ID", "Status"]
ID_COL = HEADER.index("Place ID")


def to_row(b, found_on):
    return [
        found_on, b.name, b.category, b.phone, b.address, b.presence,
        b.website if b.presence == "social-only" else "",
        b.rating if b.rating is not None else "", b.reviews, b.maps_url, b.place_id, "New",
    ]


def write_csv(leads, path):
    found_on = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(to_row(b, found_on) for b in leads)
    log.info("Wrote %d leads to %s", len(leads), path)


def _credentials():
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return Credentials.from_service_account_info(json.loads(raw), scopes=scopes)
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
    return Credentials.from_service_account_file(path, scopes=scopes)


def write_sheet(leads, sheet_id, tab="Leads"):
    """Append leads not already in the sheet. Returns the number of rows added."""
    import gspread

    gc = gspread.authorize(_credentials())
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=1000, cols=len(HEADER))

    existing = ws.get_all_values()
    if not existing or existing[0][: len(HEADER)] != HEADER:
        if existing and any(existing[0]):
            ws.insert_row(HEADER, 1)
        else:
            ws.update(range_name="A1", values=[HEADER])
        ws.freeze(rows=1)
        ws.format("A1:L1", {"textFormat": {"bold": True}})
        existing = [HEADER] + existing

    seen = {r[ID_COL].strip() for r in existing[1:] if len(r) > ID_COL}
    found_on = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_rows = [to_row(b, found_on) for b in leads if b.place_id not in seen]
    if new_rows:
        ws.append_rows(new_rows, value_input_option="RAW")
    log.info("Added %d new leads to sheet (%d already present)", len(new_rows), len(leads) - len(new_rows))
    return len(new_rows)
