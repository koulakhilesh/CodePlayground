# Blue Plaques API — Probe Notes (2026-07-11)

## Compliance gate — PASS
- robots.txt disallows only: `/archived-for-delete/`, `/commerce/checkout/`,
  `/commerce/basket/`, `/administration/`. The blue-plaques paths are allowed.

## Network reality (this machine)
- Corporate Netskope proxy intercepts TLS (self-signed root in chain).
- Decision: scraper runs with **TLS verification DISABLED** (read-only public
  data, no secrets). Scoped to this project only.
- uv Python needs its dylib → network commands must run **unsandboxed**.

## List API — CONFIRMED
- `GET https://www.english-heritage.org.uk/api/BluePlaqueSearch/GetMatchingBluePlaques`
- Params: `pageBP={page}` `sizeBP={size}` `borBP=0` `keyBP=` `catBP=0`
- Response JSON: `{"total": 1036, "plaques": [ {record}, ... ]}`
- `total` = **1036** (matches expectation).
- Each list record keys:
  - `id`          e.g. "87558"
  - `title`       e.g. "ABERCROMBIE, Sir Patrick (1879-1957)"  ← name + born/died
  - `summary`     one-sentence description
  - `path`        detail page path, e.g. "/visit/blue-plaques/sir-patrick-abercrombie/"
  - `imagePath`, `imageAlt`
  - `address`     full address, LAST segment is the borough
                  e.g. "...London Borough of Kensington And Chelsea"
  - `professions` comma-separated, e.g. "Town and country planner"

## Detail page — HTML (not JSON), CONFIRMED
- `GET https://www.english-heritage.org.uk{path}` returns HTML (~92 KB).
- Detail panels (stable element IDs under `ctl00_cpMain_BluePlaqueDetails_`):
  - `pnlProfession` → `<p class="column large-profession ...">TEXT</p>`
  - `pnlCategory`   → `<p class="column large-category ...">TEXT</p>`
  - `pnlInscription`→ `<p class="column small-detail ...">TEXT</p>`
  - `pnlMaterial`   → `<p class="column small-detail ...">TEXT</p>`
- Coordinates: inside `function InitialiseMap()` →
  `GetMapAndData("blueplaquepage", <id>, <id>, 0, "<title>", <LAT>, <LNG>, ...)`
  e.g. lat `51.496588`, lng `-0.168453`.
- Biography: first `<p>` in `div.row-wrapper.simple-content.section.pad3000`.

## Field mapping (source → clean)
- id          <- list.id
- name        <- parsed from list.title ("Surname, First (b-d)" → "First Surname")
- born, died  <- parsed from list.title "(1879-1957)"
- professions <- list.professions (also detail pnlProfession)
- category    <- detail pnlCategory
- borough     <- last comma-segment of list.address
- address     <- list.address
- lat, lng    <- detail GetMapAndData(...) floats
- inscription <- detail pnlInscription
- material    <- detail pnlMaterial
- summary     <- list.summary
- biography   <- detail first bio paragraph
- detail_url  <- list.path

## LIMITATION
- **No plaque erection/unveiling date** exposed on the page. Angle "I) age of the
  plaque roll-out" is NOT feasible from this source. All other angles are covered.

## Plan deltas vs original spec
- Detail responses are HTML → add `beautifulsoup4` dependency; split parsing into
  `parse_list_record(record)` + `parse_detail_html(html)` combined by `parse_plaque`.
- Drop `erected` field (not available). Add `category`, `material`, `biography`.
