### 2026-07-12: Scale comes from one tape-measured ground distance

**Decision:** Real-world scale is locked using a single tape-measured distance captured on site, not from GPS.

**Why:** The reconstruction has correct shape and proportion but is off by a single scale multiplier. One true length resolves it. Meter-grade GPS is far too coarse for a single building (20 to 40 m baseline gives roughly 3% linear error, which becomes roughly 6% area error, since area scales as the square of the linear error). Measuring the longest available clean edge dilutes tape error: 2 cm on 10 m is 0.2%.

**Rejected:** GPS-derived scale, on accuracy. Rejected: multiple control points, as unnecessary for a single-multiplier correction.

**Evidence:** Ground distance measured on site during the July 11-12 capture.

**Cost if wrong:** Area error scales as the square of the scale error. This is the single most sensitive input in the pipeline.
