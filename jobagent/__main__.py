"""Run the remote job agent.

    python -m jobagent                      # scrape, filter, rank, write sheet (+ CSV)
    python -m jobagent --no-sheet           # CSV only
    python -m jobagent --sources remotive,himalayas --max-age 14
"""

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone

from .filters import apply_filters
from .sheets import write_csv, write_sheet
from .sources import SOURCES, fetch_all

log = logging.getLogger("jobagent")


def main(argv=None):
    p = argparse.ArgumentParser(description="Find worldwide-remote jobs matching the CV.")
    p.add_argument("--max-age", type=int, default=21, help="max posting age in days (default 21)")
    p.add_argument("--sources", help=f"comma-separated subset of: {', '.join(SOURCES)}")
    p.add_argument("--min-fit", type=int, default=55, help="minimum Claude fit score (0-100)")
    p.add_argument("--no-llm", action="store_true", help="skip Claude ranking, use keyword score only")
    p.add_argument("--no-sheet", action="store_true", help="don't write to Google Sheets")
    p.add_argument("--csv", default="jobs.csv", help="CSV output path ('' to disable)")
    p.add_argument("--sheet-id", default=os.environ.get("GOOGLE_SHEET_ID"))
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.max_age)
    only = set(args.sources.split(",")) if args.sources else None
    raw = fetch_all(cutoff=cutoff, only=only)
    log.info("Fetched %d postings in total", len(raw))

    jobs = apply_filters(raw, max_age_days=args.max_age)
    log.info("%d fresh, worldwide postings match the CV keywords", len(jobs))

    if jobs and not args.no_llm and os.environ.get("ANTHROPIC_API_KEY"):
        from .ranker import rank_with_claude

        jobs = rank_with_claude(jobs, min_fit=args.min_fit)
        log.info("%d postings kept after Claude review", len(jobs))
    elif not args.no_llm:
        log.info("ANTHROPIC_API_KEY not set, skipping Claude review")

    if args.csv:
        write_csv(jobs, args.csv)
    if not args.no_sheet:
        if args.sheet_id:
            write_sheet(jobs, args.sheet_id)
        else:
            log.warning("GOOGLE_SHEET_ID not set, skipping Google Sheets output")

    for j in jobs[:15]:
        log.info("  %3d  %-45.45s %-25.25s %s", j.score, j.title, j.company, j.url)


if __name__ == "__main__":
    main()
