### 2026-07-29: RESULT: the shingle-sawtooth hypothesis is REFUTED on the image. The 1.83 deg bias is not what we thought

**Scored against `decisions/2026-07-29-preregistration-pitch-bias-mechanism.md`,
committed and pushed at `7a64185` before 5b was run.**

**Nothing adopted. NO CORRECTION APPLIED to any pitch, on any facet, at any
site.**

---

## SCORECARD, BEFORE ANY INTERPRETATION

    10-1  stripes visible in the residual images        FAILED
    10-2  spectral peak in the 4 to 7 in band           AMBIGUOUS, weak
    10-3  stripe amplitude 0.12 to 0.24 in              FAILED
    5b    shape discriminator, shallow/steep ratio      NEITHER SHAPE FITS
    5a    field geometry prediction                     NOT YET RUN (site visit)

**Evidence:** `reports/big_house/facet-residuals-2026-07-29.png`,
`facet-residuals-spectrum-2026-07-29.png`, `pitch-bias-score-2026-07-29.json`.

---

## 10-1: NO STRIPES. SAID PLAINLY, AS ASKED

48 x 48 inch windows at the densest part of each main facet body, 0.25 inch
cells, all 8 facets. Point spacing is 0.21 in and a course is about 5 in, so a
course spans 24 point spacings and about 20 image cells. **The resolution can
show a course. There are no stripes.**

What the residuals actually show is **large-scale structure, 10 to 40 inches,
often diagonal**: broad warps rather than periodic banding. Nothing at the
shingle scale in any of the 8.

**A false negative was avoided, and it nearly was not.** The first version of
this render drew each facet whole. Those panels span 300 to 1500 inches, so a
5 inch course was at or below one pixel and "no stripes" would have been a
statement about the figure rather than about the roof. That is the same failure
class as silent-failure rows 7 and 8, a test structurally blind to the thing it
checks, and it was caught by asking what the panel's resolution actually was
before reading it.

---

## 10-3: THE AMPLITUDE FAILS BY AN ORDER OF MAGNITUDE, AND THIS IS THE CLEANEST RESULT

Predicted: 0.12 to 0.24 in, being a 3 to 6 mm butt thickness.

Measured, taking the spectral peaks entirely at face value: **0.014 to 0.034
in**, on all 8 facets.

**Five to seventeen times too small.** Even granting every ambiguous peak in
10-2 as real, there is not enough amplitude in the cloud at the shingle scale to
produce a 1.83 deg tilt from a sawtooth. A 4.6 mm step over a 5.625 in exposure
is 0.18 in of relief; the cloud shows at most 0.03 in.

---

## 10-2: AMBIGUOUS, AND A STATISTIC OF CLAUDE'S THAT WAS INVALID

The spectra are **RED**: power rises monotonically with wavelength from 2 in to
12 in, with no bump in the pre-registered band.

**The first statistic reported was wrong and is recorded as such.** Peak power
in 4 to 7 in divided by the median of flanks spanning 2.5 to 4 and 7 to 12
returned values up to **318** on facet 0. That number measures the SLOPE OF THE
BACKGROUND, not a peak: against a monotonically rising spectrum, the maximum in
the band sits at the long-wavelength edge while the flank median is dragged down
by the low-power short-wavelength side. It would have returned a large number
whether or not any peak existed.

Replaced with a valid test: fit the background trend in log-log using the
FLANKS ONLY, then measure the excess of the band above that extrapolation.

    facet          0     1     2     3     4     5     6     7
    excess (dB) +9.0  +1.4  +0.6  +2.6  +6.1  +3.1  +5.1  +2.6
    angle from
    slope (deg)  0.0  12.5  45.0  39.8   0.0   0.0   0.0   0.0

**Read cautiously rather than as a positive.** Five of the eight wavevectors sit
at EXACTLY 0.0 deg, on the image axis. A separable Hann window leaves residual
leakage along the axes, so an exactly-axial peak is what an artifact looks like,
not what a physical signal looks like. Combined with 10-1 showing nothing and
10-3 failing by a factor of 5 to 17, **the honest reading is that 10-2 does not
rescue the hypothesis.**

The invalid figure is retained in the artifact as `naive_ratio_INVALID` so the
correction is auditable rather than quietly overwritten.

