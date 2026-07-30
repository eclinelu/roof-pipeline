### 2026-07-30: PRE-REGISTRATION: executing the approved grid adoption, and the five values that decide whether it worked

**Kind:** PRE-REGISTRATION. Written and pushed BEFORE the run it predicts.

**Decision:** Execute the grid adoption approved in
`2026-07-28-adopt-exact-pitch-and-declared-lattice-origin.md` by RE-RUNNING
`scripts/canonical_state.py` on big_house under the adopted defaults
(`exact_pitch=True`, `anchor="lattice"`), writing a new artifact stamped
`2026-07-30-grid-adopted`, and rendering the per-facet review images from it.
Adoption only: no parameter, threshold or window is changed in this pass.
`canonical-2026-07-26-r2` is not written to, and neither is
`canonical-2026-07-28-grid`.

**Why:** The code fix has been the default since 2026-07-28, but the CANONICAL
ARTIFACT still predates it, so the published state and the code state disagree.
Closing that gap needs an artifact produced BY the adopted code, not a promotion
of one produced alongside it.

The stamp is `2026-07-30-grid-adopted` rather than the approved name
`canonical-2026-07-28-grid` because that name is already taken: those files
exist and were committed at `0bc8bf8` on 2026-07-28. Re-using the stamp would
overwrite a committed frozen artifact, which contradicts the rule stored inside
the artifact itself ("supersede, never overwrite. A corrected file implies the
old numbers were an arithmetic mistake; they were not"). Emmett chose the new
stamp when the collision was reported.

This also BUYS something rather than merely avoiding harm. With a separate
stamp, P3 is a genuine reproduction: the 2026-07-28 artifact becomes an
independent prior that today's run either reproduces or does not. Had the run
written to the same path, P3 would have compared the run to itself and could
only have passed. Reasoning mine, not stated by Emmett; he chose the option and
the framing of P3 as "a real reproduction against the 2026-07-28 artifact" is
his.

**Rejected:**

| Option | Why it lost |
| --- | --- |
| Overwrite `canonical-2026-07-28-grid` | Rewrites a committed frozen artifact. Violates supersede-never-overwrite and the task's own instruction not to edit a frozen artifact. |
| Promote the existing 2026-07-28 artifact, no re-run | Zero overwrite risk and fastest, but nothing is executed and P3 degrades from a reproduction to a file lookup that can only pass. |
| New subdirectory `canonical-2026-07-28-grid/` | Preserves the approved name but leaves two different objects sharing one name, and needs the writer's output path changed. |

**Evidence, the prior values. Every number below is read from a file committed
BEFORE this entry, and is what the run will be scored against.**

The 8 MAIN facets of `canonical-2026-07-26-r2`. Hash is
`sha256(sorted int64 index array || plane_abcd_hex || centroid_hex)`:

| Facet | n_points | pitch_deg | hash |
| --- | --- | --- | --- |
| 0 | 1,538,098 | 21.1883 | `fd8f7154e3bdd07010e5d9c288399a711221602d63325d0225ffb1bbe7fde781` |
| 1 | 1,154,335 | 33.0669 | `b4748236d8e74982d4080338c546bc8594fc189f3bc39fa8bc49181855de24e9` |
| 2 | 693,991 | 22.7224 | `1d049ef0d2e5d4731f5ab4733902a8ebc71e609747295f7d0e3b32635dad9e7f` |
| 3 | 850,268 | 34.0059 | `4a61c6e75f792132333e069f1248f17ec7cc83ec9f3819b33dc63879a1457868` |
| 4 | 744,303 | 20.9901 | `ae5544f618df79219b94e170c3efa2abbf9648f7b3a69a5cc611089adf05e8b2` |
| 5 | 669,484 | 21.3571 | `6c2d8f96201f023618d7a44a03034dba44bb0c2e6e438e6229bd6c708ac5d28e` |
| 6 | 403,109 | 33.7566 | `c1d38070a3008dc7b0a1af15632d211ec1e6325fbb03176729a29f6c7cc13d51` |
| 7 | 297,583 | 33.5153 | `b03c8da052c6b819d50784e1d895ba99290e7f53bb2563ed9b7f006be8c90105` |

Combined 8-main hash:
`e1df986ea6ac840be520663b398e9d6edd8d392a8dcc8a27dcd06a60eea64824`

Already established and re-verified while writing this entry: all 8 are ALREADY
bit-identical between `canonical-2026-07-26-r2` and `canonical-2026-07-28-grid`.

Coverage and footprint, both states:

| Quantity | `2026-07-26-r2` | `2026-07-28-grid` |
| --- | --- | --- |
| facet coverage | 88.40 pct (256.574 / 290.256) | **94.25 pct (272.618 / 289.237)** |
| density-testable | 82.29 pct | **82.72 pct** |
| footprint raw / filled / eroded cu^2 | 299.654 / 362.105 / 352.707 | **299.440 / 359.843 / 349.640** |
| counts | 8 main + 21 recovered = 29, 17 blobs | 8 + 21 = 29, 17 blobs |

Phase spread under the ADOPTED configuration, from
`grid-adoption-2026-07-28.json`, key `new_stability_claim/spread`:
facet coverage min **94.27**, max **94.45**, **spread 0.18** points.

Note the 94.25 / 94.27 gap: the adopted artifact reads slightly BELOW the phase
sweep's own minimum. This is already accounted for and is not a new anomaly.
All 8 main facets are bit-identical; only the recovered facets moved, because
`recover_facets` selects blob candidates BY CELL, so moving the grid moved the
candidate point sets.

Published deliverable, `comparison-2026-07-18-scored-2026-07-18.json`:
`total_area_ft2` = **3559.3**, over **8** facets, whose stored `area_ft2` values
(487.4, 776.2, 349.7, 602.9, 326.5, 211.7, 383.1, 421.8) sum to exactly 3559.3.
Its `pipeline_deg` values (21.188, 33.067, 22.722, ...) match the r2 main
facets, so these are the same 8 facets.

Frozen configuration, unchanged by this pass: `probability=1.0`,
`min_pitch_deg=5.0`, `max_pitch_deg=60.0`, `min_points_hard=1933`,
`min_area_hard_cu2=0x1.99a1fedfa5076p-4`, `alpha_mult=4.0`, `band_mult=3.0`,
`trim_mult=3.0`, `coverage_cell_mult=2.5`, `min_blob_area_cu2=0.15`,
`spacing_cu=0x1.5488f976ee19ep-8`, `cell_cu=0x1.a9ab37d4a9a06p-7`,
`quality_bar=0x1.7957f5ed10c3ep+1`, source cloud sha256
`1e04669c7f9b079d16dc4bf6efbd0a6bebd0c8f7b5782c0f0977e680d1b27335`.

**Literal values, so a third party could execute this without a numeric choice.**
Command: `.venv/Scripts/python.exe -u scripts/canonical_state.py
C:/odm/datasets/big_house --stamp 2026-07-30-grid-adopted`. No `--min-points`
override. Outputs `reports/big_house/canonical-2026-07-30-grid-adopted.json`
and `.npz`. Renders: `scripts/review_render.py` against the new stamp, writing
`reports/big_house/review/2026-07-30-grid-adopted/facet-NN.png` (one per facet)
plus `overview.png`. The renderer currently pins `CANONICAL_STAMP` as a module
constant; it gets a `--canonical` argument defaulting to the present value, which
is argparse glue and changes no analysis.

---

## PREDICTIONS

**P1. The 8 main facets are unchanged.** Per-facet index sets and plane
coefficients must equal the r2 values at FULL STORED PRECISION: identical sorted
int64 index arrays, identical `plane_abcd_hex`, identical `centroid_hex`, hence
identical per-facet hashes and the combined hash above. Any difference is FAIL.

Slope areas are cross-checked at 0.1 ft^2 against the 8 stored `area_ft2` values
from the scored 2026-07-18 comparison. **This cross-check is a check on the AREA
FUNCTION, not independent confirmation of bit-identity** (Emmett): identical
indices and identical coefficients necessarily give identical areas, so the area
comparison cannot add evidence about facet identity. It can only detect drift in
the area code or the scale factor since 2026-07-18. Pre-declared reading, so it
cannot be rationalised afterwards: if the hashes match but the areas move, that
is area-function drift and is recorded as such, and P1 still passes on its own
terms; if the hashes move, P1 fails regardless of what the areas do.

**P2. The published deliverable is untouched.** `total_area_ft2` stays 3559.3
over 8 main facets, and `comparison-2026-07-18-scored-2026-07-18.json` is
unmodified. Any change is FAIL.

**P3. Coverage reproduces 94.25 pct.** The new run's
`coverage.facet_coverage.pct` must equal 94.25, with explained 272.618 and
testable 289.237 cu^2. A different value means the fix executed today is not
the fix measured on 2026-07-28. FAIL.

**P4. Phase spread stays at or below 0.18 points.** Sweeping the grid origin
phase under the adopted configuration must give a facet-coverage spread
<= 0.18. Larger means the lattice origin is not global. FAIL.

**P5. Recovery is unchanged and stays out of the total.** `n_recovered` == 21
AND `total_area_ft2` == 3559.3 over 8 facets. Any total that absorbs the
recovered facets is FAIL.

Recorded for honesty: the figure **404.9 ft^2**, named in the task as the
recovered-facet area, **does not appear anywhere in this repo**. No area total
has ever been computed from the 29-facet state. It is carried here as an
UNVERIFIED figure and is not what P5 is scored on.

---

## POWER CHECK

Required field since `2026-07-29-power-check-required-in-preregistrations.md`.
For each prediction: can it actually separate its hypotheses?

| Prediction | Effect vs resolution | Independent samples | Can it fail? |
| --- | --- | --- | --- |
| P1 | sha256 equality. Resolution is exact; any single differing bit or ULP flips it | 8 facets, each hashed separately, plus a combined hash | YES. The recovered facets DID move between these two states, so the pipeline demonstrably can move facets across a grid change. Main facets staying fixed is a real outcome, not a foregone one. |
| P2 | file-level equality plus an exact decimal | 1 file, 8 rows | YES, trivially, if anything writes to it |
| P3 | 94.25 against a reporting resolution of 0.01 pct. The pre-fix value is 88.40, a 5.85-point gap, 585x the resolution | 1 run, but compared to an independently produced prior | YES. Three distinct values are live in the record (94.25 adopted, 94.27 sweep minimum, 94.33 counterfactual probe), so landing on 94.25 specifically is discriminating rather than automatic. |
| P4 | 0.18 threshold against a pre-fix spread of 5.20 points, 29x larger | the sweep's grid of origin phases | YES. This is the test that failed loudly before the fix. |
| P5 | integer count and an exact decimal | 21 facets, 1 total | YES |

**The honest weakness, stated in advance.** P1, P2 and P5 are near-certain to
pass, because the run is deterministic (`probability=1.0`) and this pass changes
no parameter. They are REGRESSION GUARDS, not discoveries: their value is that
they would fire loudly if adoption silently disturbed the frozen main facets or
the published total, which is exactly the failure mode worth insuring against.
They are not evidence FOR the fix.

**P3 and P4 carry the actual information in this pass.** P3 asks whether the
adopted code path, run fresh two days later, lands on the number the adoption
decision was made on. P4 asks whether the stability claim that justified the
adoption survives re-measurement. Either can genuinely go the other way.

**Cost if wrong:**

- **P1 fails:** the most serious outcome. It would mean adoption disturbed the
  frozen main facets, so the 2026-07-18 pitch validation was computed on a
  membership the pipeline no longer produces. The run STOPS and nothing is
  adopted. Recovery is cheap in compute and expensive in trust.
- **P3 fails:** the 94.25 in the adoption decision was not reproducible, and the
  decision was made on a number nobody can regenerate. Adoption is withdrawn
  pending an explanation; the published 88.40 pct stands.
- **P4 fails:** the lattice origin is not global, meaning the fix is incomplete
  and coverage is still phase-dependent. Coverage cannot be used as a
  cross-pass detector, and R5 stands unsatisfied.
- **P2 or P5 fails:** something wrote where it should not have. Cheap to find,
  and it invalidates the pass rather than the fix.

---

## CARRIED FORWARD, not fixed by this pass

These are stated so the new artifact cannot be read as cleaner than it is.

- **Footprint residue is NOT fixed.** Genuinely phase-sensitive even after the
  fix: filled footprint spread **4.40 cu^2**, eroded footprint spread
  **6.20 cu^2**. This is real discretisation sensitivity from `min_pts=2`, not a
  grid artifact, and it must be carried on ANY footprint claim. Raw footprint is
  stable (spread 0.121 cu^2).
- **Capture metrics on the fixed grid:** density-testable **82.72 pct**
  (289.237 / 349.640 cu^2), one-point cells **227,964**, p10 points per occupied
  cell **1.0**. Capture quality is a property of the flight, not of this fix.
- **The 1.83 deg pitch bias is ACCEPTED, UNTESTED** and is a known limit under
  3e. **No correction is applied to any pitch on any facet anywhere in this
  pass**, and the caveat travels attached to any pitch number, never in an
  appendix.

## RECORDED, gating nothing in this pass

Both stated by Emmett on 2026-07-30, logged here so the sequence is on the
record before the fact rather than reconstructed afterwards:

- **bungalow will be reprocessed at ultra.** bungalow is a HELD-OUT VALIDATION
  site with one scored attempt, so the reprocessing decision and its timing
  belong in the record before any bungalow number exists.
- **The plan-view render gate before ultra is SKIPPED by decision.** Skipped
  deliberately, not overlooked.
- The per-facet PNGs this run produces are the BASELINE for the post-ultra
  side-by-side comparison. That is why rendering is part of this pass rather
  than deferred: the baseline has to exist before ultra runs, or there is
  nothing to compare against.

**Attribution.** The task, the five predictions and their directions, the stamp
choice, the requirement to render, the P1 and P5 rewrites, and the ruling that
the area cross-check tests the area function rather than confirming bit-identity
are all Emmett's. The artifact-name collision, the missing per-facet area field,
the absence of 404.9 from the repo, the power-check arithmetic and the
regression-guard-versus-discovery split are mine.
