### 2026-08-05: SCALE OF THE DEFECT: correcting the covariance flips the keep/discard decision for 51.25 pct of points under the unchanged threshold, and the effect is BROAD rather than concentrated

**Decision:** The uncentred-covariance defect recorded in
`2026-08-05-covariance-accumulated-on-uncentred-utm-coordinates.md` is recorded
as MATERIAL to the production filter's output, not cosmetic. Under the unchanged
`score_max = 0.05`, correcting the covariance changes the keep/discard decision
for 8,653,847 of 16,885,409 points, and the change is spread across the whole
cloud rather than confined to the points that visibly showed the defect. Nothing
is fixed or changed by this entry; it establishes the size of the problem so the
response can be argued from a measured number.

**Why:** "Does the defect fire" and "does the defect change anything" are
different questions, and the first was already answered. This entry answers the
second, because a numerically wrong score can still land on the correct side of a
threshold, and if it always did, the defect would be a documentation problem
rather than a measurement problem.

It does not. The kept count falls from 9,470,646 to 6,129,425, a loss of
3,341,221 points or 35.3 pct. That net figure understates the disturbance,
because the flips run in both directions at once: 5,997,534 points leave the kept
set and 2,656,313 enter it. Roughly one point in eight of the corrected keep set
is material production rejected. The corrected selection is therefore not a
tightened version of the current one, it is a substantially different selection
of the same roof, and any argument that the current filter is "conservative" or
"keeps a superset" is unavailable.

**The part that changes how the defect must be reasoned about.** The flip rate is
HIGHER among points that never showed the symptom, 62.44 pct of the 8,262,191
previously-unflagged points, than among the 8,623,218 flagged ones, 40.53 pct.
This confirms at full production scale what the 50,000-point control group in
`ad85d65` first showed, and it settles the scope question against the intuitive
answer. Any reasoning that treats the flagged count as the size of the problem,
or that expects the damage to sit where the negative diagonals are, is wrong in
the direction that understates it.

For orientation, the corrected score distribution places the existing threshold
between p25 (0.031001) and p50 (0.074057), so under corrected scores the median
point is discarded where production kept it. That is stated as a description of
where the current value falls, not as an argument about where a threshold should
go. No replacement value was searched for, computed, or implied by the probe,
because choosing a threshold needs its own justification and a probe that
surfaced "the value that keeps the artifact stable" would be fitting the
threshold to the answer.

Reasoning not stated by Emmett; this is the measured case.

**Evidence:** `scripts/probe_planarity_score_max_check.py`, commit `16ff751`,
written to `reports/diagnostics/planarity-scoremax-check.json`. All 16,885,409
points, medium cloud, `score_max` 0.05, `radius_mult` 5.0, `max_nn` 30, all read
and unchanged.

| Quantity | Value |
|---|---|
| kept by production | 9,470,646 |
| kept by corrected | 6,129,425 |
| change in kept | -3,341,221 (-35.3 pct) |
| TOTAL FLIPS | 8,653,847 (51.25 pct of input) |
| kept -> discarded | 5,997,534 |
| discarded -> kept | 2,656,313 |
| flips within previously-FLAGGED set | 3,495,070 of 8,623,218 (**40.53 pct**) |
| flips within previously-UNFLAGGED set | 5,158,777 of 8,262,191 (**62.44 pct**) |
| corrected p25 / p50 / p75 | 0.031001 / 0.074057 / 0.128066 |

Two figures inside that total are reported so they can be netted out rather than
silently inflating it: 216,320 points cloud-wide sit on Open3D's identity-matrix
fallback for neighbourhoods too small to define a covariance (k=1, k=2), so their
production score is the degenerate 1/3 for a reason unrelated to centring; and
81,895 corrected scores fall outside the valid 0 to 1/3 range, with the
distribution minimum at -4.19e-16, which is floating-point noise scale. How that
81,895 splits between the two ends was not measured.

The probe's neighbourhood-fidelity anti-null FAILED on its first run and was
correct to. Sampling from all points rather than from the flagged set pulled in
the identity-fallback rows, which are a documented Open3D behaviour rather than a
neighbour-selection difference. They are now excluded from the assertion and
counted in the report; after that correction the rebuild is bit-exact, max
deviation 0.000e+00. The other two anti-nulls passed unchanged: production score
equals `planarity_scores()` bit for bit over all 16,885,409 points, and the flag
set matches the prior probes exactly.

**Cost if wrong:** This finding is what makes the frozen 3,559.3 ft^2 figure
suspect, so disputing it is the same as defending that figure. If the finding is
later overturned, the frozen area and the pitch validation stand as they are and
the response entry built on this one becomes unnecessary work. If it is correct
and were ignored, the consequence is more specific: the roof point set feeding
every downstream stage, plane fit, facet membership, area and pitch, is selected
by a filter whose input is corrupted for a majority of candidate points, which
makes 3,559.3 ft^2 a number produced from the wrong points rather than a number
with a quantified error bar. It is already known that the published per-facet
areas do not recompute today
(`2026-07-30-published-areas-do-not-recompute.md`); this entry does not claim to
explain that, and no attempt was made to connect them.

The measurement is cheap to attack directly, which is the point of recording it
this way: the flip counts come from one script on one committed input, with the
production side asserted bit-identical to `planarity_scores()`, so a challenge
can be settled by re-running it rather than by argument.
