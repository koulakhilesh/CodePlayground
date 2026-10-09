# Wren's London

A sourced historical register and visitor research project. Data collection is
separate from verification; a scraped statement is not a verified fact.

Run offline tests from the CodePlayground root:

```sh
uv run pytest london-wren-churches
```

Generated source snapshots and datasets belong under `data/london_wren_churches/`.
Publication exports belong under this project's ignored `exports/` directory.
Reviewed identity decisions live in `review/identities.json`; the original seed
rows remain available separately, including excluded and unresolved candidates.

The historical atlas, discovery graph and walking companion are later stages.
No current opening or accessibility recommendation is implied by the register.

## Exploratory Charts

After collection and review:

```sh
.venv/bin/python london-wren-churches/analyse_wren.py
.venv/bin/python london-wren-churches/walk_wren.py
.venv/bin/python london-wren-churches/discover_wren.py
.venv/bin/python london-wren-churches/export_wren_charts.py   # website charts -> exports/site/
.venv/bin/python london-wren-churches/chooser_wren.py         # "Which Wren church?" poster + chooser
```

`review/chooser.json` holds the yes/no questions and which sites sit on each answer.
Every site carries checks (published hours, access scope, list section, listing flag,
step-free statement, cost, relocation, walk) that `chooser_wren.py` tests against the
reviewed tables before writing `exports/site/chooser.json` and `wren-chooser.svg`; a
failed check stops the export.

Exports: [cohort map](exports/cohort_map.html), [verified event timeline](exports/reviewed_timeline.html),
[rebuilding intervals by evidence tier](exports/construction_tiers.html),
[how the churches were lost](exports/losses.html) (with City census population),
[discovery connections](exports/discovery_graph.html) and the
[weekday pilot](exports/pilot_walk.html). `church_register.csv` carries cohort,
construction range and tier, and published access status per church.

These are local
research previews, not website publications. The map labels extracted site
coordinates; the timeline is deliberately limited to verified events (fifteen at the
latest checkpoint). The map's OpenStreetMap tiles require network access, with attribution
displayed. The generated CSV/JSON files retain cohort and evidence limitations.

The source-supported cohort now has one unresolved attribution, not 44 unreviewed
candidates. This does not imply that the dates of all classified churches are verified.

Open [the weekday pilot](exports/pilot_walk.html) for the sourced stop sequence.
It includes Walbrook, Aldermary's church-run cafe and Abchurch as a restricted
optional interior. Abchurch announces an approximately nine-month closure from
around 12 October 2026; no exact reopening is assumed. Walking legs come from the
OpenStreetMap foot profile between site coordinates (Walbrook to Aldermary: 293 m,
about 4 minutes). There is no live-open guarantee or surveyed step-free route.

Visitor decisions are in `review/visits.json`; the review CLI includes them in
`tables_reviewed.json`, which the walk exporter consumes. `review/walks.json` contains editorial stop order and visit estimates;
`review/routing-source.json` selects the FOSSGIS OSRM foot profile, so the walk export
adds cached walking legs between site coordinates with OpenStreetMap attribution. After
changing these records, rerun review before exporting. Published source hours are checked facts
about the page, not guaranteed real-time availability.

## Collection And Review

From the CodePlayground root:

```sh
.venv/bin/python london-wren-churches/collect_wren.py seed
.venv/bin/python london-wren-churches/collect_wren.py articles
.venv/bin/python london-wren-churches/collect_wren.py references
.venv/bin/python london-wren-churches/collect_wren.py references --retry-failed
.venv/bin/python london-wren-churches/context_wren.py      # lost parishes, population, Monument
.venv/bin/python london-wren-churches/visitors_wren.py     # third-party visitor listings
.venv/bin/python london-wren-churches/review_wren.py
.venv/bin/python london-wren-churches/collect_wren.py inspect --names Walbrook
```

Downloads are cached with content hashes and source metadata. `--retry-failed`
retries only failed reference sources and retains earlier attempt metadata;
successful cached pages are reused. `--refresh` refetches all requested sources,
including previously failed sources. Article collection rebuilds raw
tables from seed and articles; rerun references afterwards to restore reference
claims. Review files are retained separately and applied only by the review CLI.
Use `--output` for collector data paths and `--data` for the review data path.

