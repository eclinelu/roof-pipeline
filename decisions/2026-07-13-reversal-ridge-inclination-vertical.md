### 2026-07-13: REVERSAL: Z is tilted 1.25 degrees; ridge inclination replaces the symmetry gate as the primary vertical reference

**Decision:** Georeferenced Z is rejected for big_house: measured tilt 1.25 degrees, uphill azimuth 81.3, from the ridge instrument. The cloud is leveled by this vector before all measurement. Ridge-line inclination becomes this project's primary vertical reference; the opposing-facet symmetry residual is demoted to an asymmetry report, and only ridge-validated pairs count as instruments at all.

**Why (the reasoning is the deliverable here, not the number):**

1. The symmetry gate was a flawed instrument, and specifically why: it assumed any two facets facing opposite directions form a gable. Pair 0,2 met at mid-height, not at a ridge; it was never a gable pair, so its 0.10 residual was never evidence about anything, and the earlier 0.85 conclusion was anchored to it. The failure mode is a plausible instrument reading confidently and being wrong, not a noisy number.
2. The ridge method is better because it assumes less. Ridges are level in the real world. Two ridges running roughly orthogonal fully determine which way is up, with no symmetry assumption anywhere. That is why it can be trusted where the gate could not.
3. The cross-validation is what makes it trustworthy: the ridge fit PREDICTED pair 6,7's symmetry residual at 1.24 degrees, and the independent symmetry measurement read 1.17. Two unrelated instruments agreeing is the evidence. Without that, this is just a second story replacing a first one.
4. Facet 7 was innocent. The contamination hypothesis was wrong. The trimmed refit stays (cleaner fits, cleaner membership) but it did not fix anything and is not credited with it.
5. Tilt and building asymmetry are now separated, and that separation is the real result. 1.25 degrees is instrument error and is correctable. The ~1.2 degrees surviving on pair 1,3 after leveling is the house being genuinely asymmetric, which is normal on an old roof and is not an error to chase to zero. It is reported as a measured property of the building.

**Rejected:** Leveling from the facet-normal bisector (it assumes exactly the symmetry that pair 1,3 measurably lacks). Widening the gate (standing instruction).

**Evidence:** Ridge inclinations +1.239 degrees (ridge az 88.6) and -0.157 (az 178.5), ~1,400 contact points each; contact-height fractions 0.95/0.95 for both true ridge pairs versus 0.48/0.55 for pair 0,2; the cross-validation in point 3. Diagnostic runs of 2026-07-13.

**Cost if wrong:** If the ridge extraction is biased (asymmetric contact zones, curved ridge lines), the leveling bakes that bias in. Checked empirically: after leveling, re-measured ridge inclinations must read ~0.

**Reverses:** 2026-07-13 "Z gate first reading: a ~0.85 degree rigid tilt is the pitch uncertainty floor."
