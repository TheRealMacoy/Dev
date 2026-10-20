"""Find Cape Town businesses that have no website.

    python -m leadfinder                                  # OpenStreetMap, free, no key
    python -m leadfinder --source google                  # Google Maps via Places API key
    python -m leadfinder --categories plumber,barber --areas "Woodstock,Bellville"
    python -m leadfinder --source google --include-social --max-requests 50 --no-sheet
"""

import argparse
import logging
import os
import sys

from . import osm
from .config import AREAS, CATEGORIES
from .output import write_csv, write_sheet
from .places import Budget, find_businesses

log = logging.getLogger("leadfinder")


def _split(value):
    return [s.strip() for s in value.split(",") if s.strip()]


def main(argv=None):
    p = argparse.ArgumentParser(description="Find Cape Town businesses with no website.")
    p.add_argument("--source", choices=["osm", "google"], default="osm",
                   help="osm: OpenStreetMap, free with no key (default); google: Places API, needs a key")
    p.add_argument("--categories", help="comma-separated, e.g. 'plumber,hair salon' (default: config.py list)")
    p.add_argument("--areas", help="comma-separated Cape Town suburbs (default: config.py list)")
    p.add_argument("--include-social", action="store_true",
                   help="also keep businesses whose only 'website' is a Facebook/Instagram/etc. page")
    p.add_argument("--min-reviews", type=int, default=0,
                   help="skip places with fewer Google reviews (google source only)")
    p.add_argument("--require-phone", action="store_true", help="skip places with no phone number")
    p.add_argument("--max-requests", type=int, default=200,
                   help="cap on billable Places API calls (google source only, default 200)")
    p.add_argument("--no-sheet", action="store_true", help="don't write to Google Sheets")
    p.add_argument("--csv", default="leads.csv", help="CSV output path ('' to disable)")
    p.add_argument("--sheet-id", default=os.environ.get("GOOGLE_SHEET_ID"))
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")

    if args.source == "osm":
        if args.min_reviews:
            log.warning("OpenStreetMap has no reviews; ignoring --min-reviews")
            args.min_reviews = 0
        found = osm.find_businesses(_split(args.categories) if args.categories else None,
                                    _split(args.areas) if args.areas else None)
        log.info("Found %d named businesses on OpenStreetMap", len(found))
    else:
        api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
        if not api_key:
            sys.exit("GOOGLE_PLACES_API_KEY is not set. Use --source osm for the free option, "
                     "or see README: 'Cape Town lead finder'.")
        categories = _split(args.categories) if args.categories else CATEGORIES
        areas = _split(args.areas) if args.areas else AREAS
        budget = Budget(args.max_requests)
        found = find_businesses(api_key, categories, areas, budget)
        log.info("Found %d unique businesses using %d API requests", len(found), budget.used)

    keep = {"none", "social-only"} if args.include_social else {"none"}
    leads = [b for b in found
             if b.presence in keep
             and b.reviews >= args.min_reviews
             and (b.phone or not args.require_phone)]
    leads.sort(key=lambda b: (b.category, -b.reviews))
    log.info("%d have no website%s", len(leads), " (or only a social page)" if args.include_social else "")

    if args.csv:
        write_csv(leads, args.csv)
    if not args.no_sheet:
        if args.sheet_id:
            write_sheet(leads, args.sheet_id)
        else:
            log.warning("GOOGLE_SHEET_ID not set, skipping Google Sheets output")

    for b in leads[:15]:
        log.info("  %-35.35s %-20.20s %-15s %s", b.name, b.category, b.phone, b.presence)


if __name__ == "__main__":
    main()
