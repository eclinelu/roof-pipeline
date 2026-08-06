### 2026-08-05: ROOT CAUSE: the planarity covariance is accumulated on RAW UTM coordinates, and the negative-diagonal symptom is not the scope of the damage

**Decision:** The cause of the planarity score defect is named: the per-point
covariance is accumulated as `E[ab] - E[a]E[b]` on raw, uncentred UTM
coordinates, which destroys the result to catastrophic cancellation. Centring
each neighbourhood on its own centroid before accumulating resolves it. This
entry records the DISCOVERY and its scope only. It does not fix anything, does
not change the production path, and does not decide what to do about it; see
`2026-08-05-fix-the-covariance-before-bungalow-and-rederive-score-max.md` for
the response.

This REFINES the mechanism recorded in
`2026-08-05-planarity-score-leaves-its-range-and-depends-on-enumeration-order.md`.
That entry's measurements stand unchanged. Its attribution of the negative
smallest eigenvalue to "eigvalsh on a numerically rank-deficient covariance" was
incomplete: the matrix handed to `eigvalsh` was not a covariance at all.

**Why:** The cloud is georeferenced UTM, centred near (553485.9, 4543297.7).
Open3D's per-point estimator accumulates nine cumulants over each neighbourhood
and then forms `cov(0,0) = E[x*x] - E[x]*E[x]`. On raw UTM the two terms are each
about 3.06e11 in x and about 2.06e13 in y, and their difference is the variance
being recovered, of order 1e-4. That is roughly 17.3 digits of cancellation
against float64's ~16, so the answer is not degraded, it is gone.

Two things confirm the mechanism rather than merely being consistent with it.
First, the failure has the right fingerprint: the corrupted matrix entries land
on exact dyadic fractions such as -1/128 and -1/8192, which are the ULP of
numbers of that magnitude, instead of on smooth small values. Second, 8,623,218
points carry a NEGATIVE variance on the covariance diagonal and 7,198,421 a
negative trace, both of which are impossible for a real covariance and neither of
which any eigenvalue routine can cause, since they are properties of the input
matrix.

**The scope finding, which matters more than the mechanism.** The natural
assumption is that the affected points are the ones showing the visible symptom,
the negative diagonal. That assumption is wrong, and the correct diagnostic is the
SCORE, not the sign of a diagonal entry. Centring resolved all 8,623,218 flagged
points completely, with zero left broken. But in the same run, 31,322 of 50,000
points that were NEVER flagged also changed materially, median absolute score
deviation 0.125 on a scale whose entire valid range is 0 to 1/3. A non-negative
diagonal is a far weaker condition than a correct covariance: cancellation
corrupts the matrix whether or not it happens to leave a negative sign behind.

Reasoning not stated by Emmett; this is the measured case.

**Rejected:**

- **That the negative diagonal delimits the problem.** This was the working
  assumption when the flag set was first measured, and it was carried into the
  design of the centring probe, whose control group was drawn from unflagged
  points precisely because they were believed healthy. The control group then
  failed to behave as a control, which is what overturned it. Confirmed at
  production scale by
  `2026-08-05-corrected-covariance-flips-a-majority-of-keep-decisions.md`: the
  flip rate is HIGHER among previously-unflagged points, 62.44 pct, than among
  flagged ones, 40.53 pct. The symptom was not merely a weak indicator of which
  points were affected, it was anti-correlated with it.
- **That clamping the negative eigenvalue is the fix.** Rejected on measurement,
  not on taste: the clamp's effect is entirely a property of the convention
  chosen for it, giving 6,694,195 flips when the total is rebuilt from clamped
  eigenvalues and exactly 0 when the original total is kept. A fix whose result
  depends on an arbitrary choice inside the fix is not addressing the cause. The
  clamp operates on the eigenvalue, downstream of where the precision was lost.
- **That the centred computation might be the wrong one.** Tested rather than
  assumed, because the control-group result was ambiguous on its face: either
  centring was wrong, or the unflagged points were never healthy. Adjudicated
  with numpy's covariance, which centres internally and shares no code with
  either path.

**Evidence:**

| Probe | Commit | Finding |
|---|---|---|
| `scripts/probe_planarity_clamp_check.py` | `e5df8e9` | 8,623,218 negative diagonal, 7,198,421 negative trace; clamp effect convention-dependent, 6,694,195 flips vs 0 |
| `scripts/probe_planarity_centering_check.py` | `ad85d65` | all 8,623,218 flagged points fully resolved by centring, 0 still broken; 31,322 of 50,000 unflagged control points also flip |
| `scripts/probe_planarity_score_max_check.py` | `16ff751` | scope confirmed at full scale, flip rate 62.44 pct unflagged vs 40.53 pct flagged |

Third-method cross-validation, from `ad85d65`: numpy's covariance agrees with the
centred computation to **5.421e-20** and disagrees with production by a median of
**3.855e-03** and a maximum of **2.340e-02**, against a production matrix scale of
**2.344e-02**. The disagreement with production is the same order as the values
themselves.

Anti-nulls, all independent of the results above and all passing: the
reconstructed production score equals `planarity_scores()` bit for bit over all
16,885,409 points; the recomputed flag set matches the prior probe exactly on both
counts; and the re-gathered neighbourhoods reproduce Open3D's own covariance
matrices bit for bit (max deviation 0.000e+00), so the corrected scores are
computed on production's neighbourhoods and production's estimator, mechanism 2's
arbitrary-30 behaviour included and deliberately uncorrected.

One honest limit on the evidence: 7,066 of the flagged points still carry a tiny
negative smallest eigenvalue after centring, despite a valid diagonal and a valid
trace. That is 0.08 pct of the flagged set. No cause was tested and none is
offered here.

**Cost if wrong:** Low, and that is a deliberate property of having stopped
before changing anything. Production has NOT been modified: `roofkit/` is
untouched, no production path is wired to the centred computation, `score_max`,
`radius_mult` and `max_nn` are unchanged, and `roof.npy`, the canonical artifacts
and the frozen 3,559.3 ft^2 figure were never read or rewritten by any of the
three probes. If centring turns out not to be the correct fix, what is lost is
three diagnostic scripts and their reports, all of which remain valid as
measurements of what the current code does. The claim that would have to fail is
narrow and independently checkable: that a covariance computed with the centroid
removed first is the correct one, which numpy already agrees with to 5.4e-20.
