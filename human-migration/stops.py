"""Hand-curated stops for "When did we get here?".

Each range (years ago) is the full-score window: the span of the cited evidence, not one number.
Every stop has at least one citation, checked against Crossref. Route waypoints are (lon, lat)
and start at the previous stop's site, so the routes join up into one branching walk.
"""
from __future__ import annotations

ORIGIN = {
    "name": "Africa",
    "ll": (38.5, 8.0),
    "text": ("Homo sapiens evolved in Africa. The oldest known fossils, from Jebel Irhoud in Morocco, "
             "are about 315,000 years old. The routes below start in East Africa."),
    "cite": [{"t": "Richter et al. 2017, Nature 546:293", "doi": "10.1038/nature22335"}],
}

STOPS = [
    {
        "id": "levant", "name": "The Levant", "lo": 177000, "hi": 194000, "contested": False,
        "q": "When did Homo sapiens first reach the Levant, just outside Africa?",
        "site": "Misliya Cave, Israel: an upper jaw dated to 177,000–194,000 years ago.",
        "note": ("An early foray. These first groups outside Africa seem not to have lasted: most people "
                 "outside Africa today descend from a later dispersal, about 70,000–50,000 years ago."),
        "cite": [{"t": "Hershkovitz et al. 2018, Science 359:456", "doi": "10.1126/science.aap8369"}],
        "route": [(38.5, 8.0), (33.5, 20.0), (32.5, 29.5), (35.0, 32.7)],
    },
    {
        "id": "south-asia", "name": "South Asia", "lo": 50000, "hi": 77000, "contested": True,
        "q": "When did people reach South Asia?",
        "site": "Jwalapuram, India: stone tools above and below the ash of the Toba eruption, about 74,000 years ago.",
        "note": ("No human bones were found with the tools, so who made them is argued over. Genetic studies "
                 "put the main coastal dispersal through South Asia at about 60,000–50,000 years ago."),
        "cite": [{"t": "Petraglia et al. 2007, Science 317:114", "doi": "10.1126/science.1141564"}],
        "route": [(38.5, 8.0), (43.3, 12.6), (50.0, 15.5), (57.5, 22.0), (65.0, 25.0), (72.5, 20.0),
                  (78.1, 15.3)],
    },
    {
        "id": "australia", "name": "Australia", "lo": 50000, "hi": 65000, "contested": True,
        "q": "When did people first reach Australia?",
        "site": "Madjedbebe, northern Australia: artefacts dated to about 65,000 years ago.",
        "note": ("The 65,000-year date is debated; critics argue for about 50,000. Either way the journey "
                 "needed boats: even with sea levels low, open water separated Asia from Australia."),
        "cite": [{"t": "Clarkson et al. 2017, Nature 547:306", "doi": "10.1038/nature22968"},
                 {"t": "O'Connell et al. 2018, PNAS 115:8482", "doi": "10.1073/pnas.1808385115"}],
        "route": [(78.1, 15.3), (86.0, 20.5), (94.0, 16.5), (99.5, 7.0), (106.0, -6.5), (116.0, -8.7),
                  (124.5, -9.8), (132.9, -12.5)],
    },
    {
        "id": "europe", "name": "Europe", "lo": 43000, "hi": 47000, "contested": False,
        "q": "When did Homo sapiens reach Europe?",
        "site": "Ranis, Germany: remains of Homo sapiens from about 45,000 years ago.",
        "note": ("A 210,000-year-old skull fragment from Apidima Cave, Greece, has been claimed as Homo "
                 "sapiens, but that reading is disputed. The first Europeans left little trace in people "
                 "living there today."),
        "cite": [{"t": "Smith et al. 2024, Nature Ecology & Evolution 8:564", "doi": "10.1038/s41559-023-02303-6"},
                 {"t": "Harvati et al. 2019, Nature 571:500", "doi": "10.1038/s41586-019-1376-z"}],
        "route": [(35.0, 32.7), (36.5, 37.0), (29.0, 41.0), (25.4, 42.9), (19.0, 46.5), (11.6, 50.7)],
    },
    {
        "id": "east-asia", "name": "East Asia", "lo": 38000, "hi": 42000, "contested": False,
        "q": "When did people reach northern China?",
        "site": "Tianyuan Cave, near Beijing: a man who lived about 40,000 years ago.",
        "note": ("His DNA links him to people in East Asia and the Americas today. Teeth and jaws from "
                 "southern China, such as Zhirendong at about 100,000 years, are argued to be older, but "
                 "their dates and identity are debated."),
        "cite": [{"t": "Yang et al. 2017, Current Biology 27:3202", "doi": "10.1016/j.cub.2017.09.030"},
                 {"t": "Liu et al. 2010, PNAS 107:19201", "doi": "10.1073/pnas.1014386107"}],
        "route": [(78.1, 15.3), (86.0, 20.5), (94.0, 16.5), (100.0, 14.0), (106.0, 21.0), (113.0, 27.0),
                  (115.9, 39.6)],
    },
    {
        "id": "siberia", "name": "Arctic Siberia", "lo": 30000, "hi": 33000, "contested": False,
        "q": "When did people live above the Arctic Circle in Siberia?",
        "site": "Yana RHS, 71°N: a camp from about 32,000 years ago (27,000 radiocarbon years).",
        "note": ("People were living in the high Arctic well before the coldest part of the last Ice Age, "
                 "much earlier than was once thought."),
        "cite": [{"t": "Pitulko et al. 2004, Science 303:52", "doi": "10.1126/science.1085219"}],
        "route": [(115.9, 39.6), (106.0, 48.0), (104.3, 52.3), (118.0, 60.0), (129.0, 66.0), (135.4, 70.7)],
    },
    {
        "id": "americas", "name": "The Americas", "lo": 15000, "hi": 23000, "contested": True,
        "q": "When did people first reach the Americas?",
        "site": "White Sands, New Mexico: human footprints dated to 21,000–23,000 years ago.",
        "note": ("The footprint dates are still debated; the conventional estimate is 15,000–20,000 years "
                 "ago. The older view put the first arrivals at about 13,000–16,000 years ago."),
        "cite": [{"t": "Bennett et al. 2021, Science 373:1528", "doi": "10.1126/science.abg7586"},
                 {"t": "Pigati et al. 2023, Science 382:73", "doi": "10.1126/science.adh5007"}],
        "route": [(135.4, 70.7), (160.0, 68.0), (-170.0, 65.5), (-152.0, 60.0), (-136.0, 57.5),
                  (-124.5, 45.0), (-118.5, 36.0), (-106.3, 32.8)],
    },
    {
        "id": "new-zealand", "name": "Aotearoa New Zealand", "lo": 725, "hi": 775, "contested": False,
        "q": "When did people first reach New Zealand?",
        "site": "Aotearoa New Zealand: settled by Polynesian voyagers about 1250–1300 CE.",
        "note": ("The last large land mass people reached. Their ancestors sailed from Taiwan through Island "
                 "Southeast Asia and Melanesia, reached Samoa and Tonga about 2,800 years ago, and East "
                 "Polynesia later."),
        "cite": [{"t": "Wilmshurst et al. 2011, PNAS 108:1815", "doi": "10.1073/pnas.1015876108"},
                 {"t": "Wilmshurst et al. 2008, PNAS 105:7676", "doi": "10.1073/pnas.0801507105"}],
        "route": [(115.9, 39.6), (119.5, 30.0), (121.0, 23.5), (121.5, 15.0), (135.0, -1.0), (148.0, -4.5),
                  (160.0, -9.0), (167.0, -15.5), (178.0, -17.8), (-172.0, -13.8), (-149.5, -17.6),
                  (-165.0, -32.0), (174.1, -41.5)],
    },
]

LABELS = [
    ("Africa", (20.0, 5.0)), ("Europe", (22.0, 52.0)), ("Asia", (95.0, 45.0)),
    ("Australia", (134.0, -25.0)), ("North America", (-100.0, 45.0)),
    ("South America", (-60.0, -15.0)), ("Antarctica", (60.0, -78.0)),
]
