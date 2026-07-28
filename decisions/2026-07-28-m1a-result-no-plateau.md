### 2026-07-28: M1a RESULT: no plateau. The pass STOPS, nothing is adopted, and four of nine predictions failed

**Decision: the M1a pass stops here and adopts nothing.** The pre-registration
says: "IF THERE IS NO PLATEAU, THE REPORT SAYS SO AND THE PASS STOPS. No value
is picked from a monotone curve." There is no plateau. The report says so.

`canonical-2026-07-26-r2` remains canonical. Published facet coverage remains
88.40 pct. The connectivity filter stays in the codebase OPT IN, defaulting
off, so no existing artifact changes.

**Evidence:** `reports/big_house/m1a-sweep-2026-07-28.json` (20 grid points plus
baseline, 3,928 s), `reports/big_house/m1a-scorecard-2026-07-28.json`,
`reports/big_house/grid-phase-2026-07-28.json`,
`reports/big_house/component-sizes-2026-07-28.json`,
`reports/big_house/recovered-identity-2026-07-28.json`.

---

## THE SCORECARD, BEFORE ANY INTERPRETATION

    P1  UNSCOREABLE  main-facet lines resolve, dormer lines survive
    P2  HELD         the control, on the amendment's replacement assertions
    P3  FAILED       main-facet quality improves
    P4  FAILED       the quality bar should DROP
    P5  UNSCOREABLE  blob 0 gets further from passing
    P6  HELD         coverage: bounded, direction deliberately not claimed
    P7  FAILED       pitch will change on ALL 8 main facets
    P8  HELD         residual pool bounded by about 79,000 points
    P9  HELD         8 main, 21 plus or minus 3 recovered

Four HELD, three FAILED, two UNSCOREABLE. Read the qualifications below before
reading that line as a score, in both directions: two of the HELDs are weaker
than they look and one of the FAILEDs is more of an artifact than a refutation.

---

## THE PLATEAU TEST: 16 DISTINCT ANSWERS OVER 20 GRID POINTS

The criterion was fixed IN CODE before the run: two grid points share an answer
when `n_main`, `n_recovered`, every facet's pitch to 0.01 deg, facet coverage
to 0.01 pct and the quality bar to 0.001 all agree. The largest group of
agreeing grid points is THREE, and they are not adjacent in the grid:
(2.5, 0.0001), (3.5, 0.001) and (5.0, 0.0001).

**A plateau is a CONNECTED REGION over which the answer does not change.** Three
scattered points that happen to round to the same tuple are not a region. There
is nothing here to adopt a value from.

The tolerance was NOT loosened after the fact to manufacture a flat region.
That would be choosing the answer, which is what the plateau rule exists to
prevent, and this project has already withdrawn three fixes for adjacent
reasons.

**The observed spread, given descriptively so the size of the effect is
visible rather than hidden behind a verdict:** the quality bar ranges 2.9429 to
2.9662 against a baseline of 2.9480, facet coverage ranges 88.37 to 88.40 pct
against a baseline of 88.40, and points removed ranges 3,134 to 838,168, a
factor of 267 across the grid.

---

## WHY IT FAILS, and it is not subtle

The connectivity scale has a FLOOR below which the filter destroys real roof,
and the floor is not far below the values a person would naturally pick.
`component-sizes-2026-07-28.json` measured this on the INPUT before the sweep
ran: at 1.0 x spacing, facet 7's largest component holds 21,294 of ~290,000
points and facet 6's holds 86,290 of ~400,000. At 1.5 and 2.0 x spacing facet 3
is still split into two near-equal halves (second component 0.9237 of the
largest), so `min_component_frac` = 1.0 deletes half of it. That is 838,168
points removed at (1.5, 1.0) and 653,345 at (2.0, 1.0), and at the second of
those a dormer stops being recovered (21 becomes 20).

So the two swept parameters are not independent knobs over a flat region; they
trade off against each other, and the answer moves continuously as they do.

---

## P3 AND P4 FAILED FOR THE SAME REASON, AND IT IS INFORMATIVE

The bar ROSE at (1.5, 1.0), from 2.9480 to 2.9662. Both predictions were
directional and both are therefore refuted by one grid point, correctly.

**Why the bar rose is the interesting part.** The bar is `max()` over the 8 main
facets' trimmed RMS. Deleting points usually improves an RMS. It got worse
because at that setting the filter deleted the wrong half of a facet: what
survived was a worse-fitting piece than the whole had been. **A quality metric
got worse because a fix removed real surface.** That is the pre-registered
catastrophic failure mode showing up as a number rather than as a picture, and
it is the strongest evidence in the run that the filter's floor is real.

At the other 19 grid points the bar dropped, by at most 0.0051. So the
predicted direction is right in general and wrong where it matters, which is a
worse outcome for a directional prediction than being uniformly wrong.

---

## P7 FAILED, BUT ON RESOLUTION, NOT ON SUBSTANCE. STATED PLAINLY BECAUSE IT
## FLATTERS NOBODY TO BLUR IT

