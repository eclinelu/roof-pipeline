### 2026-07-29: PRE-REGISTRATION: what causes the 1.83 deg systematic pitch bias, and how it will be scored

**Status: PRE-REGISTRATION. Committed and pushed BEFORE 5b is run.** No residual
image has been produced and no spectrum computed. Every prediction below is
recorded with the shape it implies so it can be SCORED, not reinterpreted.

**Why this is now the top item:** the systematic bias is 1.83 deg. It is 151
times the largest M1a effect, it is what blocks a PASS at 2 deg, it applies to
every facet, and there is no reason to think it stops at big_house. bungalow is
ready and cove_house arrives in about a week, so whatever this is, it will be in
their numbers too.

---

## THE HYPOTHESIS (Emmett's, from how the readings were taken)

The inclinometer readings were taken by resting a phone on the shingle faces.
**Each course's exposed face is shallower than the deck**, because its butt sits
on top of the course below. The surface is a sawtooth of shallow faces separated
by small step-ups. **The phone touches only the faces. The cloud sees both, and
the plane fit follows the average, which is the deck.**

That predicts the phone reads SHALLOW, and the observed direction is that the
pipeline reads STEEPER than the phone by 1.83 deg. The direction matches.

**Reference band, so the magnitude can be checked rather than assumed:**

    3-tab          5.000 in exposure, 3.2 mm butt  ->  arctan = 1.44 deg
    architectural  5.625 in exposure, 6.0 mm butt  ->  arctan = 2.40 deg
    observed 1.83 deg sits between them, at about 4.6 mm over 5.625 in

**THE CORRECTION MUST NOT BE DERIVED FROM THE DISAGREEMENT.** Ground truth is
audit-only (`2026-07-14-ground-truth-audit-only.md`). A correction fitted to the
size of the disagreement is circular and worse than the uncorrected error,
because it would guarantee agreement while measuring nothing. Both tests below
are constructed to produce a number from geometry or from the cloud, never from
the residual against the tape.

---

## 5a. THE GEOMETRIC PREDICTION, AND ITS FIELD PROTOCOL

    offset = arctan(butt thickness / exposure)

**Measurement protocol for the next site visit**, to be executed before any
comparison with the pipeline:

1. **Exposure.** Measure the exposed face height of a course, eave to the butt
   of the course above, PERPENDICULAR TO THE EAVE and along the slope. Steel
   rule to 1 mm. Take it over FIVE consecutive courses and record each, not a
   mean: the variation is data, because it is what sets the spectral width in
   5b.
2. **Butt thickness.** Measure the step at the butt edge, deck-normal, with
   calipers to 0.1 mm. Five separate butts, recorded individually. Measure at
   the middle of a tab, not at a slot or a seam.
3. **Repeat on THREE facets of different pitch**, chosen to span the range, and
   note the material and whether the facet is 3-tab or architectural. Different
   pitch facets are what tests whether the offset is pitch-independent.
4. **Photograph a steel rule laid across four courses on each facet**, so the
   exposure is auditable from the image afterwards and does not rest on a
   number written in a notebook.
5. **Record whether any course is a starter, ridge or hip course**, which have
   different geometry and must be excluded rather than averaged in.

**PREDICTION 5a-1.** If measured geometry gives `arctan(t/e)` = 1.83 deg plus or
minus 0.3 deg, computed from the tape and the calipers ALONE with no reference
to the pipeline, that is a finding. If it lands outside that band, **the
hypothesis is wrong and the bias is something else.** Recorded now so the band
cannot be widened afterwards.

---

## 5b. THE DISCRIMINATOR, FROM DATA ALREADY ON DISK

Per-facet (pipeline pitch minus inclinometer) plotted against facet pitch.
**Two hypotheses, two different shapes, and the shapes are quantitatively
distinct rather than merely qualitatively.**

**SHINGLE STEP predicts a CONSTANT offset in degrees**, independent of pitch.
The face is tilted relative to the deck by `arctan(t/e)` whatever the deck is
doing.

**VERTICAL SCALE STRETCH predicts an offset that GROWS with pitch and vanishes
near flat.** If Z is stretched by a factor `k`, then
`tan(measured) = k * tan(true)`, and for a small stretch the offset is
approximately `(k-1) * sin(theta) * cos(theta)` in radians. That peaks at 45 deg
and is zero at 0 and 90.

**This building gives the test real power, because its facets fall in two clean
clusters:** truth pitches of 19.00, 19.33, 19.33 and 20.67 deg, against 31.67,
32.00, 32.00 and 32.00 deg.

**THE SHARP PREDICTION, fixed here.** Under vertical scale stretch the ratio of
the shallow-cluster offset to the steep-cluster offset is

    [sin(19.6) cos(19.6)] / [sin(31.9) cos(31.9)] = 0.315 / 0.449 = 0.70

