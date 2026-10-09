# Third Pass: The Missing Pieces (2026-10-08)

This pass worked through the second pass's "Still missing" list. Figures in the second
pass below are kept for the record; where they differ, this section supersedes them.
No website files were touched and nothing was committed.

### Construction dates

I read the cached article and listing passages for all 41 unverified replacement
churches and recorded one decision per church in `review/date_reviews.json`:

- **15 verified intervals**, where a passage states a start and an end for a named
  scope. Together with the earlier 4, that makes 19 of 45. Most rest on encyclopedia
  articles; each row records its source publisher. Four are body-only and keep the
  longer whole-church range as an alternative: Mary-le-Bow 1670-73 (tower to 1680),
  Vedast 1670-73 (tower and spire later), All Hallows Bread Street 1681-84 (steeple later)
  and Magnus 1671-76 ("substantially complete").
- **6 conflicts**, where an article contradicts the list or listing. These moved to
  disputed: Greyfriars, St Alban, Mildred Poultry, Nicholas Cole Abbey, Lawrence Jewry and
  Olave Old Jewry.
- **8 single-year milestones**: an opening, a reopening, a completion or a bare
  "rebuilt in" year. They are verified as dated events but are not intervals.
- **7 left unresolved**, where the sources differ and nothing in them explains why.

The tiers for the 45 are now 19 verified, 15 disputed, 3 agreeing and 8 reported. The
median verified span is 5 years.

**An eighteenth-century catalogue breaks the pattern of disputes.** *Parentalia* (1750),
compiled by Wren's son, gives a "rebuilt" or "finished" year for most churches. I read
those years by eye from the public-domain scan, and every quote is checked against the
cached OCR text. Nine disputed churches disagree about the end year and have a
catalogue year. In 7 of them (Lothbury, Greyfriars, Martin Ludgate, Lawrence Jewry, James
Garlickhythe, Abchurch, Pattens) the catalogue matches the earlier end year. In the other
2 (Nicholas Cole Abbey, Walbrook) it matches neither. It never matches the later
Historic England end year. That fits the
idea that the listings' later dates include towers or fittings. It is not proof: the
articles and *Parentalia* may share a tradition. The catalogue year is shown next to each
construction row and decides nothing.

### The count of 51, and St Michael Cornhill

*Parentalia* headlines "Fifty-one parochial Churches ... erected according to the Designs,
and under the Care and Conduct, of Sir Christopher Wren", then lists 54 entries
"together with other Churches built, and repair'd". Mapped to the register:

- 45 replacements, 3 repairs, St Michael Cornhill, St Andrew Holborn (not burned in
  1666), St Clement Danes and St James's (both in Westminster), plus St Mary Woolnoth and
  St Sepulchre, which are not register candidates.
- The 49 fire-area register entries plus Woolnoth and Sepulchre make **exactly 51**.

So the traditional 51 counts repaired churches as well as new ones. The seed list's 51
rows reach the same number differently: they include St Paul's and St Andrew Holborn in
place of Woolnoth and Sepulchre. This is computed in `reconciliation.json` from the
reviewed mapping in `review/parentalia.json`.

Cornhill stays unresolved, but the dispute is now explicit. For Wren: the Historic
England listing ("1670 to 77, by Wren") and *Parentalia* entry XLIV. Against: the
*Buildings of England* assessment, cited in the article, that the parish dealt with the
builders directly. The two "for" sources come from the tradition the modern assessment
challenges. Only the building accounts would settle it.

### Loss reasons