P7 said pitch WILL change on all 8 main facets. Scored at the 4 decimal places
the pre-registration itself demanded, it fails at 9 of 20 grid points, and at
(5.0, 0.0001) only ONE facet of 8 shows a non-zero delta.

**But no facet anywhere lost zero points.** The count of facets losing nothing is
0 at every one of the 20 grid points. So pitch did change on all 8 everywhere;
at loose settings it changed by less than 0.00005 deg and rounded away. P7
fails against its own stated precision, and the honest reading is that the
prediction was true and the reporting precision was chosen too coarse to show
it. Recorded as FAILED regardless, because rewriting the precision after seeing
the result is the same error as rewriting a tolerance.

**The magnitude, which is the part that matters for a primary deliverable:** the
largest pitch change anywhere in the grid is 0.2120 deg, at (1.5, 1.0), the
destructive setting. At (2.5, 1.0) it is 0.0141 deg. Against the frozen
validation result of max |error| 2.19 deg and a 3 deg pass threshold, **M1a
contamination moves pitch by well under one percent of the frozen error.** The
pre-registration asked for this to be checked rather than assumed: checked. The
frozen pitch numbers were not meaningfully computed on contaminated membership.

---

## THE TWO-CHANNEL RESULT: EMMETT'S EXPECTATION IS REFUTED BY THE DATA, AND THE
## DECOMPOSITION IS WHAT MADE THAT VISIBLE

The 2026-07-28 amendment required the coupling to be reported as two separate
channels rather than pooled as "the plane moved". At (2.5, 1.0):

    facet  centroid shift  OFFSET channel   ROTATION channel   stray radius
             (total, in)   (along-normal)   (at stray radius)
      0          3.6186          +0.0057             0.2404          69.5 ft
      2          9.1388          -0.0018             0.1111          73.2 ft
      6          4.1460          +0.0007             0.0192          69.8 ft
      7         21.0765          +0.0015             0.0176          83.0 ft

**Emmett expected the centroid channel might dominate for facets whose strays
are far out and one-sided. It does not. It is negligible everywhere.** The
centroids move a great deal, up to 21 inches on facet 7, but **almost entirely
IN PLANE**, so they do not move the plane. The along-normal component, which is
the only part that is a channel at all, never exceeds 0.0057 inches. The
rotation channel is one to two orders of magnitude larger.

**This is exactly why pooling them would have been wrong, and the error would
have been large rather than cosmetic.** A report of "facet 7's plane anchor
moved 21 inches" would have overstated that plane's actual offset shift of
0.0015 inches by a factor of about 14,000. The requirement to separate the
channels was Emmett's; the finding that only the along-normal component is a
channel is what turned a 21-inch number into a 0.0015-inch one.

---

## THE PRE-REGISTERED COUNT-VERSUS-AREA GUARD: NEVER FIRED

"Any facet where largest-by-count and largest-by-area disagree is a
stop-and-look." They agreed at every facet at every one of the 20 grid points.
Per the pre-registration's own wording, **the choice of definition was
immaterial and is recorded as such.**

---

## P2, AND AN INSTRUMENT ERROR OF MINE THAT HAD TO BE CAUGHT BEFORE IT COULD BE
## REPORTED

The amendment's replacement assertions A1 (point-domain separation), A2
(independent component count), A3 (the no-op tripwire) and A5 (conservation) all
PASS at every grid point, as does A0 (the filter-off baseline reproduces
`canonical-2026-07-26-r2`) and A4 (facet identity: the discovery planes are
bit-identical across all 21 runs).

A1 passed tightly rather than comfortably, which is what a sharp assertion looks
like: the minimum kept-to-removed distance runs about 1.10 times the
connectivity cell, against a theoretical floor of 1.0.

The committed P2's INDIRECT half (recovered facet identity, not merely count)
was not answerable from the sweep, which persisted counts only.
`probe_recovered_identity.py` answers it: at (2.5, 1.0) all 21 recovered facets
sit within **3.66 inches** of a canonical recovered facet's centroid, and 18 of
21 within 0.26 inches. The largest pitch move on a matched pair is 0.11 deg.
Recovered facet identity is stable.

**The instrument error, recorded because the number it produced was reported
before it was caught:** that probe's acceptance radius was set to half a
coverage cell, which is **0.022 ft, or 0.26 inches**. A quarter-inch radius for
deciding whether two facets are the same facet is a point-spacing quantity
being used to answer a building-scale question, and it produced a headline of
"17 of 21 matched" that meant nothing. The distances themselves, all under 3.7
inches, are the answer. **This is the same class of error as P8's bound below:
a threshold inherited from a nearby quantity without checking what it means in
the units of the question being asked.**

---

## P8 HELD, AND THE HOLDING IS LUCK

Newly unexplained points range from 40 to 6,662 against the pre-registered
bound of about 79,000, so the bound holds with room to spare.

**But the bound was derived from the wrong point set.** The 79,000 figure was the
sum of stray counts in `fragments-2026-07-27.json`, measured on the canonical
POST-TRIM facet points. The filter runs on PRE-TRIM membership, a strictly
larger set, and actually removes between 3,134 and 838,168 points. At ten of the
twenty grid points the filter removes MORE than 79,000 points, and at
(1.5, 1.0) it removes more than ten times that.

So the quantity the bound was reasoning about is not the quantity it bounded.
It survives only because newly-unexplained turned out to be two orders of
magnitude smaller than points-removed, which is a fact about how little the
planes moved and not something the bound anticipated. **Emmett's own standard,
applied to a prediction Claude wrote: a prediction resting on a false premise
scores as luck even when the direction is right.** Recorded HELD, with the
premise marked false.

---

## P6 HELD, AND IT COST NOTHING TO MAKE

The amended P6 deliberately claims no direction. It therefore cannot be refuted
by coverage moving either way, and scoring it HELD is close to vacuous.
Recorded as such rather than counted as a success. Coverage moved between 88.37
and 88.40 pct, a range of 0.03 points, so the honest content of P6 is that the
quantity barely moved at all.

---

## P5 IS UNSCOREABLE FOR A STRUCTURAL REASON THAT WAS INVISIBLE WHEN IT WAS
## WRITTEN

P5 asks what happens to "blob 0's candidate quality". **Under the production
configuration blob 0 has no candidate.** Its dominant plane, 162,938 points at
3.774 deg, is discarded by the recovery PITCH WINDOW (`min_pitch` = 5.0) before
quality is ever tested. The quality bar never gets to judge it.

This does not contradict
`decisions/2026-07-26-correction-min-pitch-exclusion-figure.md`, which found the
bar to be what holds blob 0 back. That finding came from a probe that
deliberately opened the recovery pitch window to 1.0 so the plane could reach
the quality test, where it failed by 0.0002 (quality 2.9482005 against bar
2.9479968). Both statements are true of their own configuration.

The consequence for P5 is that it was written asking a question the production
pipeline does not evaluate. **An indicative reading, not a score:** holding blob
0's historical candidate quality of 2.9482005 fixed, it would clear the bar at
exactly one grid point, (1.5, 1.0), where the bar rose to 2.9662. That is the
"surprise" direction P5 named, and it arrives for the worst possible reason:
blob 0 becomes acceptable only because the reference facets were degraded by a
setting that deletes real roof. **A rising bar admitting more roof is not the
detector working, it is the detector losing its calibration.**

---

## ONE ANOMALY, FLAGGED RATHER THAN EXPLAINED

At (2.5, 1.0) facet 3's extent inflation gets WORSE, 1.41 to 2.21, while every
other facet improves (facet 0: 2.09 to 1.15, facet 2: 2.40 to 1.04, facet 7:
2.18 to 1.42). Facet 3 loses only 772 points there. Inflation is measured at a
FIXED cell of 2.5 x spacing regardless of the sweep's connectivity scale,
deliberately, so this is not the measurement following the knob. Not explained;
recorded so it is not lost.

---

**Rejected:**

- **Loosening the plateau tolerance until three scattered points become a
  region.** The tolerance was fixed in code before the run precisely so this
  could not be done afterwards.
- **Adopting (2.5, 1.0) because it is the canonical cell and the pre-registered
  main-body rule.** It is the most defensible single point and it is still a
  point on a slope, not a plateau. Adopting it would be picking a value from a
  monotone curve with extra steps.
- **Re-running the sweep with the recovery pitch window opened so P5 becomes
  scoreable.** That is a different configuration, and
  `decisions/2026-07-27-reassignment-pass-contamination.md` already establishes
  that a probe run with altered parameters does not measure the production
  pipeline.

**Cost if wrong:** the exposure is one superseded artifact and about 65 minutes
of compute. `canonical-2026-07-26-r2` was never written to and every number
quoted from it stays quotable. If M1a is later shown to matter more than these
numbers suggest, the filter is already built, tested by six passing assertions,
and opt-in.

**What this does NOT establish.** It does not show that M1a is not a real
mechanism; `fragments-2026-07-27.json` measured the fragmentation and it is
real. It shows that a connectivity filter parameterised this way has no stable
operating region on this building, and that the effect it removes moves the
deliverables by very little: pitch by at most 0.0141 deg at the canonical cell,
coverage by at most 0.03 points.

**Attribution:** the demand for a full grid rather than a pilot, the
stop-if-no-plateau rule, the requirement that the two coupling channels be
reported separately, the requirement that the scorecard precede any
interpretation, and the instruction that nothing be adopted, are Emmett's. The
grid values, the plateau criterion and its fixing in code before the run, the
scoring of each prediction, the identification of P8's bound as
wrongly-derived, the reading that P7 fails on resolution rather than substance,
and the two instrument errors recorded above, are Claude's.