Under shingle step (or any constant procedural offset) the ratio is **1.00**.

    SCORING, fixed before the number is computed:
      ratio in 0.60 to 0.82   -> consistent with SCALE STRETCH
      ratio in 0.90 to 1.10   -> consistent with CONSTANT OFFSET
      anything else           -> NEITHER SHAPE FITS, reported as such

**Also reported, as a measurement only and with no correction adopted:** the
residual scatter after removing a constant offset, per facet, in degrees.

---

## 10. THE RENDER, WHICH IS THE STRONGEST TEST AND OUTRANKS THE PLOT

Point spacing on this cloud is **0.21 in** and a shingle exposure is about
**5 in**, so a single course spans roughly **24 point spacings** and individual
courses should be RESOLVABLE. This is the test that can kill the hypothesis on
an image, which under standing rule R6 is what a claim about a physical roof
surface requires.

**Method, fixed here:** for each of the 8 main facets, render the SIGNED
RESIDUALS to the fitted plane as an image in PLANE COORDINATES, with a scale bar
in inches and the eave direction marked. All 8, no selection.

**PREDICTION 10-1, STRIPES.** If the sawtooth is real, residuals are not random.
They form **STRIPES PARALLEL TO THE EAVE, alternating in sign, spaced at the
exposure**. Scored by eye on the images, which is what R6 requires, and reported
as present or absent per facet before any spectrum is computed.

**PREDICTION 10-2, THE SPECTRUM.** The 1D power spectrum of residuals taken
PERPENDICULAR TO THE EAVE shows a peak in the **4 to 7 in** band. Reported only
AFTER the images have been shown, so the images are read on their own terms.

**PREDICTION 10-3, AMPLITUDE.** If stripes are present, their peak-to-peak
amplitude is the butt thickness, so **3 to 6 mm, i.e. 0.12 to 0.24 in**. An
amplitude far outside that band means the stripes are something else, not
shingle courses.

**IF STRIPES ARE PRESENT, THIS BECOMES THE NON-CIRCULAR TEST.** Measuring their
SPACING and AMPLITUDE from the render gives exposure and step height **from the
cloud itself**, which yields an independent `arctan(t/e)` derived from the
building rather than from the disagreement. That is the test 5a wanted, available
without a site visit.

**IF THERE ARE NO STRIPES, THE REPORT SAYS SO PLAINLY.** Emmett's instruction,
recorded verbatim in substance: the hypothesis is his and he would rather it die
on an image than survive on a plot.

**THE PRECEDENT THAT DOES NOT SETTLE IT.** The same periodicity test on blob 0
found no peak at 5 in. **Blob 0 is different material at low slope**, so a null
there says nothing about the main facets. Recorded so the earlier null is not
quoted as if it had already answered this.

---

## THE THIRD POSSIBILITY, STATED PLAINLY BECAUSE IT IS INDISTINGUISHABLE

**The inclinometer procedure could be biased for some other reason entirely.**
A phone case with a lip, a consistent lean while placing it, a calibration
offset, or reading the instrument at an angle would each produce a systematic
offset in the same direction and of a similar size.

**A procedural bias looks IDENTICAL to the shingle-step hypothesis under test
5b**, because both predict a constant offset independent of pitch. 5b can
separate scale stretch from the other two; it cannot separate shingle step from
procedural bias. **Only 5a and 10 can**, because only they produce a number from
the geometry rather than from the comparison. If 10 finds no stripes and 5a's
measured geometry does not land near 1.83 deg, procedural bias becomes the
leading explanation by elimination, and the honest write-up is that the truth
data has an unquantified offset.

---

**What would refute the shingle-step hypothesis:**

- No stripes in the residual images, and no spectral peak in 4 to 7 in.
- Stripes present but spaced far from a plausible exposure, or amplitude far
  from 3 to 6 mm.
- The 5b ratio landing near 0.70, which is the scale-stretch shape.
- Measured `arctan(t/e)` on site landing outside 1.83 plus or minus 0.3 deg.

**Cost if wrong:** a wrong hypothesis costs one set of renders and one field
protocol. The expensive failure mode is the one explicitly forbidden above,
adopting a correction fitted to the disagreement, which would hide the error
instead of measuring it and would contaminate two held-out sites.

**Nothing is adopted from this. No correction is applied to any pitch, on any
facet, at any site, on the strength of this work.**

**Attribution:** the hypothesis, the sawtooth mechanism and its predicted
direction, the instruction that the correction must not be derived from the
disagreement, the two predicted shapes and which hypothesis implies each, the
demand that the render come before the spectrum, the reference band for 3-tab
and architectural shingle, the note that the blob 0 null does not transfer, and
the instruction to state the procedural-bias possibility plainly, are all
Emmett's. The quantitative 0.70 ratio and its scoring bands, the field protocol's
specifics, and the observation that 5b cannot separate shingle step from
procedural bias, are Claude's.
