### 2026-07-29: The 6 points of coverage are INTERIOR SPECKLE, not a boundary rim. The old grid was failing to explain roof it was sitting on

**Status: RENDER-GATED FINDING under standing rule R6.** The grid fix
(`2026-07-28-adopt-exact-pitch-and-declared-lattice-origin.md`) was adopted with
its entry written first; this is the render that R6 requires before the new
number is published, and the 3d re-render that a regeneration triggers.

**Evidence:** `reports/big_house/coverage-flips-2026-07-29.png` and
`.json`.

---

## THE QUESTION, AS PUT

Roughly 6 points of coverage change hands. Those cells have locations, and two
very different stories fit the same number:

    A THIN RIM around every facet     discretisation. Benign. What a regrid
                                      does to a boundary.
    PATCHES IN FACET INTERIORS        something else, and more serious: the old
                                      grid was failing to explain roof it was
                                      sitting directly on top of.

**The number cannot tell them apart. The render can.**

---

## THE ANSWER: INTERIOR, OVERWHELMINGLY

    69,047 cells gained, 1,989 lost

    depth of gained cells inside the OLD explained region
      <= 1 cell (rim)        1,015    1.5 pct
      1 to 2 cells             611    0.9 pct
      2 to 4 cells           1,049    1.5 pct
      > 4 cells (interior)  66,372   96.1 pct

    median depth 104.8 cells, max 439.9 cells (19.27 ft from any boundary)

**96.1 percent of the gained cells sit more than four cells inside the old
explained region, at a median depth of 105 cells.** The render shows it
directly: fine green speckle distributed evenly across the face of every facet,
not a fringe.

Depth is measured with the distance transform run on the HOLE-FILLED old mask,
per standing rule R3. Unfilled, it would have measured distance to the nearest
one-point capture hole instead of depth inside the facet, which is silent
failure 2 in the register.

**So it is the second story.** The old grid was scattering false "unexplained"
verdicts through the middle of well-covered roof, because `testable` and
`explained` were being read off two rasters of different pitch. It was not
mis-drawing boundaries; it was punching holes in surfaces.

---

## THE COMPANION PANEL: THE FIX DOES STABILISE IT

With the fix applied on both sides, a half-cell phase shift moves 2,553 cells in
and 2,824 out, against 69,047 for the grid fix itself, and coverage moves 94.27
to 94.45 pct. The right-hand panel is nearly empty. **The residual phase
sensitivity is a twenty-seventh of the defect that was removed.**

---

## A PREDICTION OF CLAUDE'S THAT FAILED, RECORDED RATHER THAN DROPPED

Claude predicted a spatial signature: the Hall/Hexp pitch mismatch accumulates
linearly with distance from the origin, reaching 0.487 x 0.731 cells at the far
corner, so gained-cell density should RISE with distance and rise more along y
than along x.

    gained cells per 1000 region cells, by distance from the origin
      along x   34  93  70  47  80  43  21  33  39  43 180 120
      along y   63  69  58  49  51  48  36  24  11  26  59

**NOT CONFIRMED. The profiles are non-monotone in both axes.**

**And the test is confounded, so it is weak evidence either way.** Gained cells
are cells sitting near the `min_pts = 2` threshold, and how many of those exist
depends on local capture density, which varies enormously across this building
(facets 21 and 25 through 28 are flagged as poorly captured in the review). A
clean version would control for local point density and this one does not.

**Mechanism attribution therefore rests on the COUNTERFACTUAL, not on this
profile:** pitch fix alone moves coverage +5.93 points, origin fix alone +1.11.
That remains solid. What is refuted is Claude's account of HOW the pitch
mismatch produces the speckle, not THAT it does.

---

## CONSEQUENCE FOR THE PASS-2 REVIEW

The regenerated state `canonical-2026-07-28-grid` (8 main + 21 recovered, 94.25
pct) is a new artifact and under 3d it owes a re-render and re-review. **The
review has NOT been run.** This render answers one specific question ordered
ahead of it; it is not a substitute for the pass-2 review, which under
`2026-07-27-review-loop-changes-blind-diff-and-free-text.md` is graded blind with
the diff toggle OFF and is Emmett's eyes, not a computation.

**Note the coverage figures differ slightly by design:** 94.27 pct is the grid
fix on the FIXED canonical facet state, isolating the grid; 94.25 pct is the
regenerated artifact, where recovery re-ran on a changed residual and moved the
facet set. The 0.02 difference is that second effect, kept separate rather than
blended.

---

**Rejected:**

- **Publishing the new number on the strength of the counterfactual alone.**
  That is what R6 exists to prevent, and the render turned out to change the
  interpretation substantially: "6 points of rim" and "6 points of interior
  speckle" are different claims about the building.
- **Measuring depth on the unfilled explained mask.** R3, and the register.
- **Dropping the failed drift prediction.** It was made in writing before the
  profile was computed and it failed; deleting it would leave the entry
  claiming a cleaner mechanistic story than the evidence supports.

**Cost if wrong:** if the depth measure is somehow mis-anchored, the rim/interior
split is wrong. Three checks passed, including one that this script's own region
construction reproduces `split_coverage` exactly on the same grid, and one
anti-null on both flip sets.

**Attribution:** the instruction that item 3 triggers pass 2, the demand to
render the flipping cells specifically and in their own colour, the rim-versus-
interior discriminator and what each would mean, and the request for the same
render under a half-cell phase shift, are all Emmett's. The depth measurement,
the drift prediction and its refutation, and the note on the confound, are
Claude's.
