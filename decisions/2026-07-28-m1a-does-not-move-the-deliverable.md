### 2026-07-28: M1a moves the frozen pitch validation by 0.0121 deg against 0.81 deg of headroom. It is real, and it does not matter for the deliverable

**Status: AUDIT, side artifact only, nothing adopted.** The 2026-07-18 freeze is
not restated, reopened or corrected. This asks only what it WOULD have been.

**Evidence:** `reports/big_house/frozen-pitch-audit-2026-07-28.json`, computed
from `comparison-2026-07-18-scored-2026-07-18.json` and
`m1a-sweep-2026-07-28.json`, both committed.

---

## THE QUESTION THE PRE-REGISTRATION ASKED TO BE CHECKED RATHER THAN ASSUMED

The 2026-07-18 pitch validation ran through the same `discover_facets` path the
sweep has now shown carries disconnected fragments on all 8 main facets. So
every frozen pitch number was computed on contaminated membership. The
pre-registration flagged the consequence and required it be checked.

Checked. The arithmetic: take each frozen facet's pitch, add the sweep's
measured per-facet delta, re-score against the same inclinometer truth.

---

## THE RESULT, AT BOTH ENDS OF THE GRID

    frozen                          max |error| 2.19 deg, PASS at 3, FAIL at 2
    headroom to the 3 deg line      0.81 deg

    LOOSEST setting (5.0 x spacing, fraction 0.0001; 3,134 points removed)
      max |error| 2.19 -> 2.188      change -0.0020 deg
      PASS at 3: True -> True        PASS at 2: False -> False
      no facet's verdict flips at either threshold

    CANONICAL setting (2.5 x spacing, fraction 1.0; 151,449 points removed)
      max |error| 2.19 -> 2.2021     change +0.0121 deg
      PASS at 3: True -> True        PASS at 2: False -> False
      no facet's verdict flips at either threshold

**The largest error change anywhere is 0.0121 deg. The headroom is 0.81 deg. The
effect is 1.5 pct of the margin, about 67 times too small to change the
verdict.**

Both settings are reported rather than one, because a single setting cannot
distinguish "the fix does nothing" from "this setting does nothing". A 48-fold
change in points removed, 3,134 to 151,449, moves the worst error by 0.014 deg.

**At the canonical setting the error gets very slightly WORSE**, +0.0121 deg on
facet 0. Removing the contamination did not improve agreement with the tape. It
is far inside the noise and is recorded rather than smoothed.

---

## THE TERM THAT ACTUALLY DOMINATES, AND IT IS NOT M1a

The frozen `pitch_summary` records a **mean bias of 1.83 deg**: the pipeline
reads about two degrees steeper than the inclinometer on essentially every
facet. That is a systematic offset **151 times larger than the largest M1a
effect measured here**, and it is what stands between the current result and a
PASS at 2 deg.

M1a is not the reason the pitch validation fails at 2 deg. Whatever is, it is
not this.

---

## WHAT THIS DECIDES: SCOPE, NOT ACCURACY

This is not an accuracy claim; big_house is the development site and no accuracy
claim comes from it (`2026-07-27-development-vs-validation-split.md`).

What it decides is where the remaining time goes. **The case for fixing M1a
before freezing bungalow and cove_house is weak on this evidence.** Bungalow is
ready and cove_house arrives in about a week, and M1a's demonstrated effect on
the primary deliverable is 0.0121 deg.

**This does NOT say M1a is not real.** `fragments-2026-07-27.json` measured it:
extent inflation 1.21 to 2.40, strays up to 53.4 ft out, facet 0 in 1,076
components. It says the mechanism is real and its effect on pitch is
negligible. Those are compatible, and conflating them is how a real defect gets
either over- or under-prioritised.

**What it does NOT settle:** the effect on AREA. No measured area exists for
big_house, so area has never been validated against ground truth, and this audit
says nothing about it. Extent inflation is an AREA-shaped defect, and the one
deliverable it would most plausibly move is the one with no ground truth to move
against. Recorded as an open limit, not as a clean bill of health.

---

**Rejected:**

- **Reading this as licence to skip M1a entirely.** M1a sits at stage 1,
  upstream of M2 and M3, and 3b does not permit skipping an identified
  mechanism because it looks small. One further attempt is drafted
  (`docs/draft-m1a-attempt-2-preregistration.md`); if it also fails, M1a
  becomes a known limit written up under 3e.
- **Auditing at one setting.** Two are reported for the reason given above.
- **Restating the frozen numbers.** The freeze is what it is. This is a
  counterfactual, kept clearly separate.

**Cost if wrong:** if the sweep's per-facet deltas are themselves wrong, this
audit inherits that error. The deltas rest on sweep assertion A0, which proved
the filter-off baseline reproduces `canonical-2026-07-26-r2` bit for bit, and on
A4, which proved facet identity is preserved across all 21 runs. Both passed.

**Attribution:** the instruction to audit whether M1a actually moved the frozen
numbers, the framing that this bears on SCOPE rather than accuracy, and the
observation that bungalow and cove_house timing makes the scope question live,
are Emmett's. The two-setting design, the headroom comparison, the observation
that the 1.83 deg systematic bias dominates by two orders of magnitude, and the
caveat that area is untouched by this audit, are Claude's.