All eight unexplained losses now have a reason from a reviewed article passage
(`review/loss_reasons.json`): two Union of Benefices (Mary Somerset 1871, Olave Old
Jewry 1887), one found unsafe (All Hallows Lombard Street, 1937), two Blitz losses the
list had recorded as demolition years (Stephen Coleman Street, Mildred Bread Street), and
two sets of bombed ruins cleared later (Swithin 1961-62, St Anne's Soho 1953). After
removing a duplicate event for Mary Somerset, there are **34 loss events at 30 churches**:
13 wartime destruction, 12 Union of Benefices, 4 street works or site clearance, 3
structural safety and 2 ruins cleared after bombing. None is left unexplained.

*Correction (2026-10-09 review):* the two Blitz losses recorded as list demolition years
also had an undated seed "destruction" for the same bombing. `analyse_wren.py` now drops
an undated loss when the same church has a dated loss with the same cause, giving
**32 loss events at 30 churches**, 11 of them wartime destruction.

### Costs, fabric, accessibility and fees

- **Costs:** 30 Wren-era costs are verified against their passages (`review/costs.json`).
  For the 28 replacement churches with a cost, the median is £5,329 (nominal). The range
  runs from St Vedast's £1,854 (main body only; the later spire cost £2,958) to
  Mary-le-Bow's £15,421. Scope is recorded for each figure (church, church and tower,
  church and steeple, or unsplit).
- **Fabric condition:** for 11 churches the official listing wording gives a fabric flag.
  Six interiors were "reconstructed in near facsimile" after the war (Andrew Wardrobe,
  Bride, Lawrence Jewry, Mary-le-Bow, Nicholas Cole Abbey, Vedast). St Anne and St Agnes
  was "extensively reconstructed", Paternoster Royal was "damaged and restored", and
  three are listed as having lost their bodies.
- **Accessibility:** 5 published access statements are quoted and checked against cached
  official pages: St Bride's, St James's Piccadilly, St Margaret Pattens, St Mary
  Aldermary and St Paul's. The Friends pages and the other official homepages I checked
  say nothing about access, so the rest remain unknown, not "inaccessible".
- **Fees:** St Paul's publishes £27 per adult for sightseeing, and the Temple Church
  listing mentions an entrance fee. No other fee is stated.

### Visitor hours outside the City

St Paul's, St Clement Danes and St James's Piccadilly now have hours quoted from their
official sites, and the Chelsea chapel has Sunday services only. All 36 surviving
register entries now have published access information. The other 20 are the 19 lost
churches and St Anne's Soho, whose Wren body was destroyed.

### Walking routes

`routing_wren.py` uses the FOSSGIS OSRM foot profile (OpenStreetMap data, usage policy
of at most one request per second, cached once per leg, attribution shown). The pilot's
Walbrook to Aldermary leg is 293 m, about 4 minutes, or about 49 minutes including the
editorial visit estimates. Legs run between source-reported site coordinates, not
surveyed entrances, and are not step-free assessments.

### Aldermary

The Historic England listing text is now cached from British Listed Buildings, which
republishes the OGL list entry and whose robots.txt allows access. The quoted wording
matches the manual read of the Historic England page. Historic England itself still
returns HTTP 403 to the downloader; those failures stay in the source records.

### Still missing after this pass

- Construction intervals for 26 of 45 replacement churches: 15 disputed and 8 with a
  milestone only, plus 3 agreeing pairs that may not be independent.
- Verified dates for losses beyond the list's years (34 events, 1 verified).
- Accessibility for most churches, and verified entrance coordinates for all of them.
- Cornhill's attribution, which needs the building accounts.
- A primary source independent of the encyclopedia tradition, such as the Wren Society
  volumes, which are not openly available.

# Full-Picture Checkpoint: 2026-10-08 (second pass)

This section is the current state. The earlier collection checkpoint follows it
unchanged except where marked. No website files were touched, and nothing has been
committed.

Every number below comes from `exports/analysis_summary.json`, `exports/discovery.json`
or `data/london_wren_churches/coverage.json`, generated by the scripts in this folder.
Each figure carries an evidence tier. Most of the coverage comes from one secondary
list, and the findings should be read with that in mind.

### What the data shows

**Rebuilding was front-loaded; completions were spread out.** Of the 45 post-fire
replacement parish churches, 30 have a reported start in 1670-1679, 9 in 1680-1684
and 6 in 1685-1689. Reported end years are spread more evenly: 12 in 1675-1679, 12 in
1680-1684, 13 in 1685-1689, 5 in 1690-1694 and 3 in 1695-1698. The earliest start is
1670 and the latest end is 1698. The median reported span is 7 years, ranging from 0
to 27. These are ranges with unspecified scope; a long span can include a later tower.

