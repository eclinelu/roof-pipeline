### 2026-07-27: Blob 0 is real roof, confirmed by physical inspection. Coverage was right, and the defect is upstream of the quality bar.

**Finding:** Emmett inspected the physical building on 2026-07-27 against
`reports/big_house/blob0-location-2026-07-27.png` and identified blob 0 as A REAL
ROOF SECTION: a lower roof on the east elevation of the south wing, heavily
tree-occluded, and built of a different material from the main facets. It is
11.5703 cu^2 of plan area (131.5 ft^2 at the run 2 scale) and its rejected
candidate plane carries 16.5962 cu^2 gross across 162,938 points.

The tree occlusion is not incidental. It is why the cloud is weak there, and the
weak cloud is why the fit is rough. The physical explanation and the numerical
symptom are the same fact.

**This is a DEFINITION being applied, not ground truth tuning a parameter.** The
completeness invariant says every part of the building footprint seen in plan
must be explained by some facet. It was adopted 2026-07-21, implemented, and its
output committed on 2026-07-26 in `canonical-2026-07-26-r2`, naming blob 0 at
11.5703 cu^2 as the largest unexplained region. All of that predates the
2026-07-27 inspection. The roof was walked to answer a question the pipeline had
already asked, in the pipeline's own words. Nothing measured on the roof has been
fed back into a threshold, and the standing rule
(`2026-07-14-ground-truth-audit-only.md`) is intact.

STATED PLAINLY BECAUSE IT WOULD BE EASY TO OVERSTATE: the invariant was adopted
AFTER the 2026-07-18 pre-registration freeze, not before it. Emmett initially
recorded it as predating the freeze and corrected that himself on 2026-07-27. What
the invariant precedes is the INSPECTION, which is what this entry rests on. The
weaker claim is the true one and it is still sufficient: the detector named this
patch before anyone looked at it.

**COVERAGE IS NOT BROKEN. It fired correctly.** 88.40 percent facet coverage is a
detector reporting that 11.6 percent of the testable roof is real surface the
pipeline failed to explain, and physical inspection has now confirmed the largest
piece of it. That is the gate doing exactly the job it was built for.

**Published coverage stays 88.40 percent.** Suppressing the number by moving a
threshold would destroy the only evidence the detector works. A completeness gate
that has never flagged anything is indistinguishable from a broken one; a gate
that flagged something and was then confirmed by inspection is the strongest
evidence this project has that the invariant is worth anything. The number is not
an embarrassment to be tuned away, it is the result.

**The defect is upstream of the bar.** Fit quality is `trimmed plane RMS / point
spacing`: a residual DISTANCE. That single number confounds at least three
different things:

    capture noise            how well the cloud reconstructed the surface
    material micro-structure how rough the real surface is at point scale
    genuine non-planarity    whether the surface is actually a plane

The bar is `max()` over 8 main facets that are well-captured shingle: they have
essentially none of the first two. So the bar asks "is this as smooth as a
well-captured shingle facet", when the question the gate is supposed to answer is
"is this a plane". A tree-occluded surface of a different material fails the first
question while passing the second, which is precisely blob 0.

**This argument does not depend on blob 0's verdict** and is not an argument for
admitting it. It would be equally true if blob 0 had cleared the bar by a wide
margin. It says the metric is the wrong shape for the job, not that this
particular answer is wrong.

---

**THE CHEAP HYPOTHESIS WAS TESTED FIRST, AND IT IS DEAD.** Before anything
upstream was blamed, blob 0 was tested for being TWO surfaces with a single plane
forced across both. Measured in `blob0-residuals-2026-07-27.json`, rejected on
three independent measures:

    angle between the two fitted planes    0.267 deg   (a real facet pair: degrees)
    perpendicular separation at centroid   0.425 in    (parallel sheets: inches)
    plan cells that are nearly pure one    38.9 pct    across 175 interleaved
      part or the other                                regions, largest holds 46 pct

**The 42.25 percent RMS improvement from the two-plane fit was DISCARDED, not
treated as support.** Two planes always beat one. On a noisy sheet the gain comes
from cutting the noise cloud into an upper and a lower half, and that is exactly
what the three measures above describe: near-parallel, near-coincident, and
interleaved cell by cell rather than occupying separate regions. An RMS gain is
not evidence for a split unless the split is also spatially real. Recording this
because the discarded number is the interesting part: it is the one figure that
would have supported the wrong answer.

Two other candidate explanations were also rejected, on their own measurements.
NOT bimodal: bimodality coefficient 0.2265, BELOW the Gaussian value of 0.333, so
the distribution is more sharply unimodal than a Gaussian, and Ashman's D is 1.05
against the 2.0 needed for resolvable lobes. NOT periodic material structure: the
radial power spectrum is a smooth power law with no peak at 2.67 in
(corrugation), 5 in (shingle course) or 12/24 in (standing seam).

**THE ACTUAL CAUSE: BOUNDARY CONTAMINATION.** The residual is flat within +/-0.25
inches across 230 of the patch's 250 inches along its long axis, then steps to
-2.75 inches over the last roughly 20 inches. Not a bow and not curvature: a step
at ONE end, and that end is the edge where blob 0 abuts the main roof standing
above it. Both the bias and the scatter are monotone in depth from the boundary:

    depth from boundary    mean signed    mean |residual|
      0.0 to  2.1 in         -0.320 in       0.872 in
      4.2 to  6.3 in         -0.183 in       0.725 in
      8.4 to 12.6 in         -0.139 in       0.653 in
     16.8 to 25.2 in         +0.090 in       0.560 in

The global linear trend over the whole patch is R^2 = 0.047, essentially nothing,
which is why this had to be profiled against depth from the boundary rather than
against position: a feature confined to a margin is invisible to a whole-patch
ramp. Capture noise is a confirmed contributor alongside it but is not the whole
story: |residual| tracks local sparseness (Spearman +0.237, p ~ 0) while the
distribution is decidedly non-Gaussian (skew -0.895, excess kurtosis +1.95, a
one-sided negative tail).

**NO EROSION WIDTH IS ADOPTED HERE, AND THE ONE THAT APPEARS IN THE PROBE MUST
NOT BE USED.** Points deeper than 8.4 inches from the boundary do score 2.90857
against the 2.94800 bar, which clears. That number is NOT a result to build on:
8.4 inches is four map cells, a value Claude picked to draw a profile with, and a
fix resting on it would be a threshold chosen by looking at the answer. Emmett
flagged this and ruled it out explicitly. Any erosion width has to be established
as a population property across all 29 facets, with a plateau, before it means
anything.

---

**NOTHING WAS CHANGED IN THIS TASK.** No threshold, no comparison operator, no
definition of the bar, no regeneration. `canonical-2026-07-26-r2` remains
canonical and published coverage remains 88.40 percent. Diagnosis first: a fix
chosen before the cause is understood would be a fix chosen by looking at the
answer, and the margin here is 0.0069 percent, small enough that almost any
adjustment would flip it.

**Any eventual fix produces a NEW artifact**, superseded rather than overwritten,
labelled post-observation, and its entry must state that Emmett inspected the
roof before the change was made. A reader has to be able to see the ordering and
judge it.

**Evidence:** physical inspection 2026-07-27 (Emmett, against
`blob0-location-2026-07-27.png`); `reports/big_house/quality-bar-tie-2026-07-27.json`;
`reports/big_house/blob0-residuals-2026-07-27.json` and its three plots.

**Cost if wrong:** if blob 0 is not roof, the pipeline is currently reporting the
correct area and the only loss is the diagnostic effort. If it is roof, as
inspection says, the deliverable is short by its area and every downstream number
that omits it is short with it.

**Attribution:** the finding, the inspection, and the four arguments about
coverage and the metric are Emmett's, stated directly. The residual analysis, the
two-plane rejection and the wording are Claude's.
