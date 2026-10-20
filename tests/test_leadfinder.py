from unittest.mock import MagicMock, patch

from leadfinder import __main__ as cli
from leadfinder import output, places


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
        cli.main(["--categories", "plumber", "--areas", "Woodstock", "--no-sheet",
                  "--csv", str(out), "--require-phone"])
    rows = out.read_text().splitlines()
    assert len(rows) == 2 and "Biz none" in rows[1]

    with patch.object(places, "_post", return_value=data):
        cli.main(["--categories", "plumber", "--areas", "Woodstock", "--no-sheet",
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
