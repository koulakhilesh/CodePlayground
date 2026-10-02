# London parkrun

Where London's 5k parkruns are and who can get to one. Two posts on
koulakhilesh.github.io: *Who can get to a parkrun?* and *Which parkrun came first, and can you run the alphabet?*.

    python london-parkrun/fetch_data.py          # ~250 MB into data/parkrun/raw (gitignored)
    python -m pytest london-parkrun/tests -q
    python -m jupyter nbconvert --to notebook --execute --inplace london-parkrun/parkrun_access.ipynb
    python -m jupyter nbconvert --to notebook --execute --inplace london-parkrun/parkrun_shape.ipynb
    python london-parkrun/export_charts.py       # writes london-parkrun/exports/

Sources: parkrun events feed, London Datastore (boundaries, PTAL 2015), ONS Census 2021
(TS007A, TS045 via Nomis), DfT NaPTAN, OS Open Greenspace. No results data is used:
parkrun's terms forbid scraping results pages.
