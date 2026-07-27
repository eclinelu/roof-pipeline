### 2026-07-26: min_pitch is a definition of what counts as a roof, not a filter; set to 5, with a separate low-slope label

**Decision:** `min_pitch` drops from 10 to 5 degrees in `find_roof_planes`,
`discover_facets` and `recover_facets`. Separately and independently, any facet
below 2:12 (9.4623 degrees) is LABELLED `low_slope` in the output. The label
excludes nothing.

**Why:** min_pitch was being defended as a safety filter and it is not one. Every
threat it supposedly guarded against is already handled elsewhere: ground by the
crop box and height cutoff (2026-07-12-no-ground-plane-ransac.md), walls by
`max_pitch=60`, foliage by the ExG colour cutoff then planarity
(2026-07-12-vegetation-color-then-planarity.md), and badly fitted planes by the
fit-quality bar.

Measured directly rather than argued. Of the four sub-10-degree planes a 10
degree floor rejected on big_house, TWO ALSO FAILED THE QUALITY BAR
independently, so the floor was not what excluded them:

    blob 0  115,092 pts   8.86 deg   quality 3.561 vs bar 2.948   FAILS
    blob 6   51,435 pts   8.16 deg   quality 2.219 vs bar 2.948   passes
    blob 8   10,992 pts   6.79 deg   quality 2.741 vs bar 2.948   passes
    blob 8    9,087 pts   1.22 deg   quality 3.300 vs bar 2.948   FAILS

The two that pass carry 62,427 points and 2.969 cu^2 of gross surface. At 10 the
pipeline was deleting real low-slope roof and protecting nothing.

**Why 5 and not lower, and NOT because of the freeze.** The frozen result
surviving is a CONSEQUENCE of this value, never a reason for it. Choosing a
threshold to preserve a published number is the one thing this project cannot
do, so the argument stands entirely on its own measurement.

A near-horizontal plane laid across a pitched roof cuts a thin contour band
through every slope on it, and RANSAC will fit that band as a plane. On big_house
that artifact appears in main discovery at 4.0354 degrees with 275,975 points,
and two independent measurements identify it as an artifact:

  - It FAILS the quality bar: 3.0757 against 2.948. A real surface at that pitch
    would be planar; this one is not planar enough to be one.
  - Its plan footprint lies over ALL 8 main facets while covering only 0.3 to
    1.4 percent of each. A physical roof surface borders two or three
    neighbours. Threading a sliver across every facet on the building is what a
    contour band does, not what a surface does.

5 excludes it, and sits inside the measured 0.922-to-5.866 degree gap in the
recovery pitch distribution.

**Correction to an earlier claim, recorded because it was wrong.** The artifact
was first described as "taking points from all eight facets," inferred from net
point-count deltas. Direct intersection of the persisted inlier INDEX arrays
(possible only because of R1) shows it takes points from 7 of 8, not 8 (facet 4
loses none), totalling 16,307 points: 5.91 percent of the plane and under 0.6
percent of any facet it touches. 94 percent of its membership was points that
belonged to no main facet before. Net deltas overstated the effect; the footprint
measurement, not the point-theft measurement, is what carries the argument.

**HONEST LIMIT.** The usable plateau around 5 is about 1.8 degrees wide. The size
floors adopted the same day sit in empty bands 15.9x and 9.0x wide
(2026-07-26-size-floor-as-junk-filter.md). The evidence for this value is
materially thinner than for those, it rests on one cloud, and it must be
re-measured per site rather than copied forward.

**The low-slope label, a separate decision.** 2:12 is the roofing-practice
boundary between steep-slope and low-slope assemblies: different material,
different labour, different price, broken out separately in commercial reports.
That is almost certainly why 10 degrees "felt right" as a cutoff, since 2:12 is
9.4623 degrees. It is a good reporting category and was a bad exclusion rule. A
low-slope facet is now measured, counted and reported like any other, and
carries a flag so the report can separate the assemblies.

**WHAT min_pitch = 5 STILL EXCLUDES.** Stated as a number, because a definition
that quietly discards surface is worse than the filter it replaced. Four planes
that CLEAR the same quality bar the accepted facets clear:

    blob  0  147,505 pts  3.743 deg (0.78:12)  quality 2.833   gross 16.0915 cu^2
    blob  0    9,058 pts  3.574 deg (0.75:12)  quality 1.010   gross  1.5532 cu^2
    blob  0    6,829 pts  3.624 deg (0.76:12)  quality 1.823   gross  1.0718 cu^2
    blob 15    2,623 pts  4.010 deg (0.84:12)  quality 2.147   gross  0.3260 cu^2

    TOTAL: 166,015 points, 19.0425 cu^2 of gross surface.

Blob 0's 16.09 cu^2 plane is NOT the spanning artifact and must not be confused
with it. Two things separate them: it is confined to a single residual region
rather than threaded across the building, and it CLEARS the quality bar (2.833)
where the artifact fails it (3.076). At 0.78:12 this reads as a genuinely flat
roof section, which is a thing buildings have.

**Open question this raises, deliberately left open:** should RECOVERY carry its
own `min_pitch`, separate from MAIN DISCOVERY? They are separate parameters that
currently share a value for no measured reason. The spanning artifact is a
main-discovery problem; inside a residual blob a candidate has already passed the
quality bar, the point floor and the area floor, so the pitch window is doing
much less work there. The excluded area above is the evidence for why the
question matters, not an argument for any particular answer. Measured as a sweep
in `reports/big_house/recovery-pitch-sweep-2026-07-26.json`, DIAGNOSTIC ONLY: no
value is adopted here, and adoption is pre-registered on the next site before
that site is scored.

**Rejected:**
- Keeping 10. Measured to delete well-fitted roof while protecting against
  nothing the quality bar does not already catch.
- Dropping to 2. Admits the 4.0354 degree spanning artifact into MAIN discovery,
  where it takes points from seven facets and shifts all eight.
- Removing the pitch window entirely. `max_pitch` is still doing real work
  against walls, and without a lower bound the contour-band artifact is admitted.
- Using the 2:12 boundary as the admission rule. It is a materials boundary, not
  a geometry one; conflating the two is what produced the original mistake.

**Evidence:** `reports/big_house/task7a-2026-07-26.json` (A1 pitch distribution,
A2 min_pitch sensitivity, A3 the quality test), `spanning-plane-2026-07-26.json`
(the 4.0354 degree plane, its quality and its footprint overlap),
`empty-blobs-2026-07-26-r2.json` (what 5 still excludes),
`attribution-2026-07-26.json` (min_pitch 5 contributes +1.265 coverage points).

**Cost if wrong:** Too low and the contour-band artifact enters as a facet,
inflating area and corrupting neighbouring facets' membership; A2 measured
exactly that at min_pitch 2. Too high and real low-slope roof is silently
deleted, which is what 10 was doing. The 1.8 degree plateau is the whole margin,
and it is thin.
