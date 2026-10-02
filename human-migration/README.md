# Human migration on Fuller's map

Data and map export for **When did we get here?**, a game on
[koulakhilesh.github.io/lab/migration/](https://koulakhilesh.github.io/lab/migration/). You follow
*Homo sapiens* out of Africa on Buckminster Fuller's world map and guess when people first reached
eight places. Each guess is scored against the published evidence.

## Files

- `fuller.py`: the Fuller projection.
  - Icosahedron orientation, split faces and unfolding tree follow d3-geo-polygon's `airocean.js`
    (ISC licence).
  - The per-face transform is Robert W. Gray's exact equations (Cartographica 32(3), 1995), as in
    d3-geo-polygon's public-domain `grayfuller.js`.
  - Geometry is clipped to each face on the sphere before it is projected.
- `stops.py`: the hand-curated game data.
  - The origin, eight stops, continent labels and route waypoints.
  - Each stop has an evidence range (years ago), a short note and at least one citation. All 19 DOIs
    were checked against Crossref (28 Sep and 2 Oct 2026), and the wording against the papers'
    abstracts on Europe PMC. New Zealand is also dated in CE (`ce`), so the site can keep "years ago"
    current.
- `migration_export.py`: CLI that writes the two JSON files the site loads.
- `tests/`: tests for the projection, clipping, routes and data.

## Data (`data/natural_earth/`, gitignored)

The map uses Natural Earth 1:50m land (public domain). The `naciscdn.org` download returned 403
from this network, so fetch it from the Natural Earth GitHub mirror:

```bash
mkdir -p data/natural_earth
curl -sSfL -o data/natural_earth/ne_50m_land.geojson \
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson
```

## Export

From the CodePlayground root, with the site repo checked out next to it:

```bash
python human-migration/migration_export.py --out ../koulakhilesh.github.io/assets/lab
```

This writes two files:

- `fuller-world.json` (about 52 KB): land outlines, lakes, a 15° graticule, the 24 face triangles
  and continent labels. Coordinates are integers on a 10000-unit-wide frame. Islands and lakes
  smaller than about 4 px² at 1200 px wide are dropped.
- `migration.json` (about 6 KB): the origin and the stops.
  - Each stop keeps its text fields.
  - `path` holds the route as projected pieces. A piece ends exactly on the edge where it meets
    one of the net's cuts.
  - `xy` holds the site position.

The layout turns the net 60° clockwise, so Africa sits top-left and the Americas run to the right,
as on Wikipedia's Dymaxion map. The site rotates it upright on phones.

## Checks

```bash
python -m pytest human-migration -q
```

- **Projection:**
  - Matches d3-geo-polygon's `geoAirocean` for 12 cities. A single scale-and-turn (d3's own 45.4631
    and 60°) lines every point up to within 1e-6 px; the reference values are in the test.
  - Shared face edges agree to 1e-9.
  - Nothing is mirrored.
  - A small north step and east step stay within 0.78–1.26 of each other in length, and within 14° of
    a right angle.
- **Land** (these tests need the Natural Earth file and are skipped without it):
  - All 12 corners of Fuller's icosahedron fall at sea.
  - Projected land covers 28.69% of the net against 28.77% of the sphere; the test allows 0.2
    points.
  - Known places (Cairo, Lagos, Reykjavik, Wellington, Hawaii and others) stay on land.
- **Routes:**
  - The New Zealand voyage breaks only on the net's edge, where it crosses a cut in the Pacific.
  - Every other route is a single piece.

## Known choices

- **Clipping:** clipped continent rings can cross themselves, so shapes are repaired with
  `make_valid`, not `buffer(0)`. `buffer(0)` silently dropped lobes (Cairo, Riyadh, Lagos). Land is
  also cut into 10° tiles before clipping.
- **Ranges:** these are the span of the cited evidence, not a single date. Where the evidence is
  debated (South Asia, Australia, the Americas), the stop is marked `contested` and drawn dashed.
