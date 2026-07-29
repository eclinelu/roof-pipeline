### 2026-07-29: M1a is MEASURED AND DEPRIORITIZED. Not a known limit, and the distinction is the point

**Decision: M1a is closed as MEASURED AND DEPRIORITIZED.** Attempt 2 is NOT run.
The draft stays in `docs/draft-m1a-attempt-2-preregistration.md` as a live
option, not as an abandoned one.

**This is NOT a known limit under 3e, and the words matter:**

    KNOWN LIMIT (3e)          something the pipeline cannot do, written up so a
                              reader is not misled. The honest response when a
                              defect resists fixing.

    MEASURED AND DEPRIORITIZED  a REAL mechanism, one fix attempted and refuted
                              on its own pre-registered criterion, a second
                              designed and shelved, and the effect on the
                              deliverables MEASURED and found small enough that
                              other work outranks it. It is FIXABLE. It has not
                              been fixed because it is not worth the time right
                              now.

Calling this a known limit would claim the pipeline cannot do something it
demonstrably can. The connectivity filter works, passes six independent
assertions, and is in the codebase opt-in and defaulting off.

**Evidence:** `reports/big_house/m1a-area-exposure-2026-07-29.png` and `.json`;
`decisions/2026-07-28-m1a-does-not-move-the-deliverable.md`;
`decisions/2026-07-28-m1a-result-no-plateau.md`.

---

## THE AREA CAVEAT, WHICH WAS THE ONE THING STILL OPEN

The pitch audit closed with an explicit open limit: it said nothing about AREA,
and extent inflation is an area-shaped defect. Closing M1a on the pitch result
alone would have been closing it on incomplete evidence.

**The argument tested (Emmett's):** the alpha shape rejects triangles that bridge
large gaps, so a remote sliver cannot drag a spanning triangle into the facet's
area. It contributes only its own local area. If so, the summed alpha area of
the removed components BOUNDS M1a's area exposure.

**Measured at the canonical setting, 151,449 points removed:**

    facet  removed   comps  degen  removed area ft^2  facet ft^2  pct of facet
      0     69,021    290    185          41.041        493.48       8.316
      1      2,700    144    102           1.285        789.16       0.163
      2     42,371    338    201          19.735        351.04       5.622
      3        772     79     52           0.640        605.66       0.106
      4      1,694     43     23           0.592        326.73       0.181
      5      6,611    124     79           1.942        211.10       0.920
      6     13,855    203    118           6.597        379.21       1.740
      7     14,425    165    123           8.741        416.46       2.099

    TOTAL 80.57 ft^2 = 2.26 pct of the reported 3,559 ft^2

**The argument holds and the bound is 2.26 percent.** Cross-checked three ways,
all passing: conservation per facet; the removed count reproduces the sweep's own
151,449 written by different code; and the summed per-component area never
exceeds the whole-set area, which is the assertion that would fail loudly if the
alpha areas were computed on the wrong point sets.

**The degenerate components are counted, not swallowed.** Qhull raises on a
component whose projected points are collinear, and 883 of the 1,386 components
are degenerate. Their true alpha area IS zero, so skipping is correct, but they
hold only 1,056 points between them, and reporting the count is what
distinguishes "there was nothing there" from "the exception fired 883 times".

---

## 2.26 PERCENT IS NOT NEGLIGIBLE, AND THE RENDER IS WHY IT IS STILL DEPRIORITIZED

**Stated plainly against the temptation to round it away:** 2.26 pct of a roof
area is about three quarters of a square of shingles on this building. That is
two orders of magnitude larger than M1a's pitch effect (0.0121 deg against 0.81
deg of headroom) and it would matter in an estimate.

**The render (R6) is what settles it, and it changed the interpretation.** The
removed points are NOT scattered debris. They are **long, spatially coherent,
LINEAR runs that follow the roof's own ridges and hips**: a continuous line up
the north wing on facet 7, long traces along the hips on facets 0 and 2, runs
along the west wing on facet 6. Only a small minority are the isolated far-flung
specks the phrase "remote sliver" suggests.

**That is exactly what the mechanism predicts and nobody had drawn.** A facet's
unbounded plane, extended, passes closest to the neighbouring surface AT THE
RIDGE, where the two planes meet. The strays are ridge and hip material sitting
within the band of the wrong facet's plane.

**And it changes what the 2.26 pct means.** This is not phantom area invented in
empty space; it is real roof near shared edges, currently attributed to whichever
plane happens to be nearest. Removing it from facet 0 does not delete roof from
the building, it stops facet 0 claiming a strip that belongs to its neighbour.
The total-area exposure is therefore **an attribution error concentrated on
shared edges, not an area invention**, and the per-facet numbers (facet 0 at
8.3 pct of itself) matter more than the total.

**Which points at the fix that is already on the books.** Shared edges are
precisely the scope of
`decisions/2026-07-27-candidate-boundary-regularization.md`, where a boundary
shared with a neighbour becomes ONE line from plane-plane intersection. That
candidate would address M1a's residual area exposure as a side effect of doing
its own job properly. **Deprioritising M1a is therefore not abandoning the 2.26
pct; it is routing it to the work item whose scope it actually falls in.**

The dependency runs the right way too: that candidate is blocked behind clean
normals, and the pitch audit has now shown M1a's contamination of the normals is
0.0121 deg, i.e. not the blocker it was assumed to be.

---

## WHAT IS ON THE RECORD, SO THE CLOSURE IS AUDITABLE

    the mechanism is REAL           fragments-2026-07-27.json: all 8 main facets
                                    fragmented, inflation 1.21 to 2.40, strays to
                                    53.4 ft, facet 0 in 1,076 components
    attempt 1 REFUTED               no plateau, 16 distinct answers over 20 grid
                                    points, refuted on its own pre-registered
                                    criterion, not abandoned
    attempt 2 DESIGNED, not run     docs/draft-m1a-attempt-2-preregistration.md
    pitch effect MEASURED           0.0121 deg vs 0.81 deg headroom, no verdict
                                    flips at 3 deg or 2 deg
    area effect MEASURED            80.57 ft^2, 2.26 pct, bounded by the alpha
                                    argument, concentrated on shared edges
    the thing itself RENDERED       m1a-area-exposure-2026-07-29.png

---

**Rejected:**

- **Calling it a known limit under 3e.** It is fixable and a fix is drafted.
  3e is for what the pipeline cannot do.
- **Closing it on the pitch audit alone.** The area caveat was open and is now
  closed with a number and a picture.
- **Running attempt 2 anyway for completeness.** Emmett's call, and Claude's own
  draft predicted it would succeed technically and change nothing that matters.
  Running it to confirm a prediction of immateriality is the definition of low
  expected value.
- **Rounding 2.26 pct away as small.** It is not small. It is routed, not
  dismissed, and the render is what justifies routing it to boundary
  regularization rather than to a third membership filter.

**Cost if wrong:** if the ridge-line reading of the render is wrong and the
removed material is genuinely spurious area rather than misattributed real roof,
then the reported total is overstated by up to 2.26 pct and the correction waits
for boundary regularization instead of happening now. The bound is measured
either way, so the exposure is known rather than open.

**Attribution:** the instruction to close M1a rather than run attempt 2, the
insistence that the area caveat be killed first, the alpha argument that bounds
the exposure, the demand to render the removed components in place before
deprioritising a real mechanism, and the requirement to use the words MEASURED
AND DEPRIORITIZED rather than known limit, are all Emmett's. The measurement, the
degenerate-component accounting, the reading that the removed material follows
ridges and hips, and the argument that this routes the exposure to boundary
regularization, are Claude's.
