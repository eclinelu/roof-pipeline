### 2026-08-03: The visual pass computes facet correspondence from POINT-SET OVERLAP by mutual best match, never from indices and never from a tuned threshold

**Decision:** Facet correspondence in a visual pass is computed from set overlap
between the old and new facets' point index arrays, and from nothing else.
Grouping is by **mutual best match**: an edge runs from every old facet to the
new facet it shares the most points with, and from every new facet to the old
facet it shares the most points with, and rows are the connected components of
that graph. `REPORT_FLOOR` is a threshold, but it governs only what is
**printed** beneath a row, never what is **grouped**, and the page states which
is which. Every pairing reports its overlap in both directions. **The pixel diff
is decorative. The overlap fraction is the instrument.**

**Why:** Indices shift silently whenever a facet merges, splits, appears or
vanishes, so facet 12 in one artifact is not facet 12 in the next. The failure
that matters is not a visible mislabel but an invisible one: old facet 20
vanishes, new facet 20 exists as something unrelated, and index pairing renders
that row as an ordinary 1-to-1 that merely changed a lot. A vanished facet is a
finding, and index pairing destroys it while looking correct.

A cutoff was rejected because it is a tuned parameter with no principled value.
Set it low and facets that merely share a boundary strip collapse into one giant
row. Set it high and a genuine split whose halves each keep 40 pct of the parent
stops being detected. A cutoff tuned so that this pass looks tidy will silently
mis-group the next one, which is the exact failure this log has already recorded
for scale-dependent thresholds elsewhere in the pipeline. Mutual best match
needs no such number: "most" is a comparison, not a magnitude, so it carries no
units and does not transfer badly between clouds. All five layout cases fall out
of the component shape with no value chosen by hand.

**Evidence:** `tests/test_visual_pass.py`, 43 tests, all passing. The
load-bearing one is `test_indices_are_never_used_for_pairing`: the same geometry
with its labels reversed, where an index-based implementation returns the
identity mapping and fails. Supported by
`test_vanished_is_not_disguised_as_one_to_one`,
`test_new_facet_has_no_predecessor` and
`test_every_facet_lands_in_exactly_one_row`.

**The measured case for demoting the pixel diff.** In pass
`r2-vs-grid-adopted`, the 8 main facets have overlap of exactly
1.00000000000000000 in both directions, meaning bit-identical point membership.
All 8 nonetheless have DIFFERENT byte hashes and differ in between 27,974 and
279,270 pixels out of 3,217,500. A pixel diff read on its own would have
reported eight geometry changes that did not happen. The cause is annotation:
title length and label placement move pixels without moving a single point. So
the pixel diff is never read alone. It is read next to the overlap, which is
computed from geometry and is the one of the two that can settle the question.

**Rejected:** pairing by index, for the vanished-facet failure above. A tuned
overlap cutoff, for the transfer failure above. Using the pixel diff as the
change detector, refuted directly by the 8-facet measurement.

**Cost if wrong:** low. Correspondence is recomputed from the `.npz` index sets
on every run and nothing is frozen from it. Deleting the pass output and
regenerating reproduces all 29 overlap values exactly and 58 of 58 crops
byte-identically, so an error here is visible and cheap to correct.

**Attribution.** The design and its rationale are mine, recorded in the
`scripts/visual_pass.py` module docstring when it was written. Emmett's
requirements were that correspondence not be assumed and that the instrument be
able to fail.
