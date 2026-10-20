"""Output: append new jobs to a Google Sheet (deduped by link) and/or a CSV."""

import csv
import json
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger(__name__)

HEADER = ["Date Found", "Posted", "Title", "Company", "Location", "Source",
          "Match Score", "Matched Skills", "Why It Fits", "Apply Link", "Status"]
LINK_COL = HEADER.index("Apply Link")


def to_row(job, found_on):
    return [
        found_on,
        job.posted_at.strftime("%Y-%m-%d") if job.posted_at else "",
        job.title,
        job.company,
        job.location,
        job.source,
        round(job.score),
        ", ".join(job.matched[:8]),
        job.reason,
        job.url,
        "New",
    ]


def write_csv(jobs, path):
    found_on = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(to_row(j, found_on) for j in jobs)
    log.info("Wrote %d jobs to %s", len(jobs), path)


def _credentials():
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return Credentials.from_service_account_info(json.loads(raw), scopes=scopes)
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
    return Credentials.from_service_account_file(path, scopes=scopes)


def write_sheet(jobs, sheet_id, tab="Jobs"):
    """Append jobs not already in the sheet. Returns the number of rows added."""
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
        ws.format("A1:K1", {"textFormat": {"bold": True}})
        existing = [HEADER] + existing

    seen = {r[LINK_COL].strip() for r in existing[1:] if len(r) > LINK_COL}
    found_on = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_rows = [to_row(j, found_on) for j in jobs if j.url.strip() not in seen]
    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")
    log.info("Added %d new jobs to sheet (%d already present)", len(new_rows), len(jobs) - len(new_rows))
    return len(new_rows)
