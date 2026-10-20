# Remote Job Agent

Scans remote job boards every day for roles that are **fully remote and open worldwide**,
matches them against Fayyaadh Adams' CV, and appends the matches (with apply links) to a
Google Sheet. Postings older than **21 days** are skipped.

## How it works

1. **Scrape.** It pulls the public feeds of Remotive, RemoteOK, We Work Remotely,
   Jobicy, Himalayas and Working Nomads (`jobagent/sources.py`). If one board is
   down, the run carries on without it.
2. **Filter.** It keeps a posting only if it:
   - was posted in the last 21 days,
   - is open worldwide: the location says Worldwide/Anywhere/Global, with no
     region or country attached, and the description has nothing like "US only",
     "must be authorized to work in the UK", W-2 or a security clearance,
   - scores high enough against the CV keywords in `jobagent/profile.py`
     (community, social media, content/video, design, DevRel/ecosystem, Web3,
     Discord/Telegram, Adobe CC, HubSpot and so on). Engineering, sales and other
     unrelated titles are dropped.

   The same role listed on more than one board is merged into one row.
3. **Rank with Claude (optional).** If `ANTHROPIC_API_KEY` is set, Claude reads each
   shortlisted posting against the CV summary. It gives a fit score from 0 to 100,
   checks again that someone living in South Africa can be hired, and writes a
   one-line reason it fits. Postings scoring under 55, or restricted by region, are
   dropped.
4. **Write.** New rows go into the `Jobs` tab of your Google Sheet. A link that is
   already in the sheet is never added twice, so your edits to the **Status**
   column are kept. A `jobs.csv` copy is written each run too.

Sheet columns: Date Found · Posted · Title · Company · Location · Source ·
Match Score · Matched Skills · Why It Fits · Apply Link · Status

## Setup (one-time, about 10 minutes)

### 1. Google Sheet and service account
1. Create a blank Google Sheet. Copy its ID from the URL:
   `https://docs.google.com/spreadsheets/d/<THIS_PART>/edit`.
2. In [Google Cloud Console](https://console.cloud.google.com/), create a project
   (or use an existing one) and enable the **Google Sheets API**.
3. Go to **IAM & Admin → Service Accounts → Create service account**. Open the new
   account, then **Keys → Add key → JSON** to download the key file.
4. Share your Google Sheet with the service account's email address
   (`...@...iam.gserviceaccount.com`) as an **Editor**.

### 2. GitHub secrets (for the daily run)
In this repo, go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|---|---|
| `GOOGLE_SHEET_ID` | the sheet ID from step 1 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | the full contents of the downloaded JSON key |
| `ANTHROPIC_API_KEY` | optional: turns on Claude ranking |

The workflow in `.github/workflows/job-agent.yml` runs every day at 07:17 SAST.
To run it straight away, open **Actions → Remote job agent → Run workflow**.

### Running locally
```bash
pip install -r requirements.txt
export GOOGLE_SHEET_ID=...            # sheet ID
export GOOGLE_APPLICATION_CREDENTIALS=service_account.json
export ANTHROPIC_API_KEY=...          # optional
python -m jobagent                    # or: --no-sheet, --no-llm, --max-age 14, -v
```

## Tuning
- **Roles and skills:** edit `TITLE_KEYWORDS`, `BODY_KEYWORDS` and
  `EXCLUDE_TITLE_TERMS` in `jobagent/profile.py`. Raise `MIN_KEYWORD_SCORE` to get
  fewer, closer matches.
- **Claude's view of you:** `CANDIDATE_SUMMARY` in the same file. Update it when
  your CV changes.
- **Strictness:** use `--min-fit` (default 55) for Claude's cut-off and
  `--max-age` (default 21) for the age limit in days.

## Tests
```bash
pip install pytest && python -m pytest -q
```

---

# Cape Town lead finder

Finds businesses in Cape Town that are listed on Google Maps but have **no website**.
These are good leads for web design or digital marketing work. It uses the official
**Google Places API**, which has the same listings as Google Maps. Scraping Google's
pages directly breaks its terms and gets blocked quickly, so the tool doesn't do that.

## How it works
1. **Search.** For every category × suburb pair (for example "plumber in Woodstock, Cape Town")
   it runs a Places Text Search limited to the Cape Town metro. Each search returns at
   most 60 places, so splitting by suburb gives better coverage. The defaults are in
   `leadfinder/config.py`.
2. **Filter.** It keeps operational businesses with no website on their listing.
   With `--include-social`, it also keeps businesses whose only "website" is a
   Facebook, Instagram, WhatsApp, Linktree (or similar) page.
3. **Write.** It writes `leads.csv` and appends new rows to the `Leads` tab of your
   Google Sheet. Rows are deduped by Google place ID, so your **Status** edits are kept.

Columns: Date Found · Business · Category · Phone · Address · Web Presence ·
Social Link · Rating · Reviews · Google Maps · Place ID · Status

## Setup
1. In [Google Cloud Console](https://console.cloud.google.com/), enable **Places API (New)**
   and turn on billing. Google gives a monthly free allowance; past that, Text Search
   with the website field costs about US$35 per 1,000 requests.
2. **APIs & Services → Credentials → Create credentials → API key.** Restrict the key
   to the Places API.
3. Add it as the `GOOGLE_PLACES_API_KEY` GitHub secret, or export it locally. The Sheet
   secrets above are reused for the `Leads` tab.

```bash
export GOOGLE_PLACES_API_KEY=...
python -m leadfinder --no-sheet                                    # all defaults
python -m leadfinder --categories "plumber,barber" --areas "Bellville,Parow" \
    --include-social --min-reviews 3 --require-phone
```
`--max-requests` (default 200) caps billable calls. A full default run is
33 categories × 32 suburbs, so raise the cap or narrow the search.

In GitHub: **Actions → Cape Town lead finder → Run workflow**. You can set categories
and suburbs there. The CSV is attached to the run.

In Claude Code: the `cape-town-leads` skill (`.claude/skills/cape-town-leads/`) lets you ask
something like *"find hair salons in the southern suburbs with no website"*. Claude picks
the flags, runs the tool and summarises the leads.
