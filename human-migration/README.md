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
  - Each stop has an evidence range (years ago), a short note and at least one citation. All 14 DOIs
    were checked against Crossref on 28 Sep 2026.
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

```bash
cd /Users/Akhilesh.Koul/Documents/GitHub/CodePlayground
python human-migration/migration_export.py --out ../koulakhilesh.github.io/assets/lab
```

This writes two files:

- `fuller-world.json` (about 62 KB): land rings, a 15° graticule, the 24 face triangles and
  continent labels. Coordinates are integers on a 10000-unit-wide frame.
- `migration.json` (about 5 KB): the origin and the stops.
  - Each stop keeps its text fields.
  - `path` holds the route as projected pieces.
  - `xy` holds the site position.

The layout turns the net 60° clockwise, so Africa sits top-left and the Americas run to the right,
as on Wikipedia's Dymaxion map. The site rotates it upright on phones.

## Checks

```bash
python -m pytest human-migration -q
```

- **Projection:**
  - Shared face edges agree to 1e-9.
  - Nothing is mirrored.
  - A small north step and east step stay within 0.78–1.26 of each other in length, and within 14° of
    a right angle.
- **Land:**
  - Projected land covers 28.69% of the net against 28.77% of the sphere.
  - Known places (Cairo, Lagos, Reykjavik, Wellington, Hawaii and others) stay on land.
- **Routes:**
  - The New Zealand voyage breaks only where it crosses a cut in Fuller's net (the Pacific).
  - Every other route is a single piece.

## Known choices

- **Clipping:** clipped continent rings can cross themselves, so shapes are repaired with
  `make_valid`, not `buffer(0)`. `buffer(0)` silently dropped lobes (Cairo, Riyadh, Lagos). Land is
  also cut into 10° tiles before clipping.
- **Ranges:** these are the span of the cited evidence, not a single date. Where the evidence is
  debated (South Asia, Australia, the Americas), the stop is marked `contested` and drawn dashed.
