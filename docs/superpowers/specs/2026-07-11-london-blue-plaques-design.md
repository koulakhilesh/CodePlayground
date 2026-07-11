# London Blue Plaques — Design Spec

**Date:** 2026-07-11
**Author:** Akhilesh Koul
**Status:** Approved (design)

## Overview

A two-part project, modeled on the London Reservoir Levels project:

1. **CodePlayground** — a web scraper that collects all English Heritage blue
   plaques in London (~1,036 total) into a clean dataset, plus an analysis
   notebook that explores and visualizes the data (Plotly, including a map).
2. **koulakhilesh.github.io** — a curiosity-driven blog post that tells the
   story the data reveals.

**Weighting:** equal — a solid, reusable scraper *and* a rich analysis/story.

## Data source

- English Heritage Blue Plaques:
  https://www.english-heritage.org.uk/visit/blue-plaques/
- The listing page is driven by a paginated backend endpoint (query params
  `pageBP`, `sizeBP`, `borBP`, `keyBP`, `catBP`) — i.e. JSON/AJAX, not static
  HTML. This is confirmed as the first implementation step.
- **Before scraping:** check `robots.txt` and terms of use; confirm automated
  collection for personal analysis is acceptable. Stay polite regardless.
- **Citation is mandatory** in the blog post: English Heritage Blue Plaques,
  scrape date, link, and a note on terms of use.

## Scope: analytical angles

Scrape everything feasible first, then decide which angles to pursue once we can
see field coverage. Candidate dimensions:

Core:
- **A) Who gets remembered** — professions/fields and how the mix shifts over time.
- **B) Gender & representation** — men vs women; whether recent plaques correct it.
- **C) Geography** — clustering by borough/area; density map; hotspots.
- **D) Time** — era lived vs. when the plaque went up.
- **E) Lifespans** — birth–death spans, longevity, era patterns.

Extended (feasibility depends on scraped fields, confirmed in notebook):
- **F) Recognition lag** — years between death and plaque.
- **G) Nationality / "London as a magnet"** — non-British honorees.
- **H) Multiple-occupancy addresses** — buildings/people with several plaques.
- **I) Age of the plaque** — roll-out over the scheme's 150+ year history.
- **J) Residency length** — "lived here YYYY–YYYY" spans from inscription text.
- **K) Category cross-tabs** — profession × geography.
- **L) Text patterns** — common words in inscriptions (small text-mining pass).

## Decisions locked

- **Dataset committed?** No — gitignored for now. User will later decide whether
  to make the `data/` folder public. Scraper still writes into `data/`.
- **Scraping approach:** Approach A — direct JSON API via `requests`. Two-pass:
  list pass + per-plaque detail pass ("click into" each plaque). Fall back to a
  detail-page HTML parse or Playwright only if the API is locked down.
- **Branching:** CodePlayground work on a new branch `london-blue-plaques` off
  `main`. Website post committed directly to `main`.

## Architecture & repo layout

```
CodePlayground/
├── data/
│   ├── blue_plaques_2026-07.csv        # gitignored (dated snapshot)
│   └── .cache/plaques/                 # gitignored raw responses (resumable)
├── london-blue-plaques/
│   ├── scrape_plaques.py               # two-pass, throttled, resumable scraper
│   ├── blue_plaques_analysis.ipynb     # analysis + Plotly viz
│   └── exports/                        # standalone HTML charts for the blog
```

- `scrape_plaques.py` is a standalone re-runnable script, separate from the
  notebook, so scraping and analysis stay decoupled.
- `.cache/` stores each plaque's raw response so re-runs resume rather than
  re-hitting the server.
- Dependencies via `uv add`: `requests` (+ `beautifulsoup4` if detail pages need
  HTML parsing; `playwright` only if forced to fall back).

## Scraper design (`scrape_plaques.py`)

Small, single-purpose, independently testable functions:

- `fetch_list_page(page, size)` → one page of plaque summaries; looped until all
  ~1,036 collected.
- `fetch_plaque_detail(id_or_url)` → Pass 2; cache-first, network only on miss,
  writes raw response to cache.
- `parse_plaque(raw)` → clean flat dict with normalized fields (name, profession,
  born, died, borough, address, lat, lng, category, inscription, erected,
  detail_url). Isolated for unit testing against saved samples, no network.
- `scrape_all()` → orchestrates both passes, assembles a DataFrame, writes
  `data/blue_plaques_<YYYY-MM>.csv`.

Politeness & robustness (built in):
- Descriptive `User-Agent` identifying the scraper.
- Small delay between requests (~0.5–1s); sequential requests at this scale.
- Retry-with-backoff on transient failures (timeouts, 429/5xx).
- Resumable via cache.
- `--limit N` flag to smoke-test on a handful before the full crawl.

First step: a "probe" that fetches page 1, dumps the raw JSON, and confirms the
real endpoint URL, field names, and whether detail pages are needed. The design
adapts to what the probe reveals.

## Analysis notebook & data flow

`blue_plaques_analysis.ipynb` reads the committed/generated CSV (never scrapes):

1. **Load & clean** — normalize fields, parse born/died to numeric years, derive
   helpers (age at death, recognition lag, gender where inferable, nationality
   flag where present).
2. **Data quality pass** — field coverage report; this is the decision point for
   which extended angles (F/I/J/L) are feasible.
3. **Exploratory sections** — one per surviving angle.
4. **Centerpiece map** — Plotly map of all plaques across London, colored by
   category, exported to `exports/`.
5. **Takeaways** — the handful of genuine, surprising findings for the post.

Each notable chart exported as standalone interactive HTML into `exports/`.

## Blog post (koulakhilesh.github.io)

- New post in `_posts/` (URL `/writing/:title/`), committed directly to `main`.
- Embeds interactive Plotly HTML exports (map + key charts).
- Voice: curiosity-driven, data-science-flavored, genuinely human — not
  AI-sounding — consistent with the user's writing preference.
- Structure follows the data: hook → 2–3 findings with visuals → reflection.
- Cite English Heritage Blue Plaques with scrape date, link, terms-of-use note.

## Error handling & testing

- **Scraper:** retry/backoff, resumable cache, `--limit` smoke test, validation
  (assert ~1,036 rows, warn on unexpected drops).
- **Parsing:** `parse_plaque` unit-tested against a saved sample record (no
  network).
- **Notebook:** runs top-to-bottom clean on the generated CSV.

## Sequencing

1. Check robots.txt / terms of use.
2. Probe the list API (confirm endpoint + fields).
3. Build the scraper (list pass, then detail pass), smoke-test with `--limit`.
4. Full scrape → dated CSV.
5. Notebook: clean, field-coverage decision, exploratory analysis, map, exports.
6. Blog post on the website with embedded visuals and citation.
