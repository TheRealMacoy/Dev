"""Search Google Maps listings through the Places API (New) Text Search.

Each query returns at most 60 places (3 pages of 20), so coverage comes from
running many small queries: every category in every suburb.
"""

import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
TIMEOUT = 30
FIELDS = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.nationalPhoneNumber", "places.internationalPhoneNumber",
    "places.websiteUri", "places.primaryTypeDisplayName", "places.rating",
    "places.userRatingCount", "places.businessStatus", "places.googleMapsUri",
    "nextPageToken",
])

# City of Cape Town metro, roughly Atlantis to Cape Point and out to Gordon's Bay.
CAPE_TOWN_BOUNDS = {"rectangle": {"low": {"latitude": -34.36, "longitude": 18.30},
                                  "high": {"latitude": -33.47, "longitude": 18.95}}}

# A "website" on these hosts is just a social profile, not a site of their own.
SOCIAL_HOSTS = ("facebook.com", "fb.com", "instagram.com", "wa.me", "whatsapp.com",
                "linktr.ee", "tiktok.com", "twitter.com", "x.com", "linkedin.com",
                "business.site", "youtube.com")


@dataclass
class Business:
    place_id: str
    name: str
    category: str
    address: str
    phone: str
    website: str
    rating: float | None
    reviews: int
    maps_url: str
    query: str

    @property
    def presence(self):
        """'none', 'social-only' or 'website'."""
        if not self.website:
            return "none"
        host = urlparse(self.website).netloc.lower().removeprefix("www.")
        if any(host == h or host.endswith("." + h) for h in SOCIAL_HOSTS):
            return "social-only"
        return "website"


def parse_place(p, query):
    return Business(
        place_id=p["id"],
        name=(p.get("displayName") or {}).get("text", ""),
        category=(p.get("primaryTypeDisplayName") or {}).get("text", ""),
        address=p.get("formattedAddress", ""),
        phone=p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber", ""),
        website=p.get("websiteUri", ""),
        rating=p.get("rating"),
        reviews=p.get("userRatingCount", 0),
        maps_url=p.get("googleMapsUri", ""),
        query=query,
    )


class Budget:
    """Caps billable API calls so a run can't run up an unexpected bill."""

    def __init__(self, limit):
        self.limit, self.used = limit, 0

    def take(self):
        if self.used >= self.limit:
            return False
        self.used += 1
        return True


def _post(api_key, body):
    resp = requests.post(SEARCH_URL, json=body, timeout=TIMEOUT, headers={
        "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELDS})
    if resp.status_code >= 400:
        raise RuntimeError(f"Places API {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def search(api_key, query, budget, max_pages=3):
    """Yield every operational place for one text query, following page tokens."""
    body = {"textQuery": query, "pageSize": 20, "locationRestriction": CAPE_TOWN_BOUNDS,
            "regionCode": "ZA", "languageCode": "en"}
    for _ in range(max_pages):
        if not budget.take():
            return
        data = _post(api_key, body)
        for p in data.get("places", []):
            if p.get("businessStatus", "OPERATIONAL") == "OPERATIONAL":
                yield parse_place(p, query)
        token = data.get("nextPageToken")
        if not token:
            return
        body = {**body, "pageToken": token}
        time.sleep(0.5)


def find_businesses(api_key, categories, areas, budget):
    """Run category x area queries. Returns unique businesses keyed by place ID."""
    found = {}
    for category in categories:
        for area in areas:
            if budget.used >= budget.limit:
                log.warning("Hit the request budget (%d); stopping early", budget.limit)
                return list(found.values())
            query = f"{category} in {area}, Cape Town"
            try:
                n = 0
                for b in search(api_key, query, budget):
                    n += b.place_id not in found
                    found.setdefault(b.place_id, b)
                log.debug("%-50s +%d new", query, n)
            except (requests.RequestException, RuntimeError) as e:
                log.warning("%s failed: %s", query, e)
                if "403" in str(e) or "401" in str(e) or "API key" in str(e):
                    raise
    return list(found.values())
