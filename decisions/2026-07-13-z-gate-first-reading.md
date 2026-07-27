### 2026-07-13: Z gate first reading: a ~0.85 degree rigid tilt is the pitch uncertainty floor

**Decision:** The big_house cloud's georeferenced Z is accepted as the vertical reference per the gate protocol (worst-pair residual 0.84 degrees, limit 1.0), and 0.85 degrees is recorded as the uncertainty floor on every pitch from this cloud. This is not treated as a pass to be forgotten: it consumes roughly a third of the 2-3 degree pitch error budget and appears in the report footer.

**Why:** Three opposing facet pairs at distinct compass axes read residuals 0.10, 0.72, 0.84. A single rigid tilt predicts residuals proportional to the cosine between each pair's axis and the tilt direction; a tilt of ~0.85-0.9 degrees with maximum sensitivity near azimuth 20 fits all three. The residuals were stable under the robust trimmed refit (0.14/0.70/0.89 before, 0.10/0.72/0.84 after), which rules out facet clutter as their cause: this is genuine cloud lean from GPS-based georeferencing.

**Rejected:** Leveling the cloud now. The bisector instrument's own accuracy is bounded by the same pair asymmetries (~0.1-0.8 degrees), so leveling would trade a measured, reported bias for a partially unknown one. Also rejected: widening the gate (standing instruction).

**Evidence:** Two runs of measure_roof.py on big_house, 2026-07-13, before and after the trimmed refit. Caveats recorded as part of the evidence: (1) run 1's worst pair read 1.31 degrees, but its smaller facet (~3.7% of points, azimuth ~89) was not rediscovered in run 2, so the clutter-contamination hypothesis for that pair is UNTESTED, not proven. (2) Open3D RANSAC exposes no seed, so plane discovery is nondeterministic and facets near the min_points_frac floor flicker between runs; reproducibility fix pending.

**Cost if wrong:** If the tilt estimate is off, every reported pitch is biased by the difference. If the vanished facet returns with a large residual not explained by clutter, the floor rises and this entry gets reversed.
