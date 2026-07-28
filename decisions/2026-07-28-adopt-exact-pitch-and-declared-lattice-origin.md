### 2026-07-28: ADOPTED: exact bin pitch, and one declared lattice origin for every raster. Facet coverage moves 88.40 to 94.27 pct

**Decision:** two changes to `roofkit/coverage.py`, adopted as defaults.

1. **`exact_pitch`**, so `plan_grid`'s bins are exactly `cell` wide. **This is a
   BUG FIX, not a tuning choice.**
2. **`lattice_origin`**, so every raster in the pipeline anchors to one declared
   origin derived from the cell pitch, rather than to `min()` of whatever points
   that stage happens to see.

`exact_pitch=False` and `anchor="extent"` are both KEPT RUNNABLE so superseded
numbers can be recomputed rather than merely quoted, the same way
`fill_holes=False` was kept after the 2026-07-26 erosion fix.

**Evidence:** `reports/big_house/grid-adoption-2026-07-28.json`,
`reports/big_house/production-phase-2026-07-28.json`.

---

## PROVENANCE, STATED FIRST BECAUSE THE CHANGE FLATTERS THE PROJECT

**This moves the headline number 5.87 points in the favourable direction.** That
is exactly the shape of a result that should be distrusted, so the trail is
recorded before the numbers.

The defect was found while auditing the raster behaviour of the M1a connectivity
filter **after that filter had already been rejected** for lack of a plateau
(`2026-07-28-m1a-result-no-plateau.md`). The audit was ordered by Emmett before
the next mechanism pass, on the stated grounds that a phase-dependent coverage
number cannot serve as a cross-pass detector. Nobody was looking for a way to
raise coverage; the question on the table was whether coverage could be trusted
to DETECT anything at all.

The chain, in order, all on record: an assertion failed in the M1a sweep -> the
cause was a grid origin, not a labelling bug -> a probe built to measure that
measured nothing and had to be rebuilt -> the rebuilt probe found the phase
sensitivity in the filter -> Emmett ordered the same audit against the
production pipeline -> the audit found the bin-pitch defect.

---

## WHY IT IS A BUG AND NOT A CHOICE

`plan_grid` asked `histogram2d` for `nx` bins spanning `[xlo, xhi]`, so its bins
were `span/nx` wide, always slightly under `cell`. Its sibling `Hexp` in the same
function was anchored over `[xlo, xlo + nx*cell]`, so its bins were exactly
`cell`. And every area in the report was charged as `cell^2`.

    Hall bin width       99.9782 pct (x), 99.9729 pct (y) of cell
    Hexp bin width       100 pct
    area charged as      cell^2
    drift at far corner  0.487 x 0.731 CELLS

**Three parts of one calculation used three different ideas of how wide a cell
is.** `coverage_masks` compares `testable` and `explained` cell-for-cell while
those two masks drift up to three quarters of a cell apart across the building.
There is no configuration in which that is correct, which is what makes it a bug
rather than a parameter. `exact_pitch=True` is the only setting under which all
three agree.

---

## WHY THE ORIGIN CHANGED TOO

Three stages took `min()` of whatever points they happened to see, and no two of
them agreed:

    coverage / footprint / residual / recovery   min() of the roof cloud
    area_accounting                              min() of the facet points
    connected_core (M1a, opt-in)                 min() per facet

None was chosen. **The adopted rule:**

    xlo = floor(x.min() / cell) * cell

the global lattice of pitch `cell` through the leveled frame's origin, snapped
down to the cell at or below the data.

**The claim this rests on is narrower than "the origin is now fixed", and it is
TESTED rather than argued.** `lattice_origin` still reads `x.min()`. The
difference is what a change in `x.min()` can do:

- under `extent`, it moves the origin by an ARBITRARY SUB-CELL amount, which
  changes which points share a cell;
- under `lattice`, it can only move the origin by a WHOLE NUMBER OF CELLS, which
  is a relabelling and changes nothing about which points share a cell.

Tested by deleting the extreme points, which is exactly what a membership filter
does and exactly what made the M1a verifier disagree with the M1a filter:

    the perturbation moved min() by a genuinely SUB-CELL amount   PASS (anti-null)
    under lattice, the partition is unchanged up to relabelling   PASS
    under extent, THE SAME perturbation changes the partition     PASS

The third check is what stops the second from being vacuous.

**Transferability, which matters more than the value.** bungalow and cove_house
raster by the same RULE. The lattice differs between sites because `cell` is
2.5 x that site's own median spacing, which is correct and is the project's
standing scale-transferability principle. What transfers is that the origin comes
from the declared pitch and not from whichever point happens to lie furthest
south-west.

---

## WHAT IT COSTS ON THE NUMBERS, DECOMPOSED

    configuration                  coverage  dens-test      raw    filled   eroded
    OLD extent + loose  PUBLISHED     88.40      82.29  299.654   362.105  352.707
    pitch fix only                    94.33      82.11  299.379   362.669  353.722
    origin fix only                   89.51      82.83  299.512   359.441  348.987
    ADOPTED lattice + exact           94.27      82.72  299.440   359.843  349.640

    pitch fix alone    +5.93 points
    origin fix alone   +1.11 points
    combined           +5.87 points

The two do not add. They act on the same marginal cells, so the combined effect
is slightly less than the sum. **Decomposed rather than reported as one number,
so it is visible that the pitch fix is 84 pct of the move and the origin fix is
not carrying the result.**

The superseded configuration reproduces the committed canonical numbers exactly,
88.40 pct and 299.654 cu^2, checked and PASSED.

---

## THE NEW STABILITY CLAIM, AND THE PART OF IT THAT GOT WORSE

Spread of each quantity over eight sub-cell phase offsets:

    facet coverage        5.20 points  ->  0.18 points
    density-testable      0.82 points  ->  0.96 points
    raw footprint         0.169 cu^2   ->  0.121 cu^2
    filled footprint      3.934 cu^2   ->  4.404 cu^2
    eroded footprint      5.316 cu^2   ->  6.200 cu^2

**Facet coverage is now phase-stable to 0.18 points, a 29-fold improvement, and
that is the claim.**

**The footprint residue is NOT fixed, and under the adopted configuration it is
slightly LARGER, not smaller.** Recorded plainly because it is the inconvenient
half. That residue is not the bug: it is discretisation sensitivity from
`min_pts = 2` on a cloud with 249,745 cells holding exactly one point, where a
phase shift flips marginal cells across the threshold and changes which holes
count as enclosed. It is a permanent property of the measure at this cell size,
about 1.2 pct on the filled footprint and 1.8 pct on the eroded one, and any
future claim resting on the footprint has to carry it.

**Consequence for the cross-pass detector, which was the question:** facet
coverage can now function as one, because a pass-to-pass change above about 0.2
points is larger than the alignment noise. The footprint cannot, at better than
about 2 pct.

---

## HANDLING OF THE PUBLISHED NUMBER

- **`canonical-2026-07-26-r2` REMAINS CANONICAL** and is not overwritten. A new
  dated artifact is written alongside it.
- **88.40 pct stays quotable** as the frozen historical figure, computed
  correctly under a defective grid definition, with a pointer to this entry.
  The project's rule holds: supersede, never overwrite. A corrected file would
  imply the old number was an arithmetic mistake. It was not; it was a correct
  computation under a definition that was wrong, and that distinction is the
  finding (`2026-07-26-2026-07-23-state-superseded.md`).
- **The successor becomes canonical only when Emmett approves this entry.**

**Not affected: PITCH.** It comes from a fitted normal via `tilt_degrees` and
never passes through a plan raster. The frozen 2026-07-18 pitch validation is
untouched.

**Also affected and worth naming: `recover_facets` candidate cell selection**
inherits the grid (`coverage.py:370`), so the recovered facet set can change.
That is reported in the new artifact rather than assumed away.

---

**Rejected:**

- **Fixing the pitch and leaving the origin.** The origin defect is the one that
  bit twice, in the M1a filter and in its own verifier. Leaving it would leave a
  parameter nobody chose in a pipeline that is about to be frozen for two
  held-out sites.
- **Overwriting `canonical-2026-07-26-r2`.** Covered above.
- **Reporting one combined delta.** It would hide which of the two changes did
  the work, and the favourable direction makes that exactly the thing to expose.
- **Adopting on the strength of the counterfactual alone**, without testing the
  invariance claim the lattice origin rests on. That claim is narrower than it
  first appears and needed its own two-sided test.

**Cost if wrong:** if `exact_pitch` is somehow the wrong convention, a 5.9-point
correction was adopted on a false basis. The argument that it is right is that
`Hexp` and the `cell^2` area charge already assume bins of width `cell`, so this
is the only self-consistent setting. If the lattice origin is wrong, the cost is
a different arbitrary phase, chosen deliberately instead of accidentally, which
is strictly better than the previous state. Both are recoverable because both old
paths remain runnable.

**Attribution:** the instruction to adopt `exact_pitch` as a bug fix rather than
a tuning choice, the requirement that the entry be written BEFORE regenerating,
the demand that provenance be recorded explicitly because the change moves the
number in the flattering direction, the instruction to fix the origin in the same
pass and anchor every raster to one declared origin, and the observation that
transferability to bungalow and cove_house matters more than the value, are all
Emmett's. The lattice rule itself, the decomposition into pitch-only and
origin-only, the two-sided invariance test with its anti-null guard, and the
finding that the footprint residue is unfixed and slightly larger, are Claude's.
