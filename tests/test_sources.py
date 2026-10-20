"""Parse sample payloads shaped like each board's public feed."""

from unittest.mock import patch

from jobagent import sources


class FakeResp:
    def __init__(self, json_data=None, content=b""):
        self._json, self.content = json_data, content

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


def fake(json_data=None, content=b""):
    return patch.object(sources, "_get", return_value=FakeResp(json_data, content))


def test_remotive():
    with fake({"jobs": [{"title": "Community Manager", "company_name": "A", "url": "https://r/1",
                         "candidate_required_location": "Worldwide", "publication_date": "2026-10-18T10:00:00",
                         "description": "<p>Discord</p>", "tags": ["web3"], "category": "Marketing"}]}):
        (j,) = sources.fetch_remotive()
    assert j.location == "Worldwide" and j.description == "Discord" and j.posted_at.day == 18


def test_remoteok_skips_legal_notice():
    with fake([{"legal": "..."}, {"position": "Video Editor", "company": "B", "url": "https://ro/1",
                                  "location": "Worldwide", "epoch": 1792314000, "tags": ["video"]}]):
        jobs = sources.fetch_remoteok()
    assert len(jobs) == 1 and jobs[0].title == "Video Editor"


def test_weworkremotely_rss():
    rss = b"""<rss><channel><item><title>Acme: Social Media Manager</title>
    <region>Anywhere in the World</region><link>https://wwr/1</link>
    <pubDate>Sat, 18 Oct 2026 09:00:00 +0000</pubDate><description>&lt;b&gt;hi&lt;/b&gt;</description>
    <category>Sales and Marketing</category></item></channel></rss>"""
    with fake(content=rss):
        (j,) = sources.fetch_weworkremotely()
    assert (j.company, j.title, j.location) == ("Acme", "Social Media Manager", "Anywhere in the World")


def test_himalayas_restrictions_and_paging_stop():
    page = {"jobs": [{"title": "Content Producer", "companyName": "C", "applicationLink": "https://h/1",
                      "locationRestrictions": [], "pubDate": 1792314000},
                     {"title": "Designer", "companyName": "D", "applicationLink": "https://h/2",
                      "locationRestrictions": ["United States"], "pubDate": 1000000000}]}
    from datetime import datetime, timezone
    with fake(page) as m:
        jobs = sources.fetch_himalayas(cutoff=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert m.call_count == 1  # oldest result is past the cutoff, so stop paging
    assert jobs[0].worldwide_hint is True and jobs[1].worldwide_hint is False


def test_fetch_all_survives_broken_board():
    def boom(**_):
        raise RuntimeError("down")
    with patch.dict(sources.SOURCES, {"a": boom, "b": lambda: []}, clear=True):
        assert sources.fetch_all() == []
