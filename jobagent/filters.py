"""Freshness, worldwide-remote and CV keyword filters."""

import re
from datetime import datetime, timedelta, timezone

from . import profile

WORLDWIDE_LOCATIONS = re.compile(
    r"\b(worldwide|world ?wide|anywhere|global(ly)?|international|"
    r"work from anywhere|all countries|any location|earth|planet earth)\b",
    re.I,
)
# Text in the location field that narrows it to a region, even next to "anywhere"
# (e.g. "Anywhere in the US", "Worldwide (EMEA timezones only)").
REGION_TERMS = re.compile(
    r"\b(us|usa|u\.s\.|united states|america[s]?|canada|uk|united kingdom|"
    r"europe|eu|emea|apac|latam|north america|south america|asia|germany|"
    r"france|spain|india|australia|brazil|mexico|philippines|est|pst|cet)\b",
    re.I,
)
# Phrases in the description that mean "not actually open worldwide".
DESCRIPTION_RESTRICTIONS = re.compile(
    r"(\b(us|usa|u\.s\.|uk|eu|canada)[- ]?(only|based)\b|"
    r"must (be|reside|live) (based )?in the (us|usa|united states|uk|united kingdom)|"
    r"(authori[sz]ed|eligible|legally able) to work in the (us|usa|united states|uk|united kingdom|eu)|"
    r"\bus citizens?\b|\bgreen card\b|\bsecurity clearance\b|\bw-?2\b|"
    r"located in (the )?(us|usa|united states|north america|europe)\b)",
    re.I,
)
WORLDWIDE_IN_TEXT = re.compile(
    r"(work from anywhere|from anywhere in the world|worldwide|globally remote|"
    r"fully remote,? (worldwide|globally|anywhere)|hire (from )?anywhere)",
    re.I,
)


def is_fresh(job, cutoff):
    return job.posted_at is not None and job.posted_at >= cutoff


def is_worldwide(job):
    desc = job.description or ""
    if DESCRIPTION_RESTRICTIONS.search(desc[:6000]):
        return False
    if job.worldwide_hint is not None:
        return job.worldwide_hint
    loc = (job.location or "").strip()
    if loc:
        if WORLDWIDE_LOCATIONS.search(loc):
            return not REGION_TERMS.search(WORLDWIDE_LOCATIONS.sub("", loc))
        if loc.lower() in {"remote", "100% remote", "fully remote"}:
            return bool(WORLDWIDE_IN_TEXT.search(desc))
        return False
    # No location given: only trust it if the posting says so explicitly.
    return bool(WORLDWIDE_IN_TEXT.search(desc))


def _contains(text, term):
    return re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", text) is not None


def keyword_score(job):
    """Score a job against the CV profile. Returns (score, matched_terms)."""
    title = job.title.lower()
    if any(_contains(title, t) for t in profile.EXCLUDE_TITLE_TERMS):
        return 0.0, []
    score, matched = 0.0, []
    for term, w in profile.TITLE_KEYWORDS.items():
        if _contains(title, term):
            score += w
            matched.append(term)
    body = " ".join([title, " ".join(job.tags).lower(), (job.description or "").lower()[:8000]])
    for term, w in profile.BODY_KEYWORDS.items():
        if _contains(body, term):
            score += w
            if term not in matched:
                matched.append(term)
    return score, matched


def dedupe(jobs):
    """Drop repeats of the same posting across boards (same URL or same title+company)."""
    seen, out = set(), []
    for j in jobs:
        keys = {j.url.split("?")[0].rstrip("/").lower(),
                (re.sub(r"\W+", "", j.title.lower()), re.sub(r"\W+", "", j.company.lower()))}
        if seen & keys:
            continue
        seen |= keys
        out.append(j)
    return out


def apply_filters(jobs, max_age_days=21, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    kept = []
    for j in jobs:
        if not j.url or not is_fresh(j, cutoff) or not is_worldwide(j):
            continue
        j.score, j.matched = keyword_score(j)
        if j.score >= profile.MIN_KEYWORD_SCORE:
            kept.append(j)
    kept = dedupe(kept)
    kept.sort(key=lambda j: j.score, reverse=True)
    return kept
