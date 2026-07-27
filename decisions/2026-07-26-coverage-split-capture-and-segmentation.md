### 2026-07-26: Coverage splits into a capture metric and a segmentation metric, over a hole-filled footprint

**Decision:** The single coverage percentage is replaced by two numbers over a
footprint whose enclosed holes are filled before erosion:

    density-testable fraction = testable cells / footprint cells   (CAPTURE)
    facet coverage            = explained cells / testable cells   (SEGMENTATION)

The footprint is reported three ways in every run: cells at 2 or more points,
that mask with enclosed holes filled, and the result after one-cell erosion.

**Why the base was wrong.** Coverage was being reported as a percentage of
something that was not the roof. The mask is not a clean outline: on big_house it
holds 111,154 enclosed holes totalling 370,079 cells, most of them a single
cell, because a cell needs 2 points to be testable and 249,745 cells inside the
roof hold exactly one. Eroding that mask widens every hole from the inside. 90 to
95 percent of what each erosion ring removed was hole boundary rather than
building outline, and the single one-cell erosion discarded 97.483 cu^2, 32.5
percent of the footprint, before the ratio was computed. Filling holes first
drops that cost to 2.6 percent.

**Why filling is principled and not a patch.** It is this project's own
invariant applied to the mask instead of to the facets: a roof is a CLOSED
SURFACE, so a cell entirely enclosed by roof is roof, whatever its point count.
It introduces no parameter and no threshold. It cannot bridge a real courtyard or
light well either, because only regions with no path to the outside are filled,
and every filled region is measured and the largest named, so a genuine opening
surfaces instead of being silently absorbed. On big_house the largest single
filled region is 2.674 cu^2 against a 362.105 cu^2 footprint.

**Why one number had to become two.** The old percentage was answering two
different questions at once, so a change in it could not be attributed. How much
of the roof has enough points to test at all is a property of the FLIGHT and the
reconstruction, which no segmentation change can move. How much of the testable
region a facet explains is the SEGMENTATION result, and it is what the coverage
gate was built to produce. Mixed together, a sparse capture drags the combined
number down and reads as a segmentation failure. That is precisely what was
happening.

**The restated numbers.**

    footprint    raw (>=2 points)  299.654 cu^2
                 holes filled      362.105 cu^2
                 after erosion     352.707 cu^2

    density-testable fraction (CAPTURE)       82.29 pct   290.256 of 352.707
    facet coverage           (SEGMENTATION)   88.40 pct   256.574 of 290.256

The previously reported 93.14 percent (2026-07-23) and 93.51 percent
(2026-07-26) are RESTATED, not corrected. They were arithmetically right over a
base that was wrong, which is a different failure and worth naming as one.

**Restating coverage costs nothing methodologically, and this is why.** Coverage
was NEVER pre-registered. The frozen file `preregistered-2026-07-18.json` holds
area and pitch; coverage arrived with Task 4, three days later. No frozen claim
depends on it, so it can be corrected on its merits without touching the
pre-registration method. Had it been frozen, this entry would read very
differently.

**Attribution, because three changes landed together.** Reported as one
before-and-after the number moves and nobody can say why, so each cause is
isolated. The baseline row reproduces the published 93.508 percent and its 9,829
duplicated points exactly, which anchors the decomposition to the real state:

    a  min_pitch 10 -> 5      93.508 -> 94.773   +1.265 pts
    b  cell-based selection   94.773 -> 94.719   -0.054 pts
    c  hole filling           94.719 -> 88.396   -6.323 pts  (base +88.085 cu^2)

Facet coverage FELL, and that is the correct direction: a base a third too small
was flattering the result. The decomposition is sequential and not commutative;
the order is stated in the report.

**Vertical surface, a small named effect.** A plan-view test can never explain a
vertical surface: a dormer cheek or gable end standing inside the footprint fills
plan cells no roof facet will ever claim. Measured absolutely, because that
figure does not depend on the disputed base: **7.075 cu^2 of vertical surface
inside the footprint**, 2.36 percent of the building, accounting for 0.725 cu^2
of residual. It is a real structural ceiling and it is small. It should be named
and never led with, and never used to explain away the residual. The instrument
adds no parameter: a cell is vertical when its points span more height than one
surface at the 60 degree pitch limit could span across a cell diagonal, plus the
scatter the quality bar already permits. The measured distribution is bimodal and
the threshold lands in its trough.

**What still limits facet coverage, by pointer not by number.** Roughly a third
of the remaining unexplained plan area sits in a single residual region that
produces no facet because its surface falls below `min_pitch`. The absolute
figures and the reasoning live in
2026-07-26-min-pitch-definition-not-filter.md, so that a later revision touches
one file rather than two. The open item is a question, not a consequence:
whether recovery should carry its own `min_pitch` separate from main discovery.

**Rejected:**
- Keeping one combined percentage. It conflates a capture shortfall with a
  segmentation score and cannot be attributed.
- The erosion-ring rows (coverage excluding a 2, 3 or 4 cell edge ring). They
  were an attempt to separate a ragged eave from real unexplained area and were
  measuring hole widening instead; the deep rings sampled only the densest roof.
  Hole filling removes the reason they existed.
- Lowering the 2-point testability threshold to 1. A single point cannot show
  whether a facet explains a cell, so this would inflate the base with cells that
  carry no evidence either way.
- Reporting facet coverage alone. The capture number is the one that is
  actionable on a future flight, and it is the one that cannot be fixed in code.

**Evidence:** `reports/big_house/task7a-2026-07-26.json` (A4 vertical surface, A5
the hole census and the ring attribution), `canonical-2026-07-26-r2.json`,
`coverage-map-2026-07-26-r2.json`, `attribution-2026-07-26.json`,
`capture-2026-07-26.json`.

**Consequence already acted on:** the density-testable fraction is now measurable
BEFORE the pipeline runs on a cloud, needing no crop box. bungalow measures 67.09
percent on the raw cloud against big_house's 60.68 percent, so the same capture
shortfall is present at the next site, slightly less severe. big_house cannot be
re-flown, so for that site it is permanent.

**Cost if wrong:** If hole filling absorbs a real opening, the footprint gains
area that is not roof and the density-testable fraction is overstated. The
filled-hole size table is the guard, and it must actually be read on each new
site rather than assumed benign.