**Where sources disagree, they mostly disagree about the end.** Ten of the 45 have
conflicting ranges. In 8 of those 10 the sources give the same start year and a
different end year (for example Walbrook 1672-1679 against 1672-1687). That pattern
fits a difference in what is being dated (body versus tower or steeple), but we have
not adjudicated it, and all alternatives are kept.

**Evidence strength for those 45 construction ranges:** 4 verified, 10 where the
list and the heritage listing agree (possibly not independent), 10 disputed and 21
reported by the list alone. Nearly half rest on a single secondary source.

**Half the replacement churches no longer stand.** By the list's own fate sections,
the 45 split into 20 standing churches (11 survived in original form, 8 substantially
rebuilt after the Blitz, 1 altered before it), 5 where only the tower remains, and 20
that are gone (10 under the Union of Benefices Act, 5 for other reasons, 3 destroyed in
the Blitz and 2 whose stones were reused elsewhere).

**The Blitz was not the main cause of loss.** There are 35 reported loss events at 30
churches (some churches have more than one, such as wartime destruction followed by
demolition of the ruins). By mechanism: 10 Union of Benefices demolitions, 11 wartime
destructions, 4 site clearances or street works, 2 for structural safety and 8 where
no reason is stated. The losses happened in waves:

- 1782-1841: four demolitions to make room for the Bank of England, the London Bridge
  approaches, the Royal Exchange and the widening of Threadneedle Street.
- 1868-1897: all ten Union of Benefices demolitions.
- 1900 and 1904: two churches judged structurally unsafe.
- 1940-1941: the Blitz. Only three of the eleven wartime events carry a year in the
  list; the rest say "destroyed in the Blitz" without a date.

**The Union of Benefices demolitions coincide with the City emptying out.** The
census population of the City was 130,117 in 1801 and 132,734 in 1851. It then fell to
108,078 in 1861, 83,421 in 1871 and 32,649 in 1901, a drop of about 70% between 1861
and 1901, the decades in which all ten Union demolitions fall. The 1831-1841
street-works demolitions happened while the census population was still roughly flat
(the 1782 one predates the first census). This is a timing
coincidence in two series, not a tested cause, and the population table has its own
caveats (1941 is not a census year; another passage in the same article gives different
figures).

**The fire's losses were absorbed, not just rebuilt.** The list of churches burned in
1666 and never rebuilt has 34 parishes. Thirty-three of them were united with one of
27 Wren churches in our register (the other went to St Mary Woolnoth, which is not a
Wren candidate). St Mary-le-Bow absorbed three. The list gives no union dates.

**Some Wren fabric travelled.** Three relocations are now verified against a source
that holds or lists the moved fabric:

- St Mary Aldermanbury to Fulton, Missouri. The custodian museum says removal began in
  1965 and the foundation stone was laid in October 1966; the list says 1964. Both are
  kept, and the museum's 1965 is the verified value.
- All Hallows Lombard Street's tower, re-erected in 1940 at All Hallows, Twickenham
  (Historic England). Its City demolition year differs between sources: 1937 in the
  article and 1939 in the list.
- The upper part of St Antholin's spire, now at Round Hill, Sydenham. Its origin is
  confirmed by Historic England; the 1829 date comes only from the article.

St Dionis Backchurch's bells went to All Hallows Lombard Street when St Dionis was
demolished, and six are reported surviving at Twickenham, so two lost churches are
linked through objects rather than buildings.

**What you can visit, as published by Friends of the City Churches on 2026-10-08:**
32 register entries in the City have a listing. Of these, 20 are interiors with
published hours. Four are interiors with restrictions: St Mary Abchurch (closure
notice), St Michael Paternoster Royal ("currently not open to the public"), St Edmund
(by arrangement) and St Clement Eastcheap (no regular opening times). The other 8 are
towers, gardens or remains, and only St Dunstan-in-the-East lists hours. The
sources disagree on when Abchurch closes: the charity says from August 2026, the
church's own page says from around 12 October 2026. St Paul's and the four churches
outside the City have no listing in this source.

