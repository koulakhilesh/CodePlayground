# Methods And Evidence

## Identity

Churches, parishes, building phases and sites are not interchangeable. IDs use
namespaced SHA-256 keys independent of display names. Article-derived candidate
IDs may be explicitly mapped to a retained ID during review; aliases are preserved.
St Paul's is a cathedral, not an ordinary parish-construction observation.

The exploratory operational cohort is not the traditional number of churches in
Wren's programme. `parish_replacement` includes substantial body rebuilding and
can include reused medieval fabric: it does not mean every stone was new.
`parish_repair` retains explicitly patched bodies or partial interior/east-end
reconstruction with surrounding old walls/tower. `parish_nonfire_rebuilding`
separates later rebuilding of a fire survivor (St Andrew Holborn). Both repair and
non-fire work remain in the wider atlas but outside replacement-body summaries.

Identity decisions can cite supporting `evidence_claim_ids`; review validates that
the claims belong to that candidate and preserves them as `identity_claim_ids`.
`wren_work` records descriptive scope and attribution caveats. A source-supported
cohort decision does not verify dates, sole authorship, present fabric or access.
St Michael Cornhill's disputed office involvement remains an unresolved cohort.

## Claims

Claims retain a source ID, locator, reported value and review status. Conflicting
structured values become disputed; selecting a claim requires a dated rationale.
Alternative claims are never deleted. Missing values remain null, not zero, false
or an invented date. Evidence passages can differ without representing factual
disagreement: their review must determine the field and construction scope.

## Dates And Survival

Record year ranges and phase; do not turn an uncertain range into a midpoint.
Damage, restoration, partial demolition and permanent loss are separate events.
Present fabric, building form, site, current use and visitor access are independent
dimensions. Section headings in the seed are source classifications, not verified
present-day condition or access.

The research timeline accepts only events with nonempty supporting claim lists,
verified review status, matching subject ownership and valid reported year ranges.
Parish-body starts/completions and elapsed spans exclude towers, repairs, non-fire
rebuildings and the cathedral. Partial demolition remains distinct from total loss;
restoration is not new church construction. Sparse reviewed events do not justify
city-wide rates. The exploratory map retains extracted coordinates and labels them
as such, with the source location role distinct from a visitor entrance.

`date_role` distinguishes construction intervals from foundation/readiness milestones
and uncertain reporting windows. Only body events with a construction-interval role
enter duration and completion summaries. A reporting window (such as 1966/1967 in
one restoration listing) is not a continuous labour duration. Timeline rows include
event kind so component destruction/restoration is distinct from new construction.

## Evidence Tiers

`tiers_wren.py` gives every candidate a construction range with an explicit tier,
so coverage is complete without pretending everything is verified:

- `verified`: a reviewed body construction interval (rationale and date recorded).
  If it differs from the seed list, the seed range is kept as an alternative.
- `disputed`: sources give different ranges; all alternatives kept, none chosen.
  Differences may reflect body/tower/steeple scope or milestone definitions.
- `agreeing_sources`: the seed list and the first Wren-mentioning Historic England
  listing range agree. These may not be independent (lists often derive from listings).
- `reported`: a single secondary list (the Wikipedia seed table); unreviewed.

Seed-reported events are derived by rule from the seed table's Comment, Demolition
and Reason cells and its section headings, always tagged `evidence_tier: reported`
with the original text. Rules distinguish demolition, partial demolition, wartime
destruction, restoration milestones (rededication, reconsecration, reopening),
later non-Wren rebuilding, alteration and relocation. Unparsed comments are written
to `seed_unparsed.json`, not silently dropped. Loss mechanisms are grouped as Union of
Benefices, site clearance/street works, structural safety, war destruction and
reason not stated. A church can contribute more than one loss event (for example
wartime destruction then demolition of ruins), so loss counts are events, not churches.

## Context: Lost Parishes, Population, Related Sites

`context_wren.py` collects the Wikipedia list of churches destroyed in 1666 and not
rebuilt (34 parishes). Each parish union is linked to a Wren church by article URL,
then exact name, then a reviewed override in `review/parish_overrides.json`.
Unions with non-candidate churches (St Mary Woolnoth) stay unmatched. The list gives
no union dates, so union events have null years.

Population is the City of London census table on Wikipedia, which cites the City of
London Corporation and ONS. 1941 is flagged `not_census` (no wartime census) and the
2024 value is an estimate; only census rows to 1971 are charted. Another passage in the
same article gives different values (for example 1851), so treat it as context, not a
measured cause of church losses.

Related non-church sites (the Monument) carry coordinates, passages and the lost
parish they stand on. The Monument's design is attributed to Robert Hooke with an
unknowable extent of Wren's role; it is labelled a related site, not a Wren church.

## Relocated Fabric

