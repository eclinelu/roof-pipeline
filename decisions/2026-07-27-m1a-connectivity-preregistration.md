### 2026-07-27: PRE-REGISTRATION for pass 1 fix, M1a: facet membership gets a connectivity constraint

**Status: PRE-REGISTRATION. Committed BEFORE the fix is written or run.** No code
has been changed and no artifact regenerated. Every prediction below is recorded
with its direction so it can be SCORED, not reinterpreted, afterwards.

---

**THE JUSTIFICATION, STATED WITHOUT REFERENCE TO THE REVIEW.**

A PLANE IS UNBOUNDED. A FACET IS A BOUNDED PIECE OF ROOF. Membership computed as
"distance to a plane" conflates the two.

`recon_common.discover_facets` selects a facet's points as
`(owner == k) & (dist <= band)`, where `dist` comes from `assign_to_planes`,
which measures perpendicular distance to an INFINITE plane. There is no term in
that expression that refers to WHERE the point is. A point on the far side of the
building joins the facet if the infinite extension of that facet's plane passes
within the inlier band of it. On a roof built from repeated slopes at the same
pitch, the infinite extension of one facet passes through several others BY
CONSTRUCTION, so this is not a coincidence; it is what the geometry of a house
guarantees.

This argument stands on the definition of the operation and would be true if
nobody had ever looked at a render. It PREDICTS the defect rather than describing
it.

Nothing downstream catches it. `assert_single_ownership` verifies that no point
is owned by TWO facets, which a remote sliver satisfies perfectly. The project's
contiguity rule (`2026-07-18-contiguity-rule-run2.md`) is applied to the
scale-span extent, not to facet membership.

**THE FIX IN ONE SENTENCE:** after membership is selected and before the plane is
refitted, a facet keeps only the points connected to its main body.

---

**WHERE THE FILTER RUNS, STATED PRECISELY BECAUSE IT CHANGES WHAT THE CONTROL
MEANS.** The filter is applied inside `discover_facets`, which produces the 8
MAIN facets. It is NOT applied inside `recover_facets` / `find_roof_planes`,
which produce the 21 recovered facets. That is deliberate: M1a is measured on the
main facets, M1b is explicitly out of scope, and one mechanism per pass.

Consequence: recovered facets are untouched DIRECTLY, but they are NOT insulated.
Main planes move, so `dist` moves, so the residual moves, so the blobs move, so
recovery re-runs on different input. The indirect path is real and is not bounded
in advance.

---

**A CORRECTION TO THIS PRE-REGISTRATION'S OWN PREMISE, MADE BEFORE COMMITTING.**

Emmett corrected P5 on the grounds that strays removed from facets become
unassigned and therefore enter the residual, which is the pool recovery draws
from. The correction to P5's reasoning is right that the residual is where to
look. **But the premise underneath it is wrong, and it was wrong in the original
P6 as well, so it is corrected here rather than carried into a scored
prediction.**

Removing a point from a facet's MEMBERSHIP does not make it unassigned.
`coverage_masks` recomputes assignment from scratch:

    owner, dist = assign_to_planes(roof, facets, max_dist=inf)
    explained = (dist <= band)

and `_point_plane_dist` measures distance to `facet["normal"]` through
`facet["points"].mean(axis=0)`. It reads the PLANE, not the membership list. A
stray dropped from facet 0's point set still lies within `band` of facet 0's
plane and is still counted as explained.

**So the residual grows only by the strays that the REFITTED plane no longer
covers.** That couples P5, P6 and P8 directly to P7: the pool grows only insofar
as the plane tilts, and how far it tilts is exactly what P7 measures. The
sensitivity is calculable and is the reason the coupling is not negligible: a
stray 50 ft out leaves a 2.66 inch band under a tilt of about 0.25 degrees.

Emmett's standard, applied to Emmett's own correction: a prediction resting on a
false premise scores as luck even when the direction is right.

---

**PRE-REGISTERED PREDICTIONS. Direction stated. Scored after the run.**

**P1, LINES.** Main-facet line errors largely resolve; dormer lines L11-L16 stay
`correct`. The partition is already in the record: all 6 "does not exist" and all
5 "short" lines are between main facets, all 6 "correct" are between dormer
facets, and that is exactly the M1a partition. **If dormer lines break, the fix
has a side effect** and that is a failure, not a wash.

