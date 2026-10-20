---
name: cape-town-leads
description: Find businesses in Cape Town, South Africa that are listed on Google Maps but have no website (or only a Facebook/Instagram page), e.g. as web-design sales leads. Use when the user asks for companies, shops or tradespeople "without a website", "no website", "website leads" or "prospects" in Cape Town or a Cape Town suburb.
---

# Cape Town no-website leads

This skill runs `python -m leadfinder` from the repo root. The tool uses the official
Google Places API (New), so it gets the same listings as Google Maps. Do not scrape
google.com search or Maps pages: that breaks Google's terms and gets blocked after a
few requests.

## 1. Check setup
- `GOOGLE_PLACES_API_KEY` must be set. If it is missing, stop and tell the user how to
  get one (README section "Cape Town lead finder"). Never ask them to paste it into the chat.
- Run `pip install -r requirements.txt` if `requests` isn't installed.
- Google Sheets output is optional. It needs `GOOGLE_SHEET_ID` plus service-account
  credentials. Without them, pass `--no-sheet`.

## 2. Turn the request into flags
| User says | Flag |
|---|---|
| a trade or type ("plumbers", "hair salons") | `--categories "plumber,hair salon"` (singular nouns) |
| suburbs ("Northern Suburbs", "Bellville") | `--areas "Bellville,Durbanville,Parow"` (expand regions into suburbs) |
| "Facebook-only is fine too" / "no proper website" | `--include-social` |
| "established" / "real businesses" | `--min-reviews 5` |
| "I want to call them" | `--require-phone` |
| nothing specific | use the defaults in `leadfinder/config.py` |

Each query (one category in one area) costs up to 3 billable requests. Estimate the number
of requests as categories × areas × 3. If that is over 200, tell the user the estimate
first, then set `--max-requests` to cover it. Text Search with the website field is billed
at the Enterprise rate, about US$35 per 1,000 requests after Google's monthly free allowance.

## 3. Run
```bash
python -m leadfinder --categories "..." --areas "..." --csv leads.csv [--no-sheet] [-v]
```

## 4. Report
- Say how many unique businesses were found and how many have no website.
- Show the top 10–15 leads as a table: Business, Category, Phone, Area, Reviews.
- Give the CSV path (and say that the sheet's `Leads` tab was updated, if it was).
- Point out that Google data can be out of date. Some businesses have a website that
  isn't linked to their Maps listing, so check a lead before contacting it.
