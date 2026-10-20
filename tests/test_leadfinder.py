from unittest.mock import MagicMock, patch

from leadfinder import __main__ as cli
from leadfinder import osm, output, places


def place(pid, website=None, reviews=5, phone="021 555 0000", status="OPERATIONAL"):
    p = {"id": pid, "displayName": {"text": f"Biz {pid}"}, "formattedAddress": "1 Main Rd, Cape Town",
         "primaryTypeDisplayName": {"text": "Plumber"}, "userRatingCount": reviews,
         "businessStatus": status, "googleMapsUri": f"https://maps.google.com/?cid={pid}"}
    if website:
        p["websiteUri"] = website
    if phone:
        p["nationalPhoneNumber"] = phone
    return p


def test_presence_classifies_social_pages():
    b = places.parse_place(place("a"), "q")
    assert b.presence == "none"
    b.website = "https://m.facebook.com/joesplumbing"
    assert b.presence == "social-only"
    b.website = "https://www.joesplumbing.co.za/"
    assert b.presence == "website"


def test_search_follows_pages_and_respects_budget():
    pages = [{"places": [place("a"), place("b", status="CLOSED_PERMANENTLY")], "nextPageToken": "t"},
             {"places": [place("c")], "nextPageToken": "t2"}]
    budget = places.Budget(2)
    with patch.object(places, "_post", side_effect=pages) as post, patch.object(places.time, "sleep"):
        ids = [b.place_id for b in places.search("key", "plumber in Woodstock", budget)]
    assert ids == ["a", "c"]
    assert post.call_count == 2 and budget.used == 2
    assert post.call_args_list[1].args[1]["pageToken"] == "t"


def test_find_businesses_dedupes_across_queries():
    with patch.object(places, "_post", return_value={"places": [place("a"), place("b")]}):
        found = places.find_businesses("key", ["plumber"], ["Woodstock", "Salt River"], places.Budget(10))
    assert sorted(b.place_id for b in found) == ["a", "b"]


def test_cli_keeps_only_businesses_without_a_website(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "key")
    data = {"places": [place("none"), place("fb", website="https://facebook.com/x"),
                       place("site", website="https://site.co.za"), place("nophone", phone=None)]}
    out = tmp_path / "leads.csv"
    with patch.object(places, "_post", return_value=data):
        cli.main(["--source", "google", "--categories", "plumber", "--areas", "Woodstock", "--no-sheet",
                  "--csv", str(out), "--require-phone"])
    rows = out.read_text().splitlines()
    assert len(rows) == 2 and "Biz none" in rows[1]

    with patch.object(places, "_post", return_value=data):
        cli.main(["--source", "google", "--categories", "plumber", "--areas", "Woodstock", "--no-sheet",
                  "--csv", str(out), "--include-social"])
    body = out.read_text()
    assert "Biz fb" in body and "social-only" in body and "Biz site" not in body


def test_write_sheet_skips_place_ids_already_present():
    ws = MagicMock()
    ws.get_all_values.return_value = [output.HEADER, [""] * output.ID_COL + ["a", "Called"]]
    gc = MagicMock()
    gc.open_by_key.return_value.worksheet.return_value = ws
    leads = [places.parse_place(place("a"), "q"), places.parse_place(place("b"), "q")]
    with patch("gspread.authorize", return_value=gc), patch.object(output, "_credentials"):
        added = output.write_sheet(leads, "sheet-id")
    assert added == 1
    (rows,), _ = ws.append_rows.call_args
    assert rows[0][output.ID_COL] == "b"


def osm_el(oid, **tags):
    return {"type": "node", "id": oid, "tags": {"name": f"Shop {oid}", **tags}}


def test_osm_parse_and_presence():
    b = osm.parse_element(osm_el(1, shop="hairdresser", phone="021 1", **{"addr:street": "Main Rd",
                                                                         "addr:suburb": "Observatory"}))
    assert b.place_id == "osm:node/1" and b.category == "Hairdresser" and b.presence == "none"
    assert b.address == "Main Rd, Observatory, Cape Town" and b.maps_url.endswith("/node/1")
    assert osm.parse_element(osm_el(2, shop="bakery", **{"contact:facebook": "shop2"})).presence == "social-only"
    assert osm.parse_element(osm_el(3, craft="plumber", website="https://p.co.za")).presence == "website"


def test_osm_filters_by_category_and_area():
    data = {"elements": [osm_el(1, shop="hairdresser", **{"addr:suburb": "Woodstock"}),
                         osm_el(2, amenity="car_repair", **{"addr:suburb": "Bellville"}),
                         {"type": "node", "id": 3, "tags": {"shop": "bakery"}}]}
    with patch.object(osm, "_fetch", return_value=data):
        assert [b.place_id for b in osm.find_businesses()] == ["osm:node/1", "osm:node/2"]
        assert [b.name for b in osm.find_businesses(["car repair"])] == ["Shop 2"]
        assert [b.name for b in osm.find_businesses(None, ["woodstock"])] == ["Shop 1"]


def test_osm_falls_back_to_second_server():
    good = MagicMock()
    good.json.return_value = {"elements": []}
    with patch.object(osm.requests, "post", side_effect=[osm.requests.ConnectionError("down"), good]) as post:
        assert osm._fetch() == {"elements": []}
    assert post.call_args.args[0] == osm.ENDPOINTS[1]


def test_cli_defaults_to_osm_without_a_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    out = tmp_path / "leads.csv"
    data = {"elements": [osm_el(1, shop="florist"), osm_el(2, shop="florist", website="https://f.co.za")]}
    with patch.object(osm, "_fetch", return_value=data):
        cli.main(["--no-sheet", "--csv", str(out)])
    rows = out.read_text().splitlines()
    assert len(rows) == 2 and "Shop 1" in rows[1] and "openstreetmap.org" in rows[1]
