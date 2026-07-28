### 2026-07-28: The published 88.40 pct facet coverage is substantially a GRID ARTIFACT. Coverage cannot be used as a cross-pass detector until this is settled

**Status: FINDING, nothing adopted.** `canonical-2026-07-26-r2` is unchanged and
published facet coverage remains 88.40 pct until a successor is deliberately
adopted. This entry does not correct that number; it records that the number is
not measuring only what it is supposed to measure, and that a decision is now
owed.

**Evidence:** `reports/big_house/production-phase-2026-07-28.json`.

---

## THE MEASUREMENT

Shifting the production raster's ORIGIN by fractions of a cell, changing nothing
else, on the canonical 29-facet state:

    offset (cells)   facet coverage   density-testable   footprint eroded
      0.00, 0.00         88.40 pct        82.29 pct          352.707 cu^2
      0.25, 0.00         89.28            82.60              350.854
      0.50, 0.00         87.22            82.54              351.171
      0.75, 0.00         87.72            82.25              353.019
      0.00, 0.50         89.83            83.07              347.703
      0.50, 0.50         88.08            82.96              347.878
      0.33, 0.66         92.42            82.51              351.352
      0.66, 0.33         88.20            82.89              348.515

    facet coverage spread over phase:  5.20 PERCENTAGE POINTS

**The published 88.40 pct is one sample from a 5.2-point range produced by an
alignment nobody chose.** For scale, the entire 20-point M1a sweep moved
coverage by 0.03 points. The unmeasured parameter is about 170 times larger than
the one that was measured.

---

## THE CAUSE, FOUND WHILE AUDITING THE ORIGINS AND CONFIRMED BY COUNTERFACTUAL

`plan_grid` (`roofkit/coverage.py:41`) asks `histogram2d` for `nx` bins spanning
`[xlo, xhi]`. It does NOT ask for bins of width `cell`. Since
`nx = int(span/cell) + 1`, the actual bin width is `span/nx`, always slightly
SMALLER than `cell`.

Its sibling in the same function, `Hexp` (`coverage.py:101`), is anchored over
`[xlo, xlo + nx*cell]` and therefore DOES have bins of exactly `cell`.

**The two histograms `coverage_masks` compares cell-for-cell are on grids of
different pitch, and the mismatch ACCUMULATES with distance from the origin.**
Measured on big_house:

    Hall bin width   99.9782 pct (x), 99.9729 pct (y) of cell
    Hexp bin width   100 pct
    drift at the far corner   0.487 x 0.731 CELLS

So at the far side of the building, `testable` and `explained` are being
compared across a shift of up to three quarters of a cell. Every area is
charged as `cell^2`, which is the pitch of neither grid.

**The counterfactual settles causation rather than leaving it argued.** The same
sweep, the same function, one flag flipped to make the bins exactly `cell` wide:

                              as-is        exact_pitch
    coverage spread over phase   5.20 pts      0.18 pts
    coverage at zero offset      88.40 pct     94.33 pct

**Fixing the pitch removes 97 pct of the phase sensitivity and moves the number
by about 5.9 points.**

---

## A CORRECTION TO CLAUDE'S OWN INTERMEDIATE READING, MADE THE SAME SESSION

On the strength of the integer-offset test (an integer cell shift moved coverage
by only 0.01 points) Claude stated that the bin-pitch defect was NOT what drove
the phase sensitivity. **That was wrong.** The integer-offset test is a poor
discriminator: an integer shift changes `nx` by the same integer, so the pitch
error is almost preserved and the test is nearly blind to it. The direct
counterfactual is the right instrument and it says the opposite. Recorded
because the wrong reading was stated out loud before the right one.

---

## WHAT IS AND IS NOT AFFECTED

**Affected**, because they all inherit the one data-derived origin from
`plan_grid`: `testable`, `explained`, the hole-filled `footprint`, the eroded
`interior`, `residual_blobs`, and `recover_facets`' candidate cell selection
(`coverage.py:370`). `area_accounting` (`coverage.py:545`) derives a SECOND,
different data-extent origin from the facet points.

**Not affected:** PITCH. It comes from a fitted plane normal through
`tilt_degrees` and never passes through a plan raster. The frozen 2026-07-18
pitch validation is untouched by this finding.

**Genuinely phase-sensitive even after the pitch fix**, and therefore NOT
explained by the defect: the filled footprint (spread 3.93 cu^2 as-is, 3.76
fixed) and the eroded footprint (5.32 as-is, 5.53 fixed), each about 1.1 to 1.5
pct. That residue is real discretisation sensitivity: with `min_pts = 2` and
249,745 cells holding exactly one point, a phase shift flips marginal cells
across the threshold and changes which holes are enclosed. The raw footprint is
stable to 0.06 pct.

---

## THE CONSEQUENCE THAT MATTERS MOST

**Attempt 1's coverage analysis measured nothing.** The M1a sweep reported
coverage moving between 88.37 and 88.40 pct and treated that as a signal. It
sits two orders of magnitude inside a 5.2-point artifact. Every coverage
statement in `decisions/2026-07-28-m1a-result-no-plateau.md` should be read as
noise. **This does not change that entry's conclusion**, which rests on the
plateau count, the quality bar and pitch, none of which are rastered.

**And coverage cannot serve as a cross-pass detector until this is settled**,
which is the reason the audit was ordered before the next mechanism pass. A
pass-to-pass coverage change of a few points would be indistinguishable from a
re-alignment.

---

## THE DECISION NOW OWED, NOT TAKEN HERE

Whether to make the grid self-consistent, which moves published facet coverage
from 88.40 pct to about 94.33 pct.

**Not taken in this entry, deliberately.** It is a change to a published number
and to the base every historical coverage figure was computed against, so it
belongs in its own deliberate decision with its own supersede-not-overwrite
handling, exactly as `2026-07-26-2026-07-23-state-superseded.md` required of the
last such change. Riding it in as a side effect of a diagnostic is how a number
changes without anyone deciding it should.

The `exact_pitch` flag exists in `plan_grid` and defaults to the historical
behaviour, so nothing moves until someone flips it on purpose.

---

**Rejected:**

- **Fixing it immediately because it is obviously a bug.** It is obviously a
  bug and it is also a 5.9-point change to the headline number. The project's
  own rule is supersede, never overwrite, and a corrected file implies the old
  numbers were an arithmetic mistake. They were correct computations under a
  defective definition, and that distinction is the finding.
- **Concluding the phase sensitivity is inherent discretisation.** Tested and
  refuted by the counterfactual for coverage; upheld for the footprint.
- **Treating the raster-phase result as an M1a-only problem.** That was the
  reading at the end of the M1a pass and it was too narrow. The M1a filter was
  the THIRD data-derived origin in the codebase, not the only one.

**Cost if wrong:** if the `exact_pitch` grid is somehow the wrong convention,
the cost is that a 5.9-point correction was proposed on a false basis. The
argument that it is right is that `Hexp` and the `cell^2` area charge already
assume bins of width `cell`, so `exact_pitch=True` is the only setting under
which all three parts of the calculation agree with each other.

**Attribution:** the instruction to audit the production pipeline rather than
stop at the M1a filter, the specific list of stages to check (occupancy grid,
hole filling, footprint mask), the requirement to measure on the production
path, the demand for an anti-null assertion, and the observation that a
phase-dependent coverage number cannot function as a cross-pass detector, are
all Emmett's, and the audit found a defect that would not have been looked for
otherwise. The bin-pitch defect, the drift measurement, the counterfactual that
established causation, and the correction to Claude's own intermediate reading,
are Claude's.
