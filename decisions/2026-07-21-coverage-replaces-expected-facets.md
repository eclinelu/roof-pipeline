### 2026-07-21: Coverage replaces expected_facets as the completeness gate

_Written 2026-07-26, late. The decision was made and implemented on 2026-07-21
and is cited in `roofkit/coverage.py` as "decision 2026-07-21", but no entry was
ever written; the gap was found by a sweep on 2026-07-26. Reconstructed from
`TASK4-COVERAGE-HANDOFF.md`, a note written contemporaneously on 2026-07-22,
not from memory. Where that note records Emmett's position it is quoted as such;
the rest is reconstruction and is marked._

**Decision:** Completeness is judged by a physical invariant instead of a
human-supplied facet count. A roof is a closed surface, so in plan view every
part of the building footprint must be explained by some fitted facet; where it
is not, a facet is missing. `expected_facets` is retired as the gate.

Inside an unexplained region the minimum facet SIZE is relaxed, because that is
what rejected the big_house dormers. FIT QUALITY IS NEVER RELAXED: the plane RMS
a small facet must achieve is the same one the large facets already achieve.

**Why:** `expected_facets` is a number a human has to know and type. It blocks an
automated run on a new house, and it cannot catch a facet nobody expected, which
is precisely the failure it was supposed to guard against. The closed-surface
invariant needs no prior count: it asks "is every building cell explained?"
instead of "did we get N?".

The hard rule is what keeps the relaxation honest. A small enough patch of
ANYTHING is planar, so if size and quality were both relaxed while iterating
toward full coverage, the pipeline would eventually fit a plane to noise and
report success. Size is negotiable because a dormer really is small; planarity
is not, because a noisy patch is not a surface.

_Reasoning above is reconstructed from the 2026-07-22 note's "Draft Why", which
was written by Claude at the time and not quoted from Emmett._

**Reverses two standing decisions:**
- `expected_facets` pinned at 8 as the vanish guard. It stays in the config as a
  cheap regression check that a known-good dataset still yields its known facet
  count, but it is no longer THE completeness gate.
- "Dormer detection deferred until after the three new houses" (2026-07-18).
  Coverage forces the dormers into scope, because they are exactly the
  unexplained regions the invariant finds.

**Evidence** (measured 2026-07-21/22, before the entry was written):
- Task 2 dormer fork resolved as CASE 1: the residual is 19.1 percent of
  `roof.npy`, and raw roof-band point density in dormer cells matches clean main
  roof exactly (median 9 points per cell each, ratio 1.00). The residual is by
  construction already inside `roof.npy`, so dormers survive crop, height,
  colour and planarity; only the facet-acceptance step (`min_points_frac`) drops
  them. They were never missing from the data, only from the segmentation.
- The hard rule was verified to bite rather than being assumed: blob 8, at RMS
  7.4x spacing, was REJECTED on quality while genuine dormers passed under
  relaxed size. Quality bar 2.95x spacing, set by the worst main facet.
- Recovery took 8 main facets to 18. Pre-recovery coverage 83.6 percent.

**Rejected:**
- Keeping `expected_facets` as the gate. A magic number that blocks automation
  and is blind to the unexpected.
- Alpha-shape or concave-hull completeness. Trades one magic number for another,
  since the shape parameter has to be chosen per cloud.
- Relaxing fit quality to force coverage to 100 percent. This is the failure
  mode the hard rule exists to prevent; it fits noise and reports success.

**Known limits, stated at the time:** coverage catches missing facets, lost
edges, and dormers rejected as too small. It does NOT catch one real facet split
into two coplanar halves, nor a spurious facet fitted to noise inside an
already-covered region. It is a PLAN-VIEW test, so vertical surfaces project to
near-zero plan area and correctly never register as gaps.

**Cost if wrong:** If the invariant is applied where a building genuinely has an
unroofed interior region, that region reads as a permanent missing facet. If the
size relaxation goes too far, junk facets enter; that is what the separately
adopted size floor now guards
(2026-07-26-size-floor-as-junk-filter.md).