### Updated measures

| Measure | Count |
| --- | ---: |
| Register candidates | 56 |
| Source records (including failures) | 153 |
| Failed source records (two are Aldermary URLs) | 4 |
| Verified claims | 34 |
| Disputed claims | 8 |
| Extracted claims | 3,775 |
| Events, all tiers (seed-derived, parish unions and reviewed) | 164 |
| Verified dated events (timeline) | 15 |
| Lost parishes (1666, not rebuilt) | 34 |
| Census population rows | 24 |
| Third-party visitor listings matched (churches and lost parishes) | 38 |
| Discovery: church-to-church edges / relocations / churches with parish unions | 8 / 5 / 27 |

### Still missing

- Verified construction ranges for 41 of the 45 replacement churches. The tiered
  chart shows them by tier, but an honest "rebuilding curve" needs more verified rows.
- Costs, fabric condition, accessibility, entrances and fees: none are verified.
- Reasons for 8 loss events are not stated in the list.
- Visitor hours for St Paul's and the four churches outside the City.
- Pedestrian routing: no source selected, so walks remain stop sequences only.
- St Michael Cornhill's attribution and the traditional count of 51 remain open.
- St Mary Aldermary's official listing is recorded from a manual read because the
  downloader gets HTTP 403. There is no cached copy or hash.

# Collection Checkpoint: 2026-10-08

This is the cohort, dated-event and weekday-pilot checkpoint, not a completed
historical dataset or visitor guide. No posts or website assets have been changed.

## Collected Evidence

| Measure | Count |
| --- | ---: |
| Seed rows retained | 56 |
| Linked church articles fetched | 56 |
| Discovered canonical heritage-entry targets | 42 |
| Additional explicit official-entry navigation targets | 3 |
| Additional official church history / visitor page targets | 7 |
| Successful reference URL fetches, including alternatives and church pages | 48 |
| Candidates with fetched references, including context and visitor pages | 36 |
| Currently failed reference URL records | 4 |
| Total source records, including seed and failures | 109 |
| Retained claims, including reviewed interpretations | 3,665 |
| Extracted claims | 3,634 |
| Disputed structured claims | 8 |
| Verified reviewed claims | 23 |
| Reviewed dated events | 11 |
| Sourced visitor records | 3 |

An article or reference being fetched does not mean its claims were verified.
One candidate can have several reference targets, including listed monuments or
footings rather than a church body. Broad reference passages are candidate evidence,
not all relevant architectural facts. The linked Royal Hospital Chelsea article
describes more than the chapel listed in the seed.

### Failed-Source Follow-Up

Of the original ten failed URLs, three had read timeouts and seven returned HTTP
403. A single normal failed-only retry recovered seven canonical URLs. Two of the
three remaining entries were cached through the site's official-entry navigation
URLs: St Olave's tower and Fishmongers Hall. The latter is contextual evidence,
not a St Magnus church entry, and is explicitly labelled `context_passage`.

St Mary Aldermary (1079145) remained blocked in the downloader at both canonical
and official-entry URLs. Its official-entry view was readable through the webpage
tool, but that is not counted as a successful reproducible cache fetch. The current
four failed URL records include superseded canonical failures for the two recovered
entries and two Aldermary URLs; they do not represent four inaccessible buildings.
Earlier failed attempts are preserved in refreshed source metadata. No access
controls were bypassed, and successful cached pages were not refetched.

## Cohort Reconciliation

The seed's eight main fate sections contain 51 rows, including St Paul's. Its
introduction states 51 parish replacements plus the cathedral. The list alone does
not reconcile that discrepancy, and we have not invented a missing building.

All 56 candidates have now been reviewed for the kind of work described in their
cached history. The current operational categories are:

| Category | Count |
| --- | ---: |
| Post-fire replacement / substantial body rebuilding | 45 |
| Post-fire repair / partial reconstruction | 3 |
| Rebuilding of a church that survived the fire | 1 |
| Cathedral | 1 |
| Interior refurbishment | 1 |
| Outside fire area | 4 |
| Wren-office attribution unresolved | 1 |

