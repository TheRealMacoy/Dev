"""Fetchers for remote job boards that publish open feeds/APIs.

Each fetcher returns a list of Job objects and never raises: a board that is
down or changes its format is logged and skipped so the rest still run.
"""

import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from .models import Job

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; remote-job-agent/1.0; personal job search)",
    "Accept": "application/json, application/rss+xml, text/xml, */*",
}
TIMEOUT = 30


def _get(url, **params):
    resp = requests.get(url, params=params or None, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_date(value):
    """Parse ISO-8601, RFC-822 or epoch (s/ms) dates into aware UTC datetimes."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            ts = float(value)
            if ts > 1e12:
                ts /= 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        s = str(value).strip()
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def fetch_remotive():
    data = _get("https://remotive.com/api/remote-jobs").json()
    return [
        Job(
            title=j.get("title", ""),
            company=j.get("company_name", ""),
            url=j.get("url", ""),
            source="Remotive",
            location=j.get("candidate_required_location", "") or "",
            posted_at=parse_date(j.get("publication_date")),
            description=strip_html(j.get("description")),
            tags=list(j.get("tags") or []) + [j.get("category", "")],
        )
        for j in data.get("jobs", [])
    ]


def fetch_remoteok():
    data = _get("https://remoteok.com/api").json()
    jobs = []
    for j in data:
        if not isinstance(j, dict) or "position" not in j:
            continue  # first element is a legal notice
        jobs.append(
            Job(
                title=j.get("position", ""),
                company=j.get("company", ""),
                url=j.get("apply_url") or j.get("url", ""),
                source="RemoteOK",
                location=j.get("location", "") or "",
                posted_at=parse_date(j.get("epoch") or j.get("date")),
                description=strip_html(j.get("description")),
                tags=list(j.get("tags") or []),
            )
        )
    return jobs


def fetch_weworkremotely():
    root = ET.fromstring(_get("https://weworkremotely.com/remote-jobs.rss").content)
    jobs = []
    for item in root.iter("item"):
        raw_title = item.findtext("title", "")
        company, _, title = raw_title.partition(":")
        if not title:
            company, title = "", raw_title
        jobs.append(
            Job(
                title=title.strip(),
                company=company.strip(),
                url=item.findtext("link", ""),
                source="We Work Remotely",
                location=item.findtext("region", "") or "",
                posted_at=parse_date(item.findtext("pubDate")),
                description=strip_html(item.findtext("description")),
                tags=[item.findtext("category", "")],
            )
        )
    return jobs


def fetch_jobicy():
    data = _get("https://jobicy.com/api/v2/remote-jobs", count=100, geo="anywhere").json()
    return [
        Job(
            title=html.unescape(j.get("jobTitle", "")),
            company=j.get("companyName", ""),
            url=j.get("url", ""),
            source="Jobicy",
            location=j.get("jobGeo", "") or "",
            posted_at=parse_date(j.get("pubDate")),
            description=strip_html(j.get("jobDescription") or j.get("jobExcerpt")),
            tags=list(j.get("jobIndustry") or []),
        )
        for j in data.get("jobs", [])
    ]


def fetch_himalayas(max_pages=25, cutoff=None):
    jobs = []
    for page in range(max_pages):
        data = _get("https://himalayas.app/jobs/api", limit=20, offset=page * 20).json()
        batch = data.get("jobs", [])
        if not batch:
            break
        for j in batch:
            restrictions = j.get("locationRestrictions") or []
            jobs.append(
                Job(
                    title=j.get("title", ""),
                    company=j.get("companyName", ""),
                    url=j.get("applicationLink") or j.get("guid", ""),
                    source="Himalayas",
                    location=", ".join(restrictions) if restrictions else "Worldwide",
                    posted_at=parse_date(j.get("pubDate")),
                    description=strip_html(j.get("description") or j.get("excerpt")),
                    tags=list(j.get("categories") or []),
                    worldwide_hint=not restrictions,
                )
            )
        # Results are newest first; stop paging once we're past the window.
        oldest = jobs[-1].posted_at
        if cutoff and oldest and oldest < cutoff:
            break
    return jobs


def fetch_workingnomads():
    data = _get("https://www.workingnomads.com/api/exposed_jobs/").json()
    return [
        Job(
            title=j.get("title", ""),
            company=j.get("company_name", ""),
            url=j.get("url", ""),
            source="Working Nomads",
            location=j.get("location", "") or "",
            posted_at=parse_date(j.get("pub_date")),
            description=strip_html(j.get("description")),
            tags=[t.strip() for t in (j.get("tags") or "").split(",") if t.strip()]
            + [j.get("category_name", "")],
        )
        for j in data
    ]


SOURCES = {
    "remotive": fetch_remotive,
    "remoteok": fetch_remoteok,
    "weworkremotely": fetch_weworkremotely,
    "jobicy": fetch_jobicy,
    "himalayas": fetch_himalayas,
    "workingnomads": fetch_workingnomads,
}


def fetch_all(cutoff=None, only=None):
    jobs = []
    for name, fn in SOURCES.items():
        if only and name not in only:
            continue
        try:
            found = fn(cutoff=cutoff) if name == "himalayas" else fn()
            log.info("%-15s %4d jobs", name, len(found))
            jobs.extend(found)
        except Exception as exc:  # one broken board shouldn't stop the run
            log.warning("%-15s failed: %s", name, exc)
    return jobs
