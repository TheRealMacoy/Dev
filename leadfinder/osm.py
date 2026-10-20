"""Search OpenStreetMap through the public Overpass API: free, no key, no sign-up.

One query pulls every named shop, trade, office, eatery and clinic in the Cape Town
metro. OSM has fewer listings than Google Maps and fewer phone numbers, but it costs
nothing and has no usage limits beyond fair use.
"""

import logging

import requests

from .places import Business

log = logging.getLogger(__name__)

ENDPOINTS = ["https://overpass-api.de/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter"]
HEADERS = {"User-Agent": "cape-town-leadfinder/1.0 (small-business lead research)"}
TIMEOUT = 300

# Same area as places.CAPE_TOWN_BOUNDS, as (south, west, north, east).
BBOX = "-34.36,18.30,-33.47,18.95"
AMENITIES = ("restaurant|cafe|fast_food|bar|pub|ice_cream|dentist|doctors|clinic|veterinary|"
             "car_repair|car_wash|driving_school|childcare|kindergarten|language_school")
# Chain branches (tagged with a brand) are left out: their website is the chain's.
QUERY = f"""[out:json][timeout:240];
(
  nwr["shop"]["name"][!"brand"]({BBOX});
  nwr["craft"]["name"][!"brand"]({BBOX});
  nwr["office"]["name"][!"brand"]({BBOX});
  nwr["healthcare"]["name"][!"brand"]({BBOX});
  nwr["amenity"~"^({AMENITIES})$"]["name"][!"brand"]({BBOX});
  nwr["tourism"~"^(guest_house|hostel|apartment)$"]["name"][!"brand"]({BBOX});
);
out center tags;"""

WEBSITE_TAGS = ("website", "contact:website", "url")
SOCIAL_TAGS = ("contact:facebook", "facebook", "contact:instagram", "instagram",
               "contact:whatsapp", "contact:tiktok")
CATEGORY_TAGS = ("craft", "shop", "amenity", "healthcare", "office", "tourism")


def category(tags):
    for key in CATEGORY_TAGS:
        if tags.get(key) and tags[key] != "yes":
            return tags[key].replace("_", " ").capitalize()
    return ""


def address(tags):
    street = " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")]))
    parts = [street, tags.get("addr:suburb"), tags.get("addr:city") or "Cape Town"]
    return ", ".join(p for p in parts if p)


def social_link(value):
    value = value.strip()
    if value.startswith("http"):
        return value
    return f"https://www.facebook.com/{value.lstrip('@')}"


def parse_element(el):
    tags = el.get("tags", {})
    website = next((tags[t] for t in WEBSITE_TAGS if tags.get(t)), "")
    if not website:
        website = next((social_link(tags[t]) for t in SOCIAL_TAGS if tags.get(t)), "")
    kind, oid = el["type"], el["id"]
    return Business(
        place_id=f"osm:{kind}/{oid}",
        name=tags.get("name", ""),
        category=category(tags),
        address=address(tags),
        phone=tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile", ""),
        website=website,
        rating=None,
        reviews=0,
        maps_url=f"https://www.openstreetmap.org/{kind}/{oid}",
        query="openstreetmap",
    )


def _fetch():
    last = None
    for url in ENDPOINTS:
        try:
            resp = requests.post(url, data={"data": QUERY}, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("Overpass server %s failed: %s", url, e)
            last = e
    raise RuntimeError(f"All Overpass servers failed: {last}")


def matches(b, el_tags, categories, areas):
    if categories:
        haystack = " ".join([b.category, b.name] + [el_tags.get(k, "") for k in CATEGORY_TAGS]).lower()
        if not any(c.lower() in haystack for c in categories):
            return False
    if areas:
        if not any(a.lower() in b.address.lower() for a in areas):
            return False
    return True


def find_businesses(categories=None, areas=None):
    """Named, unbranded businesses in Cape Town, optionally filtered by text match.

    categories match the OSM tag value or name ("hairdresser", "car repair", "plumber").
    areas match the address, which only works where OSM has addr:suburb/addr:city.
    """
    data = _fetch()
    found = []
    for el in data.get("elements", []):
        b = parse_element(el)
        tags = {k: v.replace("_", " ") for k, v in el.get("tags", {}).items()}
        if b.name and matches(b, tags, categories, areas):
            found.append(b)
    return found
