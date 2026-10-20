from datetime import datetime, timedelta, timezone

from jobagent.filters import apply_filters, is_worldwide, keyword_score
from jobagent.models import Job
from jobagent.sources import parse_date

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def job(title="Community Manager", location="Worldwide", days_old=3, desc="", **kw):
    return Job(title=title, company=kw.pop("company", "Acme"), url=kw.pop("url", f"https://x.test/{title}"),
               source="test", location=location, posted_at=NOW - timedelta(days=days_old),
               description=desc, **kw)


def test_worldwide_locations():
    assert is_worldwide(job(location="Worldwide"))
    assert is_worldwide(job(location="Anywhere in the World"))
    assert not is_worldwide(job(location="USA Only"))
    assert not is_worldwide(job(location="Anywhere in the US"))
    assert not is_worldwide(job(location="Worldwide (EMEA)"))
    assert not is_worldwide(job(location="Remote"))
    assert is_worldwide(job(location="Remote", desc="We hire from anywhere in the world."))
    assert not is_worldwide(job(location="", desc="Great team."))


def test_description_restriction_overrides_location():
    assert not is_worldwide(job(location="Worldwide", desc="Candidates must be authorized to work in the US."))
    assert not is_worldwide(job(worldwide_hint=True, desc="This role is US-only."))


def test_source_hint():
    assert is_worldwide(job(location="", worldwide_hint=True))
    assert not is_worldwide(job(location="Worldwide", worldwide_hint=False))


def test_keyword_score_and_exclusions():
    score, matched = keyword_score(job(title="Social Media Manager", desc="Discord, Telegram, Premiere Pro"))
    assert score >= 10 and "social media" in matched and "discord" in matched
    assert keyword_score(job(title="Senior Backend Engineer (Community platform)"))[0] == 0
    # "ama" must not match inside "Amazon"
    assert "ama" not in keyword_score(job(title="Video Editor", desc="Amazon store"))[1]


def test_apply_filters_age_location_dedupe():
    jobs = [
        job(title="Community Manager", days_old=2),
        job(title="Community Manager", days_old=2, url="https://other.test/cm"),  # same role, other board
        job(title="Content Producer", days_old=25),                             # too old
        job(title="Social Media Lead", location="UK"),                          # not worldwide
        job(title="Accountant"),                                                # wrong track
        Job("Video Editor", "B", "https://x.test/v", "t", "Worldwide", None),  # no date
    ]
    out = apply_filters(jobs, max_age_days=21, now=NOW)
    assert [j.title for j in out] == ["Community Manager"]


def test_parse_date_formats():
    assert parse_date("2026-10-18T09:00:00").tzinfo is not None
    assert parse_date("2026-10-18 09:00:00").day == 18
    assert parse_date("Sat, 18 Oct 2026 09:00:00 +0000").day == 18
    assert parse_date(1792314000).year == 2026
    assert parse_date(1792314000000).year == 2026
    assert parse_date("garbage") is None