The current reference discovery collects official Historic England entries linked
by the articles. Other church, museum or archive URLs require explicit targets
in `review/source_targets.json`; arbitrary outbound links are not bulk downloaded.

Local outputs include `seed_rows.json`, `tables_raw.json`, `tables_reviewed.json`,
`discovered_sources.json`, `reference_collection.json`, `coverage.json` and
`reconciliation.json`. These are ignored generated data, not tracked publication
exports. Failed heritage requests remain recorded in source metadata. The initial
checkpoint does not claim that all historical dates or visitor information have
been verified. Review JSON includes claim IDs tied to cached snapshots; if source
layouts change, recheck those locators before reapplying decisions.

## Data sources

Every cached document keeps its URL, retrieval date and content hash in the `sources`
table; each claim points back to its source. The sources used, by collector:

| Source | Used for | Collector | Terms |
|---|---|---|---|
| Wikipedia, [List of Christopher Wren churches in London](https://en.wikipedia.org/wiki/List_of_Christopher_Wren_churches_in_London) and the church articles it links | register, coordinates, dates, costs, loss causes | `collect_wren.py` | CC BY-SA 4.0 |
| Historic England, [National Heritage List for England](https://historicengland.org.uk/listing/the-list/) entries cited by the articles, plus 1079145, 1080836, 1079973, 1000353, 1359203, 1359180 | listing dates and descriptions, relocated fabric, grid references | `collect_wren.py`, `review/source_targets.json` | OGL v3.0 |
| [British Listed Buildings](https://britishlistedbuildings.co.uk/101079145-church-of-st-mary-aldermary-cordwainer-ward) mirror of entry 1079145 | Aldermary listing text (the Historic England page blocked the downloader) | `review/source_targets.json` | OGL v3.0 text |
| Wikipedia, [List of churches destroyed in the Great Fire of London and not rebuilt](https://en.wikipedia.org/wiki/List_of_churches_destroyed_in_the_Great_Fire_of_London_and_not_rebuilt) | lost parishes and their unions | `context_wren.py` | CC BY-SA 4.0 |
| Wikipedia, [City of London](https://en.wikipedia.org/wiki/City_of_London) census table (cites the City of London Corporation and ONS) | resident population 1801 to 1971 | `context_wren.py` | CC BY-SA 4.0 |
| Wikipedia, [Monument to the Great Fire of London](https://en.wikipedia.org/wiki/Monument_to_the_Great_Fire_of_London) | related site and its design caveat | `context_wren.py` | CC BY-SA 4.0 |
| *Parentalia* (1750), [Internet Archive scan](https://archive.org/details/gri_33125011157357) | catalogue of churches and years | `context_wren.py` | public domain |
| [Friends of the City Churches](https://www.fotcc.org.uk/) church pages | published visiting status | `visitors_wren.py` | copyright; brief quotes with link |
| Official sites: St Paul's, St Clement Danes, St James's Piccadilly, Royal Hospital Chelsea, St Bride's, St Margaret Pattens, St Mary Aldermary, St Stephen Walbrook, St Mary Abchurch, Host Cafe | visiting pages, access statements, church histories | `visitors_wren.py`, `review/official_visitor_pages.json`, `review/access_statements.json` | copyright; brief quotes with link |
| [America's National Churchill Museum](https://www.nationalchurchillmuseum.org/history-church-of-st-mary.html) | St Mary Aldermanbury move to Fulton | `review/source_targets.json` | copyright; brief quotes with link |
| [FOSSGIS routing server](https://routing.openstreetmap.de/about.html), foot profile | walking legs | `routing_wren.py` | OpenStreetMap data, ODbL |
| CARTO Positron basemap | chart map tiles | `export_wren_charts.py` | © CARTO, © OpenStreetMap contributors |

Background context in the posts (not parsed into data): Wikipedia's articles on
Christopher Wren, the Great Fire of London, the Rebuilding of London Act 1670 and the
Union of Benefices Act 1860, which cite T. F. Reddaway, *The Rebuilding of London after
the Great Fire* (1940), and G. Huelin, *Vanished Churches of the City of London* (1996).
Each exported chart prints a short source line (`SOURCES` in `export_wren_charts.py`).