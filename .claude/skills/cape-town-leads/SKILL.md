---
name: cape-town-leads
description: Find businesses in Cape Town, South Africa that are listed on OpenStreetMap or Google Maps but have no website (or only a Facebook/Instagram page), e.g. as web-design sales leads. Use when the user asks for companies, shops or tradespeople "without a website", "no website", "website leads" or "prospects" in Cape Town or a Cape Town suburb.
---

# Cape Town no-website leads

This skill runs `python -m leadfinder` from the repo root. There are two data sources:

- `--source osm` (default): OpenStreetMap through the public Overpass API. It's free and
  needs no key or sign-up. It has fewer listings and phone numbers than Google, and no reviews.
- `--source google`: the official Google Places API, with the same listings as Google
  Maps. It needs `GOOGLE_PLACES_API_KEY` and billing turned on.

Use OSM unless the user asks for Google, or `GOOGLE_PLACES_API_KEY` is set and they want
the fullest coverage. Do not scrape google.com search or Maps pages: that breaks Google's
terms and gets blocked after a few requests.

## 1. Check setup
- For `--source google`, `GOOGLE_PLACES_API_KEY` must be set. If it is missing, offer
  the free OSM source instead. Never ask the user to paste a key into the chat.
- Run `pip install -r requirements.txt` if `requests` isn't installed.
- Google Sheets output is optional. It needs `GOOGLE_SHEET_ID` plus service-account
  credentials. Without them, pass `--no-sheet`.

## 2. Turn the request into flags
| User says | Flag |
|---|---|
| a trade or type ("plumbers", "hair salons") | `--categories "plumber,hair salon"` (singular nouns) |
| suburbs ("Northern Suburbs", "Bellville") | `--areas "Bellville,Durbanville,Parow"` (expand regions into suburbs) |
| "Facebook-only is fine too" / "no proper website" | `--include-social` |
| "established" / "real businesses" | `--min-reviews 5` (Google only) |
| "I want to call them" | `--require-phone` |
| nothing specific | OSM: no filters (whole metro); Google: defaults in `leadfinder/config.py` |

With OSM, `--categories` matches the OSM tag (`hairdresser`, `car repair`, `plumber`,
`electrician`, `restaurant`, `beauty`) or the business name. `--areas` only matches
businesses that have a suburb in their OSM address, so it can miss some. If an area
filter returns little, rerun without it and filter the CSV by address instead.

Google only: each query (one category in one area) costs up to 3 billable requests. Estimate the number
of requests as categories × areas × 3. If that is over 200, tell the user the estimate
first, then set `--max-requests` to cover it. Text Search with the website field is billed
at the Enterprise rate, about US$35 per 1,000 requests after Google's monthly free allowance.

## 3. Run
```bash
python -m leadfinder [--source google] --categories "..." --areas "..." --csv leads.csv [--no-sheet] [-v]
```

## 4. Report
- Say how many unique businesses were found and how many have no website.
- Show the top 10–15 leads as a table: Business, Category, Phone, Area (and Reviews for Google).
- Give the CSV path (and say that the sheet's `Leads` tab was updated, if it was).
- Point out that map data can be out of date. Some businesses have a website that
  isn't linked to their map listing, so check a lead before contacting it.