**P2, THE CONTROL, restated with the indirect path made explicit.** Facets 11-28
measure 1.00-1.09 extent inflation and were called clean. The filter does not run
on them, so a direct no-op is guaranteed by construction and is NOT evidence of
anything. What is being tested is the INDIRECT effect: recovered facet identity
should be broadly stable, the same dormers found in the same places. **Large
changes among facets 11-28 require explanation before any other result is read.**
This is the assertion the silent-failure standing rule requires, and its
independence comes from it being a prediction about facets the fix does not
target.

**P3, MAIN FACET QUALITY.** Expected to improve. **Magnitude unknown and possibly
small**, because only 0.15-3.8 percent of points move and every one is already
within the inlier band, so they are not gross outliers. Recorded as a measurement
to make, NOT as an assumption. A negligible improvement is a legitimate outcome
and does not make the fix wrong.

**P4, THE BAR.** The bar is `max()` over the 8 main facets. All 8 are fragmented.
**The bar should DROP.**

**P5, BLOB 0, REWRITTEN ON REPAIRED REASONING. NET EXPECTATION: BLOB 0 GETS
FURTHER FROM PASSING, NOT CLOSER.**

The original reasoning ("its candidate comes from the residual pass, so it should
move less") was backwards, as Emmett said. The repaired reasoning is:

- Blob 0's candidate points are the unexplained points inside BLOB 0'S OWN CELLS,
  on the east elevation of the south wing.
- The strays being removed belong to main facets whose bodies are elsewhere, and
  they only enter the residual at all if the refitted planes stop covering them.
- Blob 0's candidate therefore changes only if newly-unexplained points land
  INSIDE BLOB 0'S CELLS specifically. That is an empirical question, not a
  structural guarantee, and it is now stated as such.

**The direction is still defensible, but it rests on P4, not on blob 0 being
insulated:** the bar drops because all 8 main facets refit, while blob 0's
candidate has no comparable reason to improve. A falling bar and a
weakly-coupled candidate widen the gap. **Written down before the number exists,
because it is the same shape as the erosion refutation** where the bar fell 0.239
and blob 0 moved 0.001. If blob 0 gets closer to passing, that is a surprise to
be explained, not a result to be welcomed.

**P6, COVERAGE, corrected.** The original reasoning was the same false premise.
Corrected: facet coverage changes only through refitted planes moving relative to
points, so **the direction is NOT confidently predictable**. The upper bound on
newly-unexplained points is the number of strays removed, about 79,000 across the
8 main facets; the lower bound is zero. **Recorded as a bounded quantity with an
unknown direction rather than as a confident prediction.** Stating a direction
here would be guessing and would score as luck.

**P7, PITCH WILL CHANGE ON ALL 8 MAIN FACETS, AND THIS IS THE PREDICTION THAT
MATTERS MOST.** Per-facet pitch is a primary deliverable and comes straight from
the fitted normal.

The earlier reading that "alpha rejects the bridging triangles so area barely
moves" was correct about AREA and was not carried through to PITCH. A trimmed SVD
fit minimises squared perpendicular distance, and a point's leverage on the
fitted orientation grows with its in-plane distance from the centroid. Strays sit
11.6 to 53.4 ft out against core extents of the same order, so **individual
strays carry leverage comparable to or greater than a typical core point**,
despite being a small fraction of the count. Facet 0 carries 26,753 of them.

**Per-facet pitch delta will be reported explicitly for all facets, in degrees,
to four decimals.**

**A consequence of P7 to be checked rather than assumed:** the frozen 2026-07-18
pre-registration used this same `discover_facets` path. Whatever pitch delta M1a
removal produces is also a measure of how much the frozen pitch numbers were
computed on contaminated membership. This does not retroactively change the
freeze, which is what it is. It does bear on how the pitch validation result
(max |error| 2.19 deg, PASS at 3 deg) should be read.

**P8, THE RESIDUAL POOL (new, on repaired reasoning).** The residual pool grows
by the strays whose refitted plane no longer covers them, **bounded above by
about 79,000 points** (the sum of stray counts across the 8 main facets) and
below by zero. Since escaping the band requires roughly a 0.25 degree tilt at 50
ft and proportionally more at shorter range, **the realised growth is expected to
be a MINORITY of that bound and is tightly coupled to the P7 pitch deltas.** The
run reports actual newly-unexplained point count against the 79,000 bound, and
against the measured pitch deltas, so the coupling is scored rather than assumed.

**P9, FACET COUNT (new).** `min_points_hard` is 1,933. The 8 main facets hold
297,583 to 1,538,098 points and lose at most 3.8 percent, so **all 8 main facets
survive with near-certainty; predicted main count 8.** The recovered count is
NOT safely predictable, because recovery re-runs on a changed residual:
**predicted 21 plus or minus 3, direction unknown.** A recovered count outside
that band is a flag to stop and read before going further, not a result to
absorb. **Predicted total: 29 plus or minus 3.**

---

**"MAIN BODY" IS DEFINED HERE, NOT AT IMPLEMENTATION TIME.**

Facet 0 resolves into 1,076 components. Largest by POINT COUNT and largest by
PLAN AREA are different choices and need not be the same component.

**CHOICE: LARGEST BY POINT COUNT.**

**Why:** the plane fit weights points equally. The component that dominates the
FIT is the one that should define what the facet is, and that is the point-count
component by definition. Choosing by area would let a sparse sprawling fragment,
which contributes little to the fit, decide what is kept.

**What it would cost if wrong:** on a facet whose true body is sparsely captured
and which also has a dense compact fragment elsewhere, the filter would keep the
fragment and DELETE THE BODY. That is a catastrophic and highly visible failure,
not a subtle one. Facets 21 and 25 through 28 are explicitly flagged in the
review as poorly captured, so the failure case is present on this building.

**Guard, because picking is not the same as knowing:** the sweep reports, per
facet, whether the largest-by-count and largest-by-area components are THE SAME
COMPONENT. **Any facet where they disagree is a stop-and-look, not an
auto-resolve.** If they never disagree, the choice was immaterial and is recorded
as such.

---

**PLATEAU TEST, per 3c. Two parameters, both swept. Neither may be chosen by its
effect on the outcome.**

    connectivity scale   cell size at which two points count as connected,
                         swept in multiples of median point spacing
    minimum component    how large a component must be to be kept, swept as a
                         fraction of the facet's largest component

Both are in transferable form (spacings, fractions) rather than absolute lengths,
so an adopted value carries to bungalow and cove_house.

The sweep reports at every combination: kept-point fraction per facet, extent
inflation per facet, pitch delta per facet, the resulting bar, blob 0's candidate
quality, facet coverage, facet count, and the count/area component agreement
above.

**A plateau means a region over which the ANSWER does not change.** The size
floors in this project sit in bands 15.9x and 9.0x wide; main discovery's
`min_pitch` has only about 1.8 degrees, already recorded as thin.

**IF THERE IS NO PLATEAU, THE REPORT SAYS SO AND THE PASS STOPS.** No value is
picked from a monotone curve. A threshold on a slope is a threshold chosen by its
effect, which is what 3c exists to prevent, and it would be the third time in two
days that a plausible fix was proposed and had to be withdrawn.

---

**WHAT WOULD REFUTE M1a AS A MECHANISM WORTH FIXING**

- The strays turn out to be genuine roof on the same plane, so removing them
  deletes real surface. Testable against the footprint mask and the render.
- Removing them changes nothing measurable: pitch, quality and lines all static.
  Then the fragments are cosmetic and the mechanism, while real, does not matter.
- Facets 11-28 move substantially. Then the fix is doing something other than
  what it claims.
- Dormer lines L11-L16 break. Then the fix trades one defect for another.
- No plateau exists in either parameter.

---

**ARTIFACT DISCIPLINE, per 3d.** The result is written to a NEW dated artifact.
`canonical-2026-07-26-r2` is never overwritten and remains canonical until a
successor is deliberately adopted. Published coverage stays 88.40 pct until then.

**SCOPE. This pass fixes M1a ONLY.** M1b (facets 8, 9, 10) is untouched: its
absorbed regions are spatially contiguous, so a connectivity filter cannot reach
them. M2 through M7 are untouched.

**Cost if wrong:** a superseded artifact is the whole exposure.
`canonical-2026-07-26-r2` is untouched and every number quoted from it stays
quotable.

**Evidence for the mechanism:** `reports/big_house/fragments-2026-07-27.json`;
`reviews/big_house/review-2026-07-27.json`;
`decisions/2026-07-27-triage-pass-1-result.md`.

**Attribution:** the nine predictions and their directions, the requirement to
justify the fix independently of the review, the demand that both connectivity
parameters be swept with a stated stop-if-no-plateau, the demand that "main body"
be defined here rather than at implementation time, the facet-count prediction,
and the observation that pitch was under-carried in the earlier area reading, are
all Emmett's, dictated before the fix was written. The correction to the
residual-pool premise underneath P5, P6 and P8, the leverage argument
quantifying P7, and the plane-versus-facet framing are Claude's.
