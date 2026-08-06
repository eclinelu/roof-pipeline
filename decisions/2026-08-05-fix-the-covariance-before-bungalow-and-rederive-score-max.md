### 2026-08-05: DECIDED: the covariance computation is corrected BEFORE bungalow's ultra reconstruction, and `score_max` is re-derived independently rather than tuned to preserve the frozen figure

**Decision:** The planarity covariance will be corrected in production code
before bungalow is reconstructed at ultra. `score_max` will then be re-derived on
its own justification, explicitly NOT chosen to reproduce the frozen 3,559.3 ft^2
figure. Nothing is changed by this entry itself: it records the decision, and no
production code, parameter or artifact was touched in the session that made it.

**Why:** Emmett's reasoning, stated 2026-08-05. bungalow and cove_house are
held-out validation sites and each is scored exactly ONCE under
`2026-07-27-development-vs-validation-split.md`, with roger lost, so there are two
held-out sites and one attempt at each. Running bungalow through the current
filter risks spending that single attempt on a materially wrong point selection.
"Materially wrong" is not a worry here, it is the measured result in
`2026-08-05-corrected-covariance-flips-a-majority-of-keep-decisions.md`: 51.25 pct
of points change keep/discard decision under the unchanged threshold. An attempt
spent that way cannot be re-run, so the ordering is forced by the standing rule
rather than by preference.

Emmett's second point is why this defect does not qualify for the treatment the
project has already given another known problem: this is a correctness defect in
the core geometric computation feeding the only validated result, not a bounded
cosmetic artifact. The sawtooth pitch bias
(`2026-07-29-sawtooth-accepted-untested-known-limit.md`) is accepted untested as
a KNOWN LIMIT, but it is bounded at 1.83 deg, it is characterised, and it travels
attached to every pitch number it affects. The covariance defect has none of
those properties: it is unbounded in the sense that the corrupted matrices differ
from the correct ones by the same order as the values themselves, it changes
which points exist in the roof set rather than shifting a reported quantity, and
there is no caveat that can be attached to a number to make it honest when the
inputs to that number were selected wrongly.

On the threshold: `score_max` will be justified independently of whether the
resulting figure matches 3,559.3 ft^2. The value was originally tuned by eye
against scores from the broken computation, across most of the cloud rather than
just the visibly flagged half, so it carries no evidential weight now. Choosing a
new value by whether it reproduces the frozen figure would be fitting the
threshold to a desired answer, which is the failure mode this project has already
recorded for scale-dependent cutoffs, and it would silently convert a frozen
result into a target. The probes were deliberately built not to surface a
candidate value for the same reason.

**Rejected:**

- **Run bungalow first, fix afterwards.** Rejected because the single scored
  attempt is consumed by the run, not by the analysis. Fixing afterwards would
  leave the choice between reporting a validation result known to rest on a
  defective point selection, or re-running a site whose whole evidential value is
  that it was scored once under rules frozen in advance. Neither is available, so
  the fix has to precede the run.
- **Treat it as a known limit, the way the sawtooth pitch bias was treated.**
  Rejected for the reasons in the Why above: the sawtooth is bounded,
  characterised, and expressible as a caveat attached to the affected number,
  while this defect changes which points are in the roof at all and has no
  bounded magnitude. A caveat cannot carry it.
- **Tuning `score_max` to preserve 3,559.3 ft^2**, implicitly rejected by the
  decision above and recorded explicitly so it is not reintroduced later as a
  reasonable-sounding sanity check. The frozen figure is evidence about what the
  pipeline produced on 2026-07-18, not a target the corrected pipeline must hit.

**Evidence:** This decision rests on the two entries written alongside it rather
than on new measurement.
`2026-08-05-covariance-accumulated-on-uncentred-utm-coordinates.md` establishes
the mechanism and that centring resolves it, cross-validated against numpy to
5.421e-20.
`2026-08-05-corrected-covariance-flips-a-majority-of-keep-decisions.md`
establishes that it changes 8,653,847 of 16,885,409 keep/discard decisions and
that the effect is broader among previously-unflagged points, 62.44 pct, than
among flagged ones, 40.53 pct.

The ordering constraint itself comes from
`2026-07-27-development-vs-validation-split.md`, not from this session.

**Cost if wrong:** Three distinct failure modes, worth separating because they
have different recoveries.

If centring does not actually resolve the defect, the cost is contained: the
change is made in production code where it can be reverted, and it is checkable
before anything downstream depends on it, since the same numpy cross-validation
and the same bit-exact anti-nulls used by the probes apply to the production
implementation. The 7,066 points that still carry a tiny negative smallest
eigenvalue after centring are the known open edge of that claim.

If `score_max` cannot be independently justified, the project is left without a
defensible planarity threshold at all, which blocks the held-out sites rather
than merely delaying them. That is the expensive outcome, and it is the direct
cost of refusing to tune to the frozen figure. It is accepted deliberately: a
threshold that cannot be justified except by the answer it produces would not
survive being defended, which is the standard this project holds itself to.

If the corrected pipeline produces an area materially different from 3,559.3
ft^2, that is not a failure of this decision but its expected consequence, and
the frozen figure stays on the record as what the pipeline produced on
2026-07-18 rather than being retconned. big_house is the development site and no
accuracy claim ever came from it, which is what makes recomputing its area
affordable.