These are source-supported research classifications, not 45 independently verified
attributions or a correction to the traditional 51. Most new decisions are based
on the individual article, not an independently corroborated original document.
Their supporting passage IDs and work scope are recorded in identity decisions.
The earlier six corroborated replacements remain identifiable by their rationale.

The repairs are St Mary-at-Hill (interior/east end), St Christopher le Stocks
(reconstruction retaining outer walls/tower) and St Dunstan-in-the-East (patched
body and later Wren tower). St Andrew Holborn survived the Great Fire and was
subsequently rebuilt; it belongs in the wider atlas, not fire-destroyed replacements.

St Michael Cornhill remains unresolved: the article describes traditional Wren
attribution but cites a modern architectural assessment disputing his office's
involvement with the body; upper tower work is attributed to Hawksmoor. We have
not forced a conclusion from its inclusion in the seed.

Every seed row remains accounted for in the generated reconciliation report.
The traditional numerical discrepancy remains open; broader programme counts
need not match our operational distinction between replacement and repair.

## Findings From Sample Review

The six corroborated replacements are St Clement Eastcheap, St James Garlickhythe,
St Michael Paternoster Royal, St Mary Somerset, St Olave Old Jewry and Christ Church
Greyfriars. Wren attribution is verified for these six plus St Stephen Walbrook.
St Clement's 1683-1687 and St Mary Somerset's 1686-1694 body-construction ranges
agree across the inspected article and official listing. Somerset's interval
includes interrupted work and must not be presented as continuous labour time.
Its 1871 body demolition is partial demolition because the tower remains.

- St Stephen Walbrook: Wikipedia's 1672-1679 and Historic England's 1672-1687 are
  retained as disputed construction ranges. We have verified the explicit Wren
  attribution, not chosen an unsupported explanation for the different end years.
- St Dunstan-in-the-East: the official listing dates Wren's tower to 1698 and
  identifies the body as Laing's 1817-18 work. Its reviewed event is tower-specific,
  not a whole-church start/completion interval.
