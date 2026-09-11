# London Tube Crowd Movement EDA

Station-level dataset and exploratory analysis of how crowds move across the London
Underground, built from the TfL Unified API.

## Data files (`data/tube_crowding/`, gitignored)

- `stations_master.csv` — canonical mapping master: **272 station NaPTANs** (270 unique
  names) with `naptan, name, tube_lines, n_lines, lat, lon, modes, hub_naptan_code,
  crowding_available`.
- `station_line_edges.csv` — one row per station-line pair (tube lines only), for
  network/line maps.
- `station_line_crowding.csv` — typical passenger flow per station, line and 15-minute
  time slice (~31.7k rows, 267 stations, 11 lines).
- `wiki_stations.json` — station names scraped from Wikipedia (source-of-truth list).

## NaPTAN notes

- Canonical station IDs use the `940GZZ...` prefix. Platform stop points use `9400ZZ...`
  (e.g. `9400ZZLUCWR1` = Canada Water platform 1) and are **not** valid crowding IDs.
- Three names map to two physical stations each (this is the "272 vs 269" difference):
  Edgware Road, Hammersmith, Paddington.
- Two stations have no own crowding feed (served by a sibling in the same complex):
  Monument (-> Bank) and Hammersmith `940GZZLUHSD` (-> `940GZZLUHSC`).

## API routes

- Station catalogue: `GET /StopPoint/Mode/tube`
- Station detail (lines, lat/lon): `GET /StopPoint/{id}`
- Flow-count crowding (used here): `GET /StopPoint/{id}/Crowding/{line}?direction=all`
- Station-level relative crowding (% of baseline): `GET /crowding/{naptan}`

## Refresh the data (live, opt-in)

Live fetches are rate-limited, so they are opt-in. A `TFL_API_KEY` must be present in
`london_tube_crowding/.env`.

```bash
cd /Users/Akhilesh.Koul/Documents/GitHub/CodePlayground
python london_tube_crowding/london_tube_crowding.py --live
```

## Analysis

Open `eda_notebook.ipynb` for the exploratory analysis (daily flow curve, busiest lines
and stations, line x hour heatmap, and a peak-hour spatial map).
