### 2026-07-26: CORRECTION: min_pitch=5 excludes 0.326 cu^2, not 19.04 cu^2; the quality bar is what holds back blob 0

**Decision:** The figure quoted in
2026-07-26-min-pitch-definition-not-filter.md under "WHAT min_pitch = 5 STILL
EXCLUDES" is WRONG and is corrected here. That entry is not edited; the log is
append-only, so the error and its correction both stand as the record.

    CLAIMED   4 planes, 166,015 points, 19.0425 cu^2 gross
    ACTUAL    1 plane,    2,623 points,  0.3260 cu^2 gross

The `min_pitch = 5` DECISION ITSELF IS UNAFFECTED. The spanning-artifact
argument, the A3 quality evidence, the 1.8 degree plateau limit and the
low-slope label all stand on their own measurements. What was wrong is one
paragraph quantifying the consequence.

**Why the original figure was wrong.** It came from re-peeling each residual
blob with the pitch window opened to 0-90 degrees and `max_planes` raised to 6,
then measuring the sub-window planes that came back. That instrument was built
in Task 7A3 to answer "are the planes this filter rejects any good?", which it
answers correctly. It was then reused, without re-examination, to answer "how
much would we recover by relaxing the filter?", which it does NOT answer.

Opening the window changes the PEEL ITSELF, not merely what survives it.
`find_roof_planes` ends with a reassignment pass: every point in every KEPT
plane is pooled and handed to its nearest plane, then each plane is refitted to
its final members. With the window opened to 0-90, blob 0's near-vertical planes
(85.9 and 85.3 degrees) are kept, so they enter that pool and change both the
membership and the fitted normal of the near-flat plane being measured. The same
physical surface measures 147,505 points and 16.09 cu^2 under the opened window
and 162,938 points and 16.60 cu^2 in the real recovery pass. Only the second one
was ever a candidate the pipeline could have accepted.

**What actually rejects blob 0's plane: the QUALITY BAR, by a hair.** Read from
the recovery pass's own candidate log at recovery `min_pitch = 1.0`, a value low
enough that pitch cannot be the reason for any rejection:

    blob 0  peel 0 = 162,938 pts at 3.774 deg   kept_by_pitch = True
            candidate 162,938 pts, 3.82 deg, gross 16.5962 cu^2
            REJECTED BY: quality 2.948 > bar 2.948

The plane clears the pitch window and is then rejected by the fit-quality bar on
a strict greater-than, at a margin below the log's three-decimal precision. It is
exactly as planar as facet 4, the roughest ACCEPTED main facet, and loses the
tie. Two smaller planes fail the same gate honestly and by wide margins: blob 13
at 4.693 and blob 14 at 6.823 against the same 2.948 bar.

**Evidence:** `reports/big_house/recovery-pitch-sweep-2026-07-26.json` (lowering
recovery min_pitch from 5 to anywhere in 1.0-4.0 admits exactly ONE facet of
2,623 points, on a flat 3.0 degree plateau; the cross-check row at 5.0
reproduces canonical-2026-07-26-r2 exactly, so the sweep is measuring what it
claims), and `blob0-rejection-2026-07-26.json` (the candidate log naming the
gate).

**How the error was caught, recorded because the method matters more than the
number.** It was not caught by review. The sweep was run to answer a different
question, and its result did not add up against the claimed figure: relaxing the
filter recovered 0.326 cu^2 where 19.04 had been predicted, a factor of 58. That
mismatch was the only signal. Attribution of a rejection to a threshold merely
because the value sits near that threshold is what produced the error, and the
fix is to read which gate the pipeline itself recorded rather than to infer one.

**Reasoning not stated by Emmett; the above is the measured case.** Emmett
approved recording the correction. The framing and the analysis are mine, and
the error being corrected was mine.

**Cost if wrong:** None beyond the record. Both figures are now on disk with the
runs that produced them, so a future reader can recompute either.

**Corrects:** 2026-07-26-min-pitch-definition-not-filter.md (one paragraph; the
decision in that entry stands).

**Open question this hands forward:** blob 0's 16.6 cu^2 plane is roughly a
third of all remaining unexplained plan area and sits exactly on the quality
bar. Three readings, undecided: the bar is working correctly and a facet that
rough should not be admitted; the comparison is a boundary artifact where `>`
versus `>=` decides 16.6 cu^2; or the bar itself is the problem, since it is
`max()` over main-facet quality and one rough main facet makes it permissive
everywhere. The hard rule in `roofkit/coverage.py` says fit quality is NEVER
relaxed, so nothing has been changed. Worth understanding WHY that plane matches
facet 4's roughness so precisely before touching any of it.