- St Mary Aldermanbury: the article contains 1965 and 1966 relocation statements.
  (Superseded in the second pass: the custodian museum's page was collected and the
  1965 removal start is now a verified relocation event; the seed's 1964 is kept.)
- St Benet Fink: article evidence distinguishes partial demolition in 1842 from
  the remaining building's demolition in 1846. Independent checking remains due.
- St James Garlickhythe: official 1674-1687 differs from the article's 1676
  foundations, 1682 reopening and 1683 body completion. Component scope remains
  unresolved; the two structured ranges are disputed, not rejected.
- St Michael Paternoster Royal: body start is 1686 in the listing versus 1685 in
  the article. Tower completion 1713 and steeple work 1713-1717 are different
  reported milestones, not automatically interchangeable.
- St Olave: the listing gives body loss in 1888, the article 1887. Both structured
  claims remain disputed. Tower and part of the wall were retained.
- Greyfriars: listing range 1677-1691 and tower 1704 differ from the article's
  church/tower-without-steeple completion in 1687. No duration event was inferred.

These cases demonstrate why a single construction year or survived boolean would
misrepresent the histories. They are not aggregate findings about all candidates.

### Expanded Dated Evidence

St Edmund's 1670-1679 body range agrees across the inspected listing and article.
The article identifies Hooke design signed off by Wren, so a timeline interval
does not establish sole Wren authorship.

Walbrook's detailed official history reports foundation stones on 17 December
1672, readiness for use at vestry dinner planning on 27 May 1679, and separate
steeple construction in 1713-1717. Foundation/readiness are milestones, not
zero-year construction intervals. These do not adjudicate the listing's 1687
end date. The official wartime page reports dome damage in 1941, not total loss.

St Augustine's official listing reports body and spire destruction in 1941,
with lower tower stages retained. The same entry reports reconstruction in 1966
and restoration in 1967; the chart preserves a 1966-1967 reporting window rather
than choosing a single completion year or implying continuous labour.

## Coverage Limits

### First Research Previews

- `exports/cohort_map.html`: all 56 source-reported sites, coloured by operational
  cohort. Locations are extracted seed claims, not checked visitor entrances.
- `exports/reviewed_timeline.html`: eleven reviewed events only, with component
  scope preserved. Somerset's body demolition is distinct from complete loss.
- `exports/church_register.csv`, `exports/map_points.json` and
  `exports/analysis_summary.json`: reproducible research tables and summary.
- `exports/pilot_walk.html` and `exports/pilot_walks.json`: one sourced weekday
  stop sequence with two conditional interior/cafe stops and a closure-restricted
  optional interior. No pedestrian route, walking distances or total trip time.

The sparse timeline is a coverage preview, not a representative city-wide rebuilding
curve. No imputed events, cost rankings or automated visiting recommendations are
included. Charts render on desktop and narrow screens; legend filtering was checked.
The map uses OpenStreetMap tiles and displays contributor attribution. Chart scripts
are embedded locally; map tiles still require network access. Exports remain ignored.

All candidates have seed construction-date text and coordinate claims, but these
are not verified phase-specific timelines or visitor-entrance coordinates.
The seed and article claims provide extracted attribution for many candidates;
structured loss-date fields appear for 23, including one disputed and one verified
body-loss date. Costs exist in narrative passages but
have not been converted into comparable reviewed cost records.

Published visitor hours are now sourced for Walbrook and Host Cafe at Aldermary.
Accessibility, fees, entrance coordinates and pedestrian routes remain unverified.
Source licences and site-specific permissions
still need review before publishing derived text, images or routing data.

### Weekday Pilot And Closure Notice

The proposed sequence is St Stephen Walbrook then St Mary Aldermary through Host
Cafe. Suggested 25- and 20-minute visit durations are editorial estimates, exclude
walking and do not constitute a total trip duration. Checked on 2026-10-08:

- Walbrook publishes Monday-Friday 10:30-15:30, closed weekends except great
  festivals. It advises contacting the church and checking its calendar because
  private events can cause early closure.
- Host Cafe publishes Monday-Friday 07:30-16:00. These are cafe hours, not
  unrestricted church access. Booking for work sessions over 1.5 hours is not
  presented as a blanket tourist-booking requirement.
- Abchurch announces closure for about nine months from around 12 October 2026.
  The reopening date is unknown; its history-page general weekday-opening wording
  does not override that notice. It is not a required interior stop. Exterior
  access during refurbishment is not assumed.

The walk validator rejects unverified visiting evidence, mismatched claim ownership,
required interiors with announced closures and unmeasured route metrics. Current
scope is a local research pilot, not a general itinerary engine or live availability
service. Official links and last-checked dates travel with every stop.

## Next Research Priorities

Focused supplementary reading found St Mary Woolnoth's article describes Wren
repair followed by demolition in 1711 and a Hawksmoor replacement, while St
Sepulchre's article attributes post-fire rebuilding to Joshua Marshall. These are
follow-up leads, not added cohort members or a resolution of the traditional count:

- https://en.wikipedia.org/wiki/St_Mary_Woolnoth (Early history and Hawksmoor)
- https://en.wikipedia.org/wiki/St_Sepulchre-without-Newgate (Architecture)

1. Resolve the Cornhill attribution and traditional programme count using stronger
  sources; independently corroborate the source-supported classifications.
2. Expand verified construction phases and loss/restoration events from cached
   sources; add accessible official histories for demolished and relocated buildings.
3. Revisit failed heritage sources through documented official access or record
   their continuing unavailability. Do not bypass access controls.
4. Collect official visiting information for a small first walk, retaining unknown
   values and checking related museum/monument stops individually.
5. Generate representative aggregate history charts only after dated-event coverage
  improves; then discovery connections and curated itineraries. The later publication
  plan will inspect the existing website first.

## Local Reproduction

Run the collection and review commands in README.md. Cached snapshots and generated
tables are in the ignored `data/london_wren_churches/` directory; the code, authored
fixtures and sample review decisions are trackable. No commits or pushes were made.
Collection uses the project's existing Python 3.14.2 environment and dependencies.