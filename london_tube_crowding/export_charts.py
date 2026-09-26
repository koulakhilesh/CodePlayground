"""Export the interactive Plotly charts used in the tube-crowding write-up.

Mirrors the calculations in eda_notebook.ipynb. Run from the repo root:
    python london_tube_crowding/export_charts.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "tube_crowding"
EXPORT_DIR = Path(__file__).resolve().parent / "exports"
CENTRE_LAT, CENTRE_LON = 51.5074, -0.1278
MIN_DAILY_FLOW = 5000
VIEWPORT_META = '<meta name="viewport" content="width=device-width, initial-scale=1" />'
HTML_CONFIG = {"responsive": True, "displaylogo": False}
MAP_STYLE = "carto-positron"
FONT = dict(family="Inter, system-ui, sans-serif", size=13)


def slice_hour(ts: pd.Series) -> pd.Series:
    ts = ts.astype(str)
    return ts.str[:2].astype(int) + ts.str[2:4].astype(int) / 60


def fmt(h: float) -> str:
    return f"{int(h):02d}:{int(round(h % 1 * 60)):02d}"


def load() -> dict[str, pd.DataFrame]:
    stations = pd.read_csv(DATA / "stations_master.csv")
    crowding = pd.read_csv(DATA / "station_line_crowding.csv")
    loadings = pd.read_csv(DATA / "train_loadings.csv")
    crowding["h"] = slice_hour(crowding["time_slice"])
    loadings["h"] = slice_hour(loadings["time_slice"])
    stations["km"] = np.hypot(
        (stations["lat"] - CENTRE_LAT) * 111,
        (stations["lon"] - CENTRE_LON) * 111 * np.cos(np.radians(CENTRE_LAT)),
    )
    meta = stations.set_index("naptan")[["name", "km", "lat", "lon"]]
    st = crowding.groupby(["station_naptan", "h"])["value"].sum().unstack(fill_value=0)
    return {"meta": meta, "st": st, "loadings": loadings}


def window(st: pd.DataFrame, a: float, b: float) -> pd.DataFrame:
    cols = st.columns
    return st.loc[:, (cols >= a) & (cols < b)]


def peaks_table(meta: pd.DataFrame, st: pd.DataFrame) -> pd.DataFrame:
    amw, pmw = window(st, 5, 11), window(st, 15, 20)
    peaks = pd.DataFrame({
        "am_peak": amw.idxmax(axis=1), "pm_peak": pmw.idxmax(axis=1),
        "am_max": amw.max(axis=1), "pm_max": pmw.max(axis=1),
        "daily_flow": st.sum(axis=1),
    }).join(meta)
    peaks = peaks[peaks["daily_flow"] >= MIN_DAILY_FLOW].copy()
    peaks["pm_am"] = peaks["pm_max"] / peaks["am_max"]
    peaks["am_label"] = peaks["am_peak"].map(fmt)
    return peaks


def style(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(title=dict(text=title, x=0.02), font=FONT, template="plotly_white",
                      autosize=True, margin=dict(l=60, r=20, t=60, b=50))
    return fig


def fig_daily(st: pd.DataFrame) -> go.Figure:
    net = st.sum()
    am, pm = net[(net.index >= 5) & (net.index < 12)], net[net.index >= 12]
    fig = go.Figure(go.Scatter(
        x=net.index, y=net.values, mode="lines", line=dict(color="#1c5fb0", width=2.5),
        customdata=[fmt(h) for h in net.index],
        hovertemplate="%{customdata}<br>%{y:,.0f} per 15 min<extra></extra>"))
    for h, v, label in [(am.idxmax(), am.max(), "AM peak"), (pm.idxmax(), pm.max(), "PM peak")]:
        fig.add_annotation(x=h, y=v, text=f"{label} {fmt(h)}<br>{v:,.0f}", showarrow=True, arrowhead=0, ay=-35)
    fig.update_xaxes(tickvals=list(range(0, 25, 2)), ticktext=[f"{h:02d}:00" for h in range(0, 25, 2)],
                     title="time of day (15-minute slices; no data 02:00-05:00)")
    fig.update_yaxes(title="network flow per 15 min", rangemode="tozero")
    return style(fig, "A typical day on the Tube: total passenger flow, all stations")


def fig_peak_map(peaks: pd.DataFrame) -> go.Figure:
    fig = px.scatter_map(
        peaks.reset_index(), lat="lat", lon="lon", color="am_peak", size="daily_flow",
        size_max=22, color_continuous_scale="Viridis_r", range_color=(7, 9),
        hover_name="name", custom_data=["am_label", "km", "daily_flow"],
        zoom=9.3, center=dict(lat=51.52, lon=-0.13), map_style=MAP_STYLE)
    fig.update_traces(hovertemplate="<b>%{hovertext}</b><br>busiest morning slice %{customdata[0]}"
                                    "<br>%{customdata[1]:.1f} km from Charing Cross"
                                    "<br>daily flow %{customdata[2]:,.0f}<extra></extra>")
    ticks = np.arange(7, 9.01, 0.5)
    fig.update_coloraxes(colorbar=dict(title="morning peak", tickvals=ticks, ticktext=[fmt(t) for t in ticks]))
    fig = style(fig, "When each station's morning peak hits")
    fig.update_layout(margin=dict(l=0, r=0, t=50, b=0))
    return fig


def fig_peak_vs_distance(peaks: pd.DataFrame) -> go.Figure:
    jitter = np.random.default_rng(0).uniform(-0.04, 0.04, len(peaks))
    fig = go.Figure(go.Scatter(
        x=peaks["km"], y=peaks["am_peak"] + jitter, mode="markers",
        marker=dict(size=np.sqrt(peaks["daily_flow"]) / 18 + 4, color="#c0392b", opacity=0.55),
        text=peaks["name"], customdata=peaks["am_label"],
        hovertemplate="<b>%{text}</b><br>%{x:.1f} km<br>peak slice %{customdata}<extra></extra>"))
    ticks = np.arange(6.5, 10.01, 0.5)
    fig.update_yaxes(tickvals=ticks, ticktext=[fmt(t) for t in ticks], title="busiest 15-min slice, 05:00-11:00")
    fig.update_xaxes(title="distance from Charing Cross (km)")
    return style(fig, "The morning rush reaches the centre last")


def fig_home_work(peaks: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=peaks["km"], y=peaks["pm_am"], mode="markers",
        marker=dict(size=np.sqrt(peaks["daily_flow"]) / 18 + 4, color="#16a085", opacity=0.6),
        text=peaks["name"],
        hovertemplate="<b>%{text}</b><br>%{x:.1f} km<br>evening peak / morning peak: %{y:.2f}<extra></extra>"))
    fig.add_hline(y=1, line=dict(color="grey", dash="dash", width=1))
    labelled = ["Goodge Street", "Canary Wharf", "Uxbridge", "Heathrow Terminals 2 & 3", "Queensbury", "Elm Park"]
    for _, r in peaks[peaks["name"].isin(labelled)].iterrows():
        fig.add_annotation(x=r["km"], y=np.log10(r["pm_am"]), text=r["name"], showarrow=False,
                           xshift=8, xanchor="left", font=dict(size=11))
    fig.update_yaxes(type="log", title="evening peak ÷ morning peak (log scale)",
                     tickvals=[0.1, 0.2, 0.5, 1, 2, 5, 10], ticktext=["0.1", "0.2", "0.5", "1", "2", "5", "10"])
    fig.update_xaxes(title="distance from Charing Cross (km)")
    return style(fig, "Suburbs peak in the morning, the centre in the evening")


def fig_station_types(meta: pd.DataFrame, st: pd.DataFrame) -> go.Figure:
    name_to_id = meta.reset_index().drop_duplicates("name").set_index("name")["naptan"]
    examples = {"Elm Park": "home", "Goodge Street": "work",
                "Leicester Square": "night out", "Heathrow Terminals 2 & 3": "airport"}
    fig = go.Figure()
    for n, kind in examples.items():
        s = st.loc[name_to_id[n]]
        fig.add_trace(go.Scatter(x=s.index, y=s / s.max(), mode="lines", name=f"{n} ({kind})",
                                 customdata=[fmt(h) for h in s.index],
                                 hovertemplate="%{customdata}: %{y:.0%} of own peak<extra>" + n + "</extra>"))
    fig.update_xaxes(tickvals=list(range(0, 25, 2)), ticktext=[f"{h:02d}:00" for h in range(0, 25, 2)])
    fig.update_yaxes(title="flow ÷ station's own busiest slice", tickformat=".0%")
    fig.update_layout(legend=dict(orientation="h", y=-0.18))
    return style(fig, "Four station types, each scaled to its own peak")


CENTRAL_ROUTE = ["Epping", "Theydon Bois", "Debden", "Loughton", "Buckhurst Hill", "Woodford",
                 "South Woodford", "Snaresbrook", "Leytonstone", "Leyton", "Stratford", "Mile End",
                 "Bethnal Green", "Liverpool Street", "Bank", "St. Paul's", "Chancery Lane", "Holborn",
                 "Tottenham Court Road", "Oxford Circus", "Bond Street", "Marble Arch"]


def fig_central(meta: pd.DataFrame, loadings: pd.DataFrame) -> go.Figure:
    name_to_id = meta.reset_index().drop_duplicates("name").set_index("name")["naptan"]
    wb = loadings[(loadings["line"] == "central") & (loadings["line_direction"] == "WB")
                  & (loadings["h"] >= 6) & (loadings["h"] < 10.5)]
    grid = (wb.pivot_table(index="station_naptan", columns="h", values="value")
              .reindex([name_to_id[n] for n in CENTRAL_ROUTE]))
    fig = go.Figure(go.Heatmap(
        z=grid.values, x=[fmt(h) for h in grid.columns], y=CENTRAL_ROUTE,
        colorscale="YlOrRd", zmin=0, zmax=6, colorbar=dict(title="loading<br>band"),
        hovertemplate="leaving %{y} at %{x}<br>band %{z}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", tickmode="array", tickvals=CENTRAL_ROUTE)
    fig.update_xaxes(title="departure slice")
    fig = style(fig, "Central line westbound: how full the train is as it leaves each station")
    fig.update_layout(margin=dict(l=150, r=20, t=60, b=50))
    return fig


def fig_hourly_map(meta: pd.DataFrame, st: pd.DataFrame) -> go.Figure:
    hourly = st.T.groupby(np.floor(st.columns).astype(int)).mean().T
    long = (hourly.stack().rename("flow").reset_index()
            .rename(columns={"level_1": "hour", "h": "hour"})
            .merge(meta, left_on="station_naptan", right_index=True))
    # run the day from the first trains (05:00) through to 01:00
    long = long.assign(order=(long["hour"] - 5) % 24).sort_values(["order", "station_naptan"])
    long["hour_label"] = long["hour"].map(lambda h: f"{h:02d}:00")
    vmax = long["flow"].quantile(0.98)
    long["size"] = long["flow"].clip(upper=vmax) + 1
    fig = px.scatter_map(
        long, lat="lat", lon="lon", size="size", color="flow", animation_frame="hour_label",
        labels={"hour_label": "hour"},
        size_max=26, color_continuous_scale="Plasma", range_color=(0, vmax),
        hover_name="name", custom_data=["flow"], zoom=9.3,
        center=dict(lat=51.52, lon=-0.13), map_style=MAP_STYLE)
    fig.update_traces(hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]:,.0f} per 15 min<extra></extra>")
    for frame in fig.frames:
        frame.data[0].hovertemplate = "<b>%{hovertext}</b><br>%{customdata[0]:,.0f} per 15 min<extra></extra>"
    fig.update_coloraxes(colorbar=dict(title="flow per<br>15 min"))
    fig.layout.sliders[0].currentvalue.prefix = "hour: "
    fig = style(fig, "Station flow, hour by hour (press play)")
    fig.update_layout(margin=dict(l=0, r=0, t=50, b=0))
    return fig


def write(fig: go.Figure, slug: str) -> Path:
    out = EXPORT_DIR / f"{slug}.html"
    fig.write_html(out, include_plotlyjs="cdn", full_html=True, config=HTML_CONFIG, auto_play=False)
    html = out.read_text()
    if 'name="viewport"' not in html:
        out.write_text(html.replace('<meta charset="utf-8" />', '<meta charset="utf-8" />' + VIEWPORT_META, 1))
    return out


def write_thumbnail(peaks: pd.DataFrame) -> Path:
    out = EXPORT_DIR / "tube.png"
    fig, ax = plt.subplots(figsize=(6.4, 6.4), dpi=100)
    ax.scatter(peaks["lon"], peaks["lat"], c=peaks["am_peak"], cmap="viridis_r", vmin=7, vmax=9,
               s=np.sqrt(peaks["daily_flow"]) / 3, alpha=0.9, edgecolor="none")
    ax.set_aspect(1 / np.cos(np.radians(CENTRE_LAT)))
    ax.set_xlim(-0.45, 0.2); ax.set_ylim(51.40, 51.70)
    ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def main() -> None:
    EXPORT_DIR.mkdir(exist_ok=True)
    d = load()
    meta, st, loadings = d["meta"], d["st"], d["loadings"]
    peaks = peaks_table(meta, st)
    charts = {
        "daily-flow": fig_daily(st),
        "hourly-map": fig_hourly_map(meta, st),
        "morning-peak-map": fig_peak_map(peaks),
        "peak-vs-distance": fig_peak_vs_distance(peaks),
        "home-work": fig_home_work(peaks),
        "station-types": fig_station_types(meta, st),
        "central-line": fig_central(meta, loadings),
    }
    for slug, fig in charts.items():
        print("wrote", write(fig, slug))
    print("wrote", write_thumbnail(peaks))


if __name__ == "__main__":
    main()
