### 2026-07-27: CORRECTION: boundary erosion is REFUTED as a fix, and the "interior clears the bar" figure is withdrawn. Three mechanisms proposed for blob 0, three dead.

**What this corrects.** `2026-07-27-blob0-confirmed-roof.md`, committed earlier
the same day, records boundary contamination as "THE ACTUAL CAUSE" of blob 0's
failed fit and quotes an interior-only quality of 2.90857 that clears the
2.94800 bar. The measurement behind that figure was defective, and the
generalisation drawn from it does not survive testing. That entry is not edited;
the log is append-only, so the claim and its withdrawal both stand as the record.

Emmett's own note, recorded because the attribution matters: the instruction to
record boundary contamination as the actual cause was his, and it went into a
committed entry on his instruction. The defective measurement underneath it was
Claude's. Neither half is being assigned to the other.

---

**PART 1: THE 2.90857 FIGURE IS WITHDRAWN, AND WHY IT WAS WRONG.**

The probe computed depth-from-boundary with a Euclidean distance transform on the
patch's RAW occupancy mask, with its holes still in it. Sparse capture leaves the
mask riddled with unoccupied cells, and every one of them is background to a
distance transform. So a point sitting next to an internal capture hole was
scored as shallow, and only points in DENSE neighbourhoods survived the interior
cut.

    "interior" as measured  = points in DENSE regions
    "interior" as intended  = points FAR FROM THE FACET EDGE

Those are different sets, and the first one is guaranteed to score better,
because roughness tracks sparseness (Spearman +0.237, measured in the same
probe). The figure was not a finding. It was the density correlation, re-measured
under another name.

THIS IS THE SAME DEFECT ALREADY LOGGED ON 2026-07-26 for the coverage
denominator, where eroding a hole-riddled footprint mask discarded 32.5 percent
of the roof and 90 to 95 percent of what each erosion ring removed was hole
boundary rather than building outline. It was fixed there by filling holes first.
It was then reintroduced, at full strength, inside a diagnostic probe, because
the earlier fix lived in production code and the probe wrote the operation fresh.

**STANDING RULE, no exceptions:** any depth-from-boundary or erosion measurement
FILLS ENCLOSED HOLES FIRST, matching the rule the footprint denominator already
uses. This applies to diagnostics exactly as it applies to production code. A
probe that reports a number is production code for the purposes of this rule.

Corrected figure, measured with holes filled: blob 0's genuinely deep points
score **2.9472**, against the 2.94800 bar. It still fails. The direction of the
original claim was wrong, not just its magnitude.

**What still stands.** The blob-0-specific profile is unaffected and was measured
correctly: flat within +/-0.25 inches across 230 of the patch's 250 inches along
its long axis, then a step to -2.75 inches over the last roughly 20 inches, at
the edge where blob 0 abuts the main roof above it. That observation is real.
What does not survive is the generalisation from it and the remedy proposed on
the strength of it.

---

**PART 2: EROSION IS REFUTED AS A POPULATION PROPERTY.**

Tested across all 8 main facets, all 21 recovered facets and blob 0, from the
canonical state, with nothing derived from blob 0
(`boundary-erosion-population-2026-07-27.json`).

Emmett's pre-registered condition was that BOTH numbers must move under
symmetric erosion, so that the fix could not be a one-sided favour to the
candidate under discussion, and so that the outcome at any given width was not
predictable in advance. The test was run as specified and it returned a clean
negative:

    erosion width      quality bar    blob 0     margin
    0.00 in              2.94800      2.94820   +0.00020
    2.10 in              2.86993      2.95762   +0.08770
    4.20 in              2.80332      2.95714   +0.15381
    8.41 in              2.70939      2.94720   +0.23781

The bar moves -0.2386. Blob 0 moves -0.0010. **Blob 0 never passes at any width,
and the margin gets roughly 1,200 times worse.** Eroding every facet makes the
bar stricter faster than it helps the candidate, which is the opposite of the
intended effect.

RECORDED BECAUSE THE TEST DESIGN IS THE TRANSFERABLE PART: `both_moved` was
written as a pass condition before the sweep was run, and it is what turned a
plausible fix into a refuted one in a single measurement. A fix that only moves
the thing it is meant to move is a fix chosen by its effect. Require the
symmetric version of any proposed relaxation, applied to everything, and read
both numbers.

**A mechanism prediction, half held and half refuted.** The physical story was
that dense stereo matching blends across depth discontinuities, so the effect
should be strongest where a taller surface stands over a facet. The ordering was
written into the probe BEFORE the run. Boundary minus interior, mean signed
residual:

    abuts_taller_surface   +0.727 in   (n =   337,169)
    free_edge              +0.147 in   (n = 3,838,554)
    junction_no_step       -0.010 in   (n = 3,132,592)

The MAGNITUDE ordering held exactly, 5x and 70x. The SIGN was inverted: points at
an occlusion step are pulled UP toward the taller surface, and the prediction
said down. Recorded as `prediction_held: false`. The mechanism is real and the
stated prediction was wrong, and both halves are reported because the prediction
was committed before the measurement rather than written afterwards.

**Not a population property.** 18 of 30 entities show a negative boundary bias
and 12 show a positive one, so the consistent negative sign blob 0 displays is
not shared. Stabilisation depths do not cluster, and 15 of 30 sit at the
profiling ceiling, meaning they never stabilised in the measured range. That last
figure is partly a limit of the metric and is not offered as a measurement.

---

**PART 3: BLOB 0'S STATUS, STATED HONESTLY.**

Three mechanisms have been proposed to explain why a confirmed piece of real roof
fails the fit-quality bar. All three are dead:

    two planes forced into one fit     REFUTED  0.267 deg apart, 0.425 in
                                                separation, interleaved rather
                                                than regional
    boundary contamination as cause    WITHDRAWN measured on an unfilled mask;
                                                 the figure was density, not depth
    symmetric erosion as the fix       REFUTED  bar falls 0.239, blob 0 moves
                                                0.001, never passes

**Blob 0 is real roof that fails the quality bar, and there is currently no
defensible reason to think the bar is wrong.** That is the honest position and it
is recorded as such rather than left implicit while the search continues.

ONE CANDIDATE REMAINS, AND IT IS NOT BEING PROBED YET: fit quality is a residual
DISTANCE with no normalisation for capture density, and the bar is calibrated as
`max()` over 8 well-captured facets. A surface reconstructed from fewer, noisier
points would fail it while being just as planar. That argument is stated in
`2026-07-27-blob0-confirmed-roof.md` and is untouched by anything here, because
it never depended on the boundary story.

By Emmett's instruction it WAITS until after the first visual review pass. The
reason is the reason for the development/validation split
(`2026-07-27-development-vs-validation-split.md`): three mechanisms have now been
proposed and killed by reasoning about one facet through summary statistics, and
the whole roof has not yet been looked at once.

**Cost if wrong:** none beyond the record. Every figure above is on disk with the
run that produced it, and no threshold, operator or definition was changed.

**Evidence:** `reports/big_house/boundary-erosion-population-2026-07-27.json`
(sweep, boundary-type profiles, per-entity stabilisation);
`reports/big_house/blob0-residuals-2026-07-27.json` (the blob-0 profile that
stands, and the two-plane rejection).

**Corrects:** `2026-07-27-blob0-confirmed-roof.md`, specifically the paragraph
naming boundary contamination as the actual cause and the 2.90857 interior
figure. The rest of that entry, including the confirmation that blob 0 is real
roof and the argument that the metric confounds capture quality with planarity,
stands.

**Attribution:** the instruction to record boundary contamination as the cause,
the `both_moved` test condition, the decision to hold the remaining candidate
until after visual review, and the shared ownership of the error are Emmett's,
stated directly. The defective measurement, the diagnosis of it, and the wording
are Claude's.