Destination evidence uses the `relocated_component` source relationship, producing
`relocation_passage` claims that cannot feed construction-date agreement. Reviewed
relocations: St Mary Aldermanbury to Fulton, Missouri (custodian: removal began 1965;
seed 1964 kept as reported), All Hallows Lombard Street's tower re-erected at
Twickenham in 1940 (Historic England) and St Antholin's upper spire at Round Hill,
Sydenham (origin from Historic England; 1829 from the article). St Mary Aldermary's
official listing was read manually because the downloader receives HTTP 403; that
claim records `retrieval_method: manual_read` and has no cached copy or hash.

## Reviewed Decision Files (third pass)

Each file pairs a decision with evidence claim IDs that must belong to the same church;
the review step rejects foreign or missing evidence.

- `date_reviews.json`: one outcome per church. `verified_interval` needs a stated start
  and end for a named scope (body, or body and steeple). `conflict` adds a disputed range
  and no event. `verified_milestone` dates an opening, completion or bare rebuild year
  without counting as an interval. `unresolved` records why nothing was chosen.
  Verified rows report their source publisher, because an encyclopedia passage and an
  official listing are not equal evidence.
- `loss_reasons.json`: a reviewed mechanism for loss events the list left unexplained.
  Loss summaries keep one event per church, kind and year, preferring the verified one.
- `costs.json`: nominal pounds, shillings and pence as stated, with scope. The review
  fails if the amount is not in the evidence passage. Later restoration costs and organ
  costs are excluded.
- `parentalia.json`: the 1750 catalogue mapped to register IDs. The heading and every
  quoted year must appear in the cached OCR text. Years are read by eye; illegible OCR
  stays null. Used for the count reconciliation and shown beside construction tiers,
  never as a tie-breaker.
- `official_visitor_pages.json` and `access_statements.json`: quotes from official
  sites, checked against cached copies. They describe what the site publishes, not a
  survey. Stale dated notices on a page are noted, not treated as current.
- Fabric flags come from fixed phrases in official listings (for example "reconstructed
  in near facsimile"); a church without a matching phrase has no flag, not intact fabric.

The Aldermary listing is cached from British Listed Buildings, an independent site that
republishes Historic England's OGL list entries; its robots.txt allows access. It is
labelled a mirror (`relationship: listing_mirror`).

Walking legs come from the FOSSGIS OSRM foot profile (`routing_wren.py`, decision in
`review/routing-source.json`). Each leg is one cached request, within the server's
policy of at most one request per second. Legs run between source-reported site
coordinates; they are not entrance-to-entrance, step-free or surveyed routes.

## Visitor Evidence And Pilot Walks

Official visitor pages use `visitor_source_passage`, not heritage-entry claims.
Extraction retains notices in small headings and footer hours. The reviewed field
describes published information as of `checked_at`, never live availability.
Specific closure notices override generic historical opening prose. Approximate
closure dates remain approximate and do not imply a calculated reopening date.

Cafe operating hours have cafe scope, not unrestricted church scope. Unknown fee,
accessibility and entrance coordinates remain unknown. Equality or welcome statements
are not proof of step-free access. The pilot uses sourced interior access only;
exterior access at a closed building is not inferred.

`walk_wren.py` validates matching place/visit records and claim ownership, requires
verified visitor claims and rejects required interiors with announced closures.
Visit-minute values must be positive editorial estimates. Walk definitions may not
carry their own legs or walking metrics; those are computed only by the selected
routing adapter, and totals add editorial visit estimates only when every required
stop has one. This is a curated stop sequence, not an optimised or surveyed route;
optional closed stops retain their notice rather than becoming automatic recommendations.

Wider coverage comes from Friends of the City Churches church pages
(`visitors_wren.py`), discovered through the site's public church listing endpoint
(robots.txt allows it; one request, then one page per matched church with a delay).
These are `third_party_published` listings: opening text is stored verbatim with
`checked_at`, classified only as hours published, closure notice, by arrangement, no
regular hours or no hours listed. Hours are not parsed into days and times, and
nothing predicts whether a church is open now. Access scope (interior, tower, garden,
remains) comes from the listing title. Garden-only listings for lost parishes link to
the parish, not a Wren church. St Paul's and the four churches outside the City are
not covered by this source and remain gaps.

## Sources And Reuse

Preserve source retrieval dates, revision where available and content hashes.
Wikipedia prose is CC BY-SA 4.0; Historic England official entry text is generally
OGL v3.0 except where stated. Friends of the City Churches and America's National
Churchill Museum pages are copyrighted; quote briefly with attribution and link rather
than republishing. Images, maps, contributions and routing data have
separate terms. Cached full documents are local research inputs, not publication
assets. Track actual source-specific terms before publishing excerpts or datasets.