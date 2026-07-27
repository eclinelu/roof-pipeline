## Decision log

_Append only. Newest at the top. Past entries are never edited. A reversal is a new entry that references the one it overturns._

## Entries (newest first)

- [2026-07-26: Blob candidates are selected by CELLS, not bounding box; a permanent assertion enforces single ownership](2026-07-26-duplicate-points-cell-selection.md)
- [2026-07-26: The 2026-07-23 facet state is SUPERSEDED, not corrected](2026-07-26-2026-07-23-state-superseded.md)
- [2026-07-26: The size floor is kept as a junk-facet filter, and both thresholds are stated in transferable form](2026-07-26-size-floor-as-junk-filter.md)
- [2026-07-26: Open3D's RANSAC is nondeterministic under a fixed seed; `probability=1.0` becomes the default](2026-07-26-ransac-nondeterminism-probability-1.md)
- [2026-07-25: Facet geometry is persisted every run (R1), and actionable diagnostics go to a file (R2)](2026-07-25-persist-geometry-and-diagnostics.md)
- [2026-07-25: A merge requires coplanarity AND spatial adjacency](2026-07-25-merge-requires-coplanarity-and-adjacency.md)
- [2026-07-21: Project goal reframed from commercial venture to engineering portfolio](2026-07-21-portfolio-not-commercial.md)
- [2026-07-20: PDF report is a house-agnostic, freeze-verified deliverable generator; prototyped on big_house, paused for refinement](2026-07-20-pdf-report-generator.md)
- [2026-07-18: Run 2 evidence addendum: the rule is global, the threshold sits on a plateau, the pitch offset is uniform, and the total is caveated](2026-07-18-run2-evidence-addendum.md)
- [2026-07-18: Run 2 with a contiguity rule replaces the artifact-stretched ridge extent; both runs reported, failure first](2026-07-18-contiguity-rule-run2.md)
- [2026-07-18: Facet 6/7 inclinometer readings are scored as 90 minus the raw value; the raw values stay in the record](2026-07-18-facet-67-inclinometer-complement.md)
- [2026-07-18: The explanation gate points one way: Claude explains, Emmett is never quizzed or blocked](2026-07-18-explanation-gate-one-way.md)
- [2026-07-15: Dormers are in scope but unresolved this run; they contaminate specific per-facet numbers, not only the total](2026-07-15-dormers-unresolved-this-run.md)
- [2026-07-15: The two-cloud eave bracket needs a shared absolute density floor and a guaranteed superset](2026-07-15-eave-bracket-shared-density-floor.md)
- [2026-07-14: Roof-derived scale is a big_house exception; the wall instrument is retired for this dataset](2026-07-14-roof-derived-scale-exception.md)
- [2026-07-14: Eave erosion is handled by a two-cloud bracket, never a correction](2026-07-14-eave-erosion-two-cloud-bracket.md)
- [2026-07-14: Ground truth is audit-only, never a pipeline input; outputs are pre-registered by commit](2026-07-14-ground-truth-audit-only.md)
- [2026-07-14: Constraint discovered: this cloud has no derivable wall corner; parallel-plane separation is the scale instrument](2026-07-14-no-derivable-wall-corner.md)
- [2026-07-14: Scale span is derived from wall-plane geometry, never from clicked corners; reconnaissance runs before the tape](2026-07-14-scale-span-from-wall-planes.md)
- [2026-07-13: Leveling applied from the three-ridge least squares; null check passed; pitch floor is 0.20 degrees](2026-07-13-three-ridge-leveling.md)
- [2026-07-13: REVERSAL: Z is tilted 1.25 degrees; ridge inclination replaces the symmetry gate as the primary vertical reference](2026-07-13-reversal-ridge-inclination-vertical.md)
- [2026-07-13: Z gate first reading: a ~0.85 degree rigid tilt is the pitch uncertainty floor](2026-07-13-z-gate-first-reading.md)
- [2026-07-13: Assumption A3 held: one global height cutoff cleared sloped terrain](2026-07-13-assumption-a3-height-cutoff.md)
- [2026-07-12: RANSAC peeling gets a nearest-plane reassignment pass](2026-07-12-nearest-plane-reassignment.md)
- [2026-07-12: Site-specific numbers live in a per-dataset config file, not in code](2026-07-12-per-dataset-config-not-code.md)
- [2026-07-12: Deliverable is a dimension sheet; area ships first as stage 7a](2026-07-12-dimension-sheet-7a-first.md)
- [2026-07-12: Vegetation removed by color then planarity; rests on the roof-is-not-green assumption](2026-07-12-vegetation-color-then-planarity.md)
- [2026-07-12: No ground-plane RANSAC; vertical is georeferenced Z behind a symmetry gate](2026-07-12-no-ground-plane-ransac.md)
- [2026-07-12: The adversary is vegetation, not walls](2026-07-12-adversary-is-vegetation.md)
- [2026-07-12: ODM must run past odm_filterpoints to produce a point cloud](2026-07-12-odm-past-filterpoints.md)
- [2026-07-12: Claude Code writes the analysis code; the gate is explanation, not authorship](2026-07-12-claude-writes-analysis-code.md)
- [2026-07-12: Scale comes from one tape-measured ground distance](2026-07-12-scale-from-one-tape-measure.md)

## How this directory works

One entry per file, named `YYYY-MM-DD-short-slug.md`. Append-only still applies:
to add a decision, add a NEW file and a new line at the top of the list above.
Never edit an existing entry. If a decision turns out to be wrong, write a new
entry that reverses it and names the file it overturns; the reversal is more
interesting than either position alone.

The list above is the record of order. Several entries share a date, so sorting
filenames cannot recover the sequence they were written in.

Current project state lives in `../STATE.md`, which is overwritten in place
rather than appended to. Opposite rules, deliberately: state must be true right
now, entries must never change.

This directory was split out of a single `DECISIONS.md` on 2026-07-26 with no
text changed. `python scripts/verify_decisions_split.py` reassembles the
original from these files and diffs it against the last committed `DECISIONS.md`
to prove it.