---

## 5b: NEITHER SHAPE FITS, AND THE TEST HAS LITTLE POWER

    cluster    facets      mean pitch   mean offset
    shallow    0, 2, 4, 5    19.58 deg    +1.9818 deg
    steep      1, 3, 6, 7    31.92 deg    +1.6687 deg

    observed ratio shallow/steep    1.188
    predicted, CONSTANT OFFSET      1.00   (band 0.90 to 1.10)
    predicted, SCALE STRETCH        0.70   (band 0.60 to 0.82)

    VERDICT, per the bands fixed before the number was computed:
    NEITHER SHAPE FITS

**The asymmetry in that verdict matters and is stated rather than buried.**
1.188 misses the constant band by 0.09 and misses the stretch band by 0.37.
**Vertical scale stretch is excluded with some confidence; constant offset is
missed narrowly and remains the better of the two.**

**And the test has little power, which is a property of the data.** The
within-cluster spread is large relative to what is being detected: the steep
cluster's own offsets run 1.067 to 2.087 deg, a spread of 1.02 deg, while the
two hypotheses differ by only 0.30 in the ratio. With four facets per cluster,
the standard error on each cluster mean is about 0.19 deg. **This test could
never have separated the hypotheses cleanly on eight facets, and that should
have been computed when it was designed rather than after it was run.**

Scatter after removing a constant, **as a measurement only and with no
correction adopted**: sd 0.382 deg, range -0.758 to +0.363 deg.

---

## WHERE THIS LEAVES THE 1.83 DEG BIAS

**The hypothesis was Emmett's and he asked for it to die on an image if it was
going to. It did.** The cloud does not contain the surface relief the sawtooth
requires, by an order of magnitude, and the residuals show no periodic structure
at the shingle scale.

**Elimination now points at the third possibility, which the pre-registration
required be stated plainly:** the inclinometer procedure is biased for some
other reason. A phone case lip, a consistent lean while placing the instrument,
a calibration offset, or reading it at an angle would each produce a constant
offset in the observed direction and size, and 5b cannot distinguish any of them
from the shingle step.

**What this does NOT establish.** It does not prove the truth data is wrong. It
proves the cloud does not show the mechanism that was proposed to explain the
disagreement. The pipeline could still be reading steep for a reason not yet
considered.

**5a is NOT cancelled and becomes more important, not less.** A site visit
measuring exposure and butt thickness with a rule and calipers gives
`arctan(t/e)` from the building. It is now the only remaining test that can
produce a number independent of the disagreement, and if it lands near 1.83 deg
after this refutation, that would be a genuine surprise worth taking seriously.
**A second independent instrument on the same facets would settle the procedural
question directly and is worth more than another statistical pass over eight
numbers.**

---

**Rejected:**

- **Reading the +9 dB excess on facet 0 as confirmation.** It is axis-aligned,
  unsupported by the image, and contradicted by an amplitude 5 to 17 times too
  small.
- **Keeping the naive peak/background ratio.** Invalid against a red spectrum.
- **Widening the 5b bands until 1.188 lands inside one.** The bands were fixed
  before the number existed.
- **Adopting any correction.** Forbidden by the pre-registration and by
  `2026-07-14-ground-truth-audit-only.md`. A correction fitted to the size of
  the disagreement would guarantee agreement while measuring nothing, and it
  would contaminate two held-out sites.

**Cost if wrong:** if the sawtooth is real but the cloud smooths it below 0.03 in
through reconstruction rather than measurement, this refutes the SIGNATURE
without refuting the mechanism. That is a real possibility and the honest
statement of it is that the test constrains what the CLOUD shows, not what the
shingles do. 5a is the test that does not have this weakness.

**Attribution:** the hypothesis, the sawtooth mechanism and its direction, the
instruction that the correction must never be derived from the disagreement, the
two predicted shapes, the demand that the render precede the spectrum, the
instruction to state the procedural-bias possibility plainly, and the
instruction to say so plainly if there are no stripes, are all Emmett's. The
resolution failure caught in the first render, the invalid spectral statistic and
its replacement, the reading that axis-aligned peaks are leakage, and the power
analysis showing 5b could not have separated the hypotheses on eight facets, are
Claude's.
