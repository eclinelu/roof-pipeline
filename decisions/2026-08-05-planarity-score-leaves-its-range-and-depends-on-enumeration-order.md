### 2026-08-05: OPEN DEFECT, and a STOP: the planarity score leaves its documented range on 41 pct of the input and depends on neighbour enumeration order. The ultra analysis pass is HELD

**Decision:** The ultra analysis pass is STOPPED before it produces any artifact,
and nothing about the planarity filter is changed. Two defects in the EXISTING
production stage-4 filter are recorded and measured instead. Enabling work that
does not depend on the outcome (a streaming crop-on-read in `roofkit/io.py`) is
kept and committed; everything downstream of the filter is held pending Emmett's
call.

**Why:** The task was to build the third visual pass, `grid-adopted-vs-ultra`.
Reaching it needed the stage 0-4 chain to run on a 90.2M-point cloud on a machine
with 6.78 GiB free, which needed the planarity filter run in spatial tiles rather
than one call. Tiling is exactly equivalent ON PAPER: the score is a local
operator with finite support, and each tile carried a halo of exactly the search
radius, so every core point sees the neighbourhood it would have seen in the whole
cloud. The equivalence check against the whole-cloud path FAILED.

Following that failure into `planarity_scores` found two things, and neither is
about the tiling.

1. **The score leaves its documented range, and the out-of-range points are the
   ones being KEPT.** The docstring says the score runs "0 (perfect plane) to 1/3
   (isotropic confetti)". On the production input the observed range is
   **-3.355e+07 to 0.3333**. 6,965,577 of 16,885,409 points (**41.25 pct**) score
   outside the documented range, all of them negative. Because the filter is
   `score <= score_max`, a negative score passes unconditionally: **73.55 pct of
   the points the filter KEEPS were admitted on a score the docstring says cannot
   occur.** The mechanism is that `eigvalsh` on a numerically rank-deficient 3x3
   covariance returns a small NEGATIVE smallest eigenvalue, and the existing guard
   only rejects `total <= 1e-12`, which does not catch a negative numerator over a
   small positive denominator. The filter's admission of these points is not a
   graded judgement about flatness; it is an arithmetic accident that happens to
   point the same way.

2. **The score depends on the order the points are enumerated in.**
   `estimate_covariances` is called with `KDTreeSearchParamHybrid(radius, max_nn)`
   at `max_nn=30`, while the **median neighbourhood inside the radius holds 59
   points**. The covariance is therefore built from an arbitrary 30 of roughly 59,
   chosen by KD-tree traversal order. Reordering the points -- which is all tiling
   does -- selects a different 30 and moves the score. On a 2M-point subset this
   produced **598 keep/discard flips, 101 of them with both scores inside the
   documented range**, so this is not confined to the degenerate regime. This is
   the R5 shape (`2026-07-28-raster-phase-is-an-unswept-parameter.md`) in a new
   disguise: an implementation detail nobody chose is deciding the answer.

**Why this stops the ultra pass specifically, rather than being a general defect
to note and route around.** Both effects are driven by how many candidate
neighbours sit inside the search radius, and that is a function of POINT DENSITY
-- the single variable an ultra-against-medium pass exists to isolate. A denser
cloud puts more candidates in the radius, so a smaller and more arbitrary fraction
of each neighbourhood is sampled, and a flatter sampled subset, which is what
drives the covariance rank-deficient in the first place. A facet diff across the
two clouds would therefore report this defect's response to density MIXED WITH the
roof's, with no way to separate them afterwards. The pass would have produced a
complete, well-formed record whose headline difference was substantially an
artifact. That is the same failure the grid artifact turned out to be
(`2026-07-28-published-coverage-is-a-grid-artifact.md`), caught before the run
this time rather than after.

Reasoning not stated by Emmett; this is the measured case, and the decision on
what to do about the filter is his.

**Rejected:**

- **Accept the tiling anyway, 598 flips out of 2M is 0.03 pct.** Rejected because
  size is not the question. Standing practice here is that a failed check is
  reported, never tolerance-widened, and the flips would have made roof membership
  depend on a memory parameter (`max_block`).
- **Assume the new tiling code has the boundary bug, since it is the new code.**
  Rejected on evidence: the halo is exactly the operator's support, and 101 of the
  flips occur with both scores well inside the valid range, which a halo error
  could not produce. The rewrite is an order-dependence DETECTOR, and its
  disagreements are data about the original.
- **Fix the filter now** (clamp negative eigenvalues to zero, or raise `max_nn`
  above the neighbourhood size). Rejected because it changes the production
  configuration and therefore every artifact, including the frozen 3,559.3 ft^2
  and the pitch validation. Same standing treatment as the `min_pitch` defect:
  measured, reported, not changed, because that is Emmett's call.
- **Voxel-downsample ultra to fit in memory.** Rejected because it destroys the
  one property the ultra cloud was reconstructed for.
- **Run the pass on the medium cloud only.** Rejected: that is not the requested
  comparison and there is no new artifact to grade.

**Evidence:** `reports/big_house/planarity-score-range-2026-08-05.json`, written by
`scripts/probe_planarity_score_range.py`.

The probe carries the R4 assertion, built from something known INDEPENDENTLY of
anything it reports and checked BEFORE the report is written: the stage 0-4 chain
it drives must reproduce the committed `roof.npy` **bit for bit**. It does, at
9,293,239 points, so these numbers describe the real production path and not a
lookalike. That check also establishes, as a side effect, that stage 0-4 is fully
reproducible today.

Measured, all on `big_house` medium at `radius_mult=5.0`, `score_max=0.05`,
`max_nn=30`, spacing 0.004472, radius 0.022361:

| Quantity | Value |
|---|---|
| planarity input | 16,885,409 |
| observed score range | -3.355e+07 .. 0.3333 |
| documented score range | 0 .. 0.3333 |
| scores outside documented range | 6,965,577 (41.25 pct) |
| kept by the filter | 9,470,646 |
| of those, admitted out of range | 73.55 pct |
| median neighbours within radius | 59, against a `max_nn` cap of 30 |
| keep flips from reordering alone (2M subset, 8 tiles) | 598 |
| of those, with both scores in range | 101 |

**Cost if wrong:** If the negative scores are in fact harmless -- that is, if every
point admitted on one is genuinely planar and would have been admitted anyway
under a corrected score -- then this stop cost one session and the ultra pass
resumes unchanged. That is the cheap direction and it is checkable: recompute with
the negative eigenvalues clamped and count how many admissions actually change.

If instead the defect is real and the pass had been run, the cost is a published
medium-vs-ultra facet comparison whose differences are partly numerical artifact,
presented as evidence about reconstruction density. Given that `pc_quality=ultra`
is already the intended default for both held-out validation sites
(`2026-07-30-ultra-becomes-the-odm-default.md`), a wrong reading here propagates
into bungalow and cove_house, which get exactly ONE scored attempt each. That is
the expensive direction and it is not recoverable.

**Note on scope:** this is the THIRD open defect touching the ultra comparison,
alongside the run-continuity confound
(`2026-08-03-ultra-medium-comparison-is-confounded-by-run-continuity.md`) and the
`--skip-3dmodel` contradiction
(`2026-08-03-skip-3dmodel-rule-contradicts-the-canonical-artifact.md`). The
density comparison now has confounds at the reconstruction stage AND at the
filtering stage.
