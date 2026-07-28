# DRAFT, NOT A PRE-REGISTRATION, NOT COMMITTED AS ONE, NO CODE WRITTEN

M1a attempt 2: an EXTENT-BASED membership constraint.

This file is a draft for review. It is deliberately NOT in `decisions/` and NOT
in the index, because a pre-registration is a commitment and this has not been
approved. If accepted it moves to
`decisions/YYYY-MM-DD-m1a-attempt-2-extent-preregistration.md`, gets committed
AND PUSHED, and the hash is verified with `git branch -r --contains` before any
code is written.

**Standing frame:** two attempts at M1a, not more. If this one also fails, M1a
becomes a KNOWN LIMIT written up under 3e and the loop moves on.

---

## 1. WHY ATTEMPT 1 FAILED, AND WHY THAT POINTS HERE

Attempt 1 constrained membership by CONNECTIVITY on a raster. Two things killed
it:

1. **No plateau.** 16 distinct answers over 20 grid points. The connectivity
   scale has a floor below which the filter deletes real roof (838,168 points
   at 1.5 x spacing), and the two parameters trade off rather than plateau.
2. **A third parameter nobody chose.** The raster's origin phase swings facet
   3's kept fraction from 0.5186 to 0.9978, half the facet, at the same
   connectivity scale the sweep used
   (`decisions/2026-07-28-raster-phase-is-an-unswept-parameter.md`).

Both failures are properties of RASTERISING, not of the M1a mechanism. The
mechanism is unchanged and still measured: all 8 main facets carry disconnected
fragments, extent inflation 1.21 to 2.40, strays up to 53.4 ft out
(`fragments-2026-07-27.json`).

**So attempt 2 must not raster.** That is the whole design constraint.

---

## 2. THE PROPOSAL

**A facet's points must lie inside, or within a stated distance of, the facet's
own PLAN EXTENT.**

A plane is unbounded; a facet is a bounded piece of roof. Attempt 1 tried to
recover the boundary from connectivity. Attempt 2 states it directly: the facet
has an extent, and membership is clipped to it.

### The chicken-and-egg problem, and how it is resolved

The extent comes from the membership we are trying to constrain. This must be
fixed here, not at implementation time.

**CHOICE: the extent is the ALPHA SHAPE of the plane's DISCOVERY INLIERS from
the seeded 200,000-point subsample, taken before full-cloud assignment.**

**Why that seed set.** `find_roof_planes` runs on the subsample and produces,
for each plane, the inliers RANSAC actually found. That set is already
spatially coherent, is computed before the unbounded-plane assignment that
creates the defect, and exists in every run at no extra cost. `min_points_frac`
= 0.025 guarantees at least 5,000 points per plane, which is ample for an alpha
shape.

**Why alpha and not convex hull.** A convex hull bridges across an L-shaped
roof, a courtyard, or the notch between two wings, and would readmit exactly
the far-side strays this is meant to remove. The alpha shape is already in the
codebase (`facet_kept_alpha`, `alpha_mult` = 4.0).

**What it costs if wrong:** if the subsample misses a genuinely captured but
sparse region of a facet, the extent is too small there and real roof is
clipped. This is the same catastrophic direction attempt 1 had, and it must be
measured the same way: report kept fraction per facet, and flag any facet
losing more than a stated amount for inspection rather than auto-resolving.

### Why it has no phase parameter

An alpha shape is Delaunay-based and a point-in-polygon test is a geometric
predicate. Neither has a grid, so neither has an origin, so there is no
alignment to choose. The whole construction is EQUIVARIANT under translation:
translate the cloud and the answer translates with it, unchanged. That is
precisely the property the raster lacked, and it is the reason this approach is
worth one attempt.

---

## 3. THE SWEPT PARAMETERS

    dilation d      how far outside the extent a point may lie and still be
                    kept, in multiples of median point spacing
    alpha radius a  the alpha shape's radius, in multiples of median point
                    spacing (the pipeline's existing alpha_mult is 4.0)

Both are LENGTHS expressed as multiples of spacing, so an adopted value
transfers to bungalow and cove_house.

**Honest naming of the remaining degrees of freedom, because attempt 1 was
killed by one nobody named:** `a` is a real nuisance parameter and is therefore
SWEPT rather than fixed at 4.0. The seed set (subsample discovery inliers) is a
third choice and is NOT swept; it is fixed above by argument, and if attempt 2
fails, the seed choice is the first thing to look at before concluding the
mechanism is unfixable.

**Proposed grid, 5 x 4 = 20 runs:**

    d   0.5, 1.0, 2.0, 4.0, 8.0    x spacing
    a   2.0, 4.0, 8.0, 16.0        x spacing

Basis: `d` spans from well under a point spacing (essentially strict
containment) to 8 spacings, which at big_house is about 0.14 ft, still far
below the 11.6 to 53.4 ft the strays sit out at. `a` brackets the pipeline's
existing 4.0 by a factor of two either way; too small an alpha shreds the
extent into fragments, too large degenerates to the convex hull, and both ends
need to be visible for a plateau to mean anything.

---

## 4. A BLOCKING DEPENDENCY, STATED BEFORE THE RUN RATHER THAN DISCOVERED IN IT

**Attempt 2 cannot use FACET COVERAGE as a scored outcome until the
`plan_grid` bin-pitch defect is resolved.**

Measured 2026-07-28: production facet coverage swings 5.20 percentage points
under sub-cell raster phase, and collapses to 0.18 points with `exact_pitch`.
Attempt 1's entire coverage signal was 0.03 points, i.e. two orders of
magnitude inside an artifact. Any coverage prediction scored against the
current implementation would be scoring noise.

**So one of these must happen first, and it is Emmett's call which:**

  (a) resolve the bin-pitch defect deliberately, accepting that the published
      number moves from 88.40 pct to about 94.3 pct; or
  (b) run attempt 2 with coverage explicitly EXCLUDED from the scored
      outcomes, and say so in the entry.

Option (b) is runnable immediately and is the smaller change. Option (a) is the
right fix but is a change to a published number and should not ride along
inside a mechanism pass.

---

## 5. PREDICTIONS, with directions where a direction is defensible

Written knowing attempt 1's results, which makes several of these easier than
they were the first time. That is disclosed rather than hidden, and it is why
the ones that are now easy are marked as such.

**Q1, REMOVAL COUNT.** The extent constraint removes points on the same order
as connectivity did at comparable strictness. **Predicted: between 10^4 and
10^6 points removed across the 8 main facets at the strictest grid corner.**
A count below 10^3 means the extent is not binding and the sweep is measuring
nothing; that is a stop-and-read, not a clean result.

**Q2, THE CATASTROPHIC CASE.** At small `a` the alpha shape fragments and the
extent under-covers, so kept fraction collapses on at least one facet.
**Predicted: at a = 2.0 x spacing, at least one main facet keeps less than 0.90
of its membership.** This is the analogue of attempt 1's shatter at 1.5 x
spacing and it is predicted to be PRESENT, because a fix whose failure mode is
not visible in its own sweep cannot be shown to be safe.

**Q3, PITCH.** Per-facet pitch delta reported for all 8 to 4 decimal places.
**No direction claimed.** Magnitude predicted to be of the same order as
attempt 1, under 0.25 deg everywhere. **This is now an EASY prediction** and is
recorded as such: the frozen-pitch audit already showed M1a moves pitch by at
most 0.0121 deg at the canonical setting.

**Q4, THE QUALITY BAR. No direction claimed, deliberately.** Attempt 1's P4
claimed the bar would drop, and it rose at the destructive setting because
deleting real roof left a worse-fitting remnant. **The lesson is that a fit
metric is not monotone in "removing bad points", so claiming a direction was
the error.** What IS predicted: at any grid point where a facet loses more than
0.10 of its membership, the bar rises. That is a conditional with a stated
trigger and it can fail.

**Q5, FACET COUNT.** 8 main. Recovered 21 plus or minus 3. Outside that band is
a stop-and-read.

**Q6, EXTENT INFLATION.** The direct target. **Predicted to fall below 1.15 on
all 8 main facets at the plateau, if a plateau exists.** Measured at a FIXED
cell of 2.5 x spacing regardless of the swept parameters, so the measurement
does not follow the knob. This is the prediction most likely to fail cleanly
and is the one worth watching.

**Q7, COVERAGE.** Excluded, or conditional on section 4. Not scored under
option (b).

**Q8, THE CONTROL.** Facets 11-28 are not touched directly. Identity, not
count, checked against the canonical state exactly as
`probe_recovered_identity.py` now does, with an acceptance radius stated in
FEET and sanity-checked against the building, not inherited from a cell size.
Attempt 1 used half a coverage cell, which is 0.26 inches, and produced a
meaningless answer.

---

## 6. THE PLATEAU TEST, unchanged in rule and tightened in definition

Same rule: **a plateau is a CONNECTED region over which the answer does not
change. If there is no plateau, the report says so and the pass STOPS. No value
is picked from a monotone curve.**

Tightened after attempt 1: the plateau must be **CONNECTED in the grid**, not
merely a set of points that round to the same tuple. Attempt 1's largest
agreeing group was 3 scattered points, which a naive reading could have called
a plateau. The criterion is fixed in code before the run and is not loosened
afterwards.

The answer tuple: `n_main`, `n_recovered`, per-facet pitch to 0.01 deg,
per-facet extent inflation to 0.01, the quality bar to 0.001. Coverage is in
the tuple only under option (a).

---

## 7. ASSERTIONS, carried forward and extended

- **Conservation.** Kept and removed are disjoint and sum to the membership.
- **Containment, the primary and the analogue of attempt 1's A1.** Every KEPT
  point lies within `d` of the extent polygon, and every REMOVED point lies
  farther than `d` from it, verified by a point-in-polygon and distance test
  written independently of the code that built the extent.
- **Equivariance, the assertion attempt 1 could not have had.** Translating the
  entire cloud by an arbitrary vector must leave the kept/removed partition
  bit-identical. This is the property the raster failed and it is the central
  claim of this approach, so it is asserted rather than argued.
- **Anti-null.** At the strictest grid corner, removals must be non-zero on at
  least one facet.
- **Facet identity.** Discovery planes bit-identical across all runs.
- **Baseline reproduces `canonical-2026-07-26-r2`.**

---

## 8. WHAT WOULD REFUTE THIS AS WORTH DOING

- No plateau in `d` and `a`. Then M1a becomes a known limit under 3e.
- Removing the points changes nothing measurable. Then the mechanism is
  cosmetic, which the frozen-pitch audit already half suggests.
- Facets 11-28 move substantially in identity.
- The equivariance assertion fails, which would mean the approach has smuggled
  in a frame dependence and is no better than the raster.

**Cost if wrong:** about an hour of compute and one superseded artifact.
`canonical-2026-07-26-r2` is not written to.

**A dissent from the author, recorded because it is inconvenient:** the
frozen-pitch audit shows M1a moves the primary deliverable by 0.0121 deg
against 0.81 deg of headroom and a 1.83 deg systematic bias. On that evidence
the honest expectation is that attempt 2 succeeds technically and changes
nothing that matters. It is still worth one attempt, because M1a sits at stage
1 upstream of M2 and M3 and skipping it unexamined is what 3b forbids, but the
expected value is low and the second attempt should not become a third.
