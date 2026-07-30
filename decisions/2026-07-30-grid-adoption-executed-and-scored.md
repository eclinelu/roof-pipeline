### 2026-07-30: RESULT: the grid adoption is EXECUTED and ADOPTED. Five of five predictions PASS, and the run reproduces the 2026-07-28 artifact bit for bit

**Decision:** `canonical-2026-07-30-grid-adopted` is now the CANONICAL facet
state for big_house, and the published facet coverage moves from **88.40 pct to
94.25 pct**. The published deliverable is UNCHANGED at **3,559.3 ft^2 over 8
main facets**. `canonical-2026-07-26-r2` and `canonical-2026-07-28-grid` are
both untouched on disk and remain readable.

Scores the pre-registration
`2026-07-30-preregistration-grid-adoption-execution.md`, which was committed and
pushed as `e352045` before the run started.

**Why:** The code fix has been the default since 2026-07-28 while the canonical
artifact still predated it, so the published state and the code state disagreed.
This run closes that gap with an artifact produced BY the adopted code rather
than alongside it.

**Evidence:**

| Prediction | Verdict | Measured |
| --- | --- | --- |
| P1 8 main facets bit-identical to r2 | **PASS** | combined hash `e1df986e...eea64824`, equal to the pre-registered prior |
| P2 deliverable stays 3,559.3 ft^2 over 8 | **PASS** | 3559.3, 8 rows, rows sum to 3559.3 |
| P3 coverage reproduces 94.25 pct | **PASS** | 94.25 pct, explained 272.618, testable 289.237 cu^2 |
| P4 phase spread <= 0.18 points | **PASS** | 0.1800 |
| P5 recovery stays 21 and out of the total | **PASS** | n_recovered 21, total unchanged |

Five independent assertions also passed (S0 anti-null that the scorer is not
reading the reference artifact; S1 same source cloud; S2 the run's own in-run
hash check; S3 neither frozen state overwritten; S4 single ownership).
`reports/big_house/grid-adoption-score-2026-07-30.json`.

**The strongest single result is one nothing predicted in this form: all 29
facets, not just the 8 main ones, are BIT-IDENTICAL to `canonical-2026-07-28-grid`**,
and every coverage and footprint value is equal. Two runs, two days apart, in
separate processes, on the same cloud, produced the same answer to the last bit.
That is a determinism result for the whole pipeline including recovery, which
had previously only been shown for a single grid point within one session.

The phase sweep re-ran cleanly and reproduced the 2026-07-28 decomposition
exactly: pitch fix alone **+5.93** points, origin fix alone **+1.11**, combined
**+5.87** (88.40 -> 94.27). Its anti-null passed: the SUPERSEDED configuration
still reproduces the committed canonical numbers exactly (88.40 pct, 299.654
cu^2), so "supersede, never overwrite" remains a checkable property rather than
a slogan.

**P4 passed exactly at its threshold, 0.1800 against a `<= 0.18` line.** Stated
plainly because a prediction that lands on its boundary is weaker evidence than
one that clears it comfortably, and rounding it away would hide that.

**Rejected:** re-using the approved name `canonical-2026-07-28-grid` was
rejected because those files were already committed at `0bc8bf8`; writing to
that stamp would have overwritten a frozen artifact. Promoting the existing
2026-07-28 artifact without a re-run was rejected because it would have made P3
a file lookup that could only pass. Both alternatives and the reasoning are in
the pre-registration.

**Cost if wrong:** low and recoverable. Both superseded states remain on disk
and both remain recomputable, so reverting the canonical pointer is a one-line
change and no measurement is lost.

**Two things this run added to the code, neither of them a parameter change:**

1. **A shared-lattice assertion in `coverage_masks`** (`roofkit/coverage.py`).
   Three checks: `exact_pitch` must be on, the origin must equal
   `floor(min/cell)*cell` from one shared global min, and, the part that carries
   the weight, **`Hexp <= Hall` in every cell**. The first two are read off the
   ARGUMENTS and would both pass if the rasters were misaligned for an
   unanticipated reason; the third is a property of the DATA, since explained
   points are a subset of all points. Standing rule R4.

2. **An opt-in main-facet hash assertion in `canonical_state.py`**
   (`--assert-main-hashes STAMP`), which runs BEFORE anything is written, so a
   run that disturbed the frozen facets leaves no artifact behind to be mistaken
   for a good one. It hashes the sorted index array plus the plane and centroid
   hex. Pitch and area are deliberately excluded because they are FUNCTIONS of
   those, so hashing them would add no information while creating a way to fail
   for a reason unrelated to facet identity.

**A design constraint discovered while adding the first one, worth recording
because it nearly went the wrong way.** The lattice assertion was initially
unconditional, which immediately broke the four probes that deliberately run the
OLD configuration to recompute superseded numbers, one of them the anti-null
that must show the old path still reproduces 82.29. An unconditional guard would
have converted recomputability from a provable property into an impossible one.
The guard is therefore opt-out via an explicit `allow_superseded=True` on
exactly those callers, and nowhere else. **Measured while testing it: under the
superseded configuration `Hexp > Hall` in 707,650 cells on big_house.** That is
the 2026-07-28 grid defect counted directly for the first time, rather than
inferred from coverage moving. Nothing is adopted from it; it is a consequence
of a finding already adopted.

**Renders.** 29 per-facet PNGs plus an overview were rendered from the new state
into `reports/big_house/review/2026-07-30-grid-adopted/`. These are the BASELINE
for the post-ultra side-by-side comparison and had to exist before ultra runs.
`review_render.py` gained a `--canonical` argument (argparse glue, defaulting to
the previous constant so every existing invocation is unchanged).

**Carried forward, NOT fixed by this pass, and required on any claim that uses
them:**

- **Footprint residue is not fixed.** Filled footprint spread **4.40 cu^2**,
  eroded **6.20 cu^2**, from `min_pts=2` discretisation rather than from the
  grid. Raw footprint is stable at 0.121 cu^2.
- **Capture on the fixed grid:** density-testable **82.72 pct** (289.237 /
  349.640 cu^2), one-point cells **227,964**, p10 points per occupied cell
  **1.0**. Capture quality is a property of the flight and no fix here touches
  it.
- **The 1.83 deg pitch bias remains ACCEPTED, UNTESTED**, a known limit under
  3e. **No pitch correction was applied to any facet anywhere in this pass**,
  and the caveat travels attached to any pitch number, never in an appendix.

**Recorded, gating nothing:** bungalow will be reprocessed at ultra, and the
plan-view render gate before ultra is skipped by decision. Both stated by
Emmett on 2026-07-30 and logged before the fact.

**Attribution.** The task, the five predictions, the stamp choice, the render
requirement and the P1/P5 rewrites are Emmett's. The two assertions, the
`allow_superseded` design, the 707,650-cell measurement and the all-29-facet
determinism comparison are mine.
