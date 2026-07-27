### 2026-07-26: The size floor is kept as a junk-facet filter, and both thresholds are stated in transferable form

**Decision:** Recovered facets must clear two size floors: a minimum point
count and a minimum gross alpha area. Both are expressed relative to
quantities measured from the cloud, never as raw constants:

    MIN_AREA   = 3704 x spacing^2
    MIN_POINTS = 3704 x d,  d = median (n_points x spacing^2 / gross_area)
                            over the run's own MAIN facets

The floor is a SIZE gate only. A candidate that clears it is still held to
the same fit-quality bar as the main facets; quality is never relaxed.

**Why:** This floor entered as the proposed fix for RANSAC nondeterminism and
was FALSIFIED in that role (see 2026-07-26-ransac-nondeterminism-probability-1.md:
with the floor applied the facet count still varied 16 or 17 across 25 reps).
It is kept on separate merit. A plane fitted to too few points is not merely
small, it is not reproducible, and an irreproducible facet cannot be part of a
result anyone freezes. The floor removes facets the instrument cannot measure
twice.

Both values sit inside EMPTY BANDS in the data, which is what makes them
defensible. A threshold in a gap is a threshold whose exact value does not
matter: move it anywhere inside the gap and not one facet changes side, so it
cannot have been tuned to the answer.

The bands were re-measured on the current pipeline, because the state they were
originally measured on no longer exists. They could NOT be measured on the
canonical state, which was built with the floors applied and so contains
nothing below them by construction; measuring there would be circular. So the
full pipeline was re-run UNFLOORED and the unfiltered distribution measured:

    point count:  668 below the floor, 10,621 above    (band 15.9x wide)
    gross area:   0.0786 below, 0.7090 above           (band  9.0x wide)

Both floors sit inside their band. One correction to the earlier claim: the
0.019 / 0.378 figures quoted on 2026-07-23 were NET areas, but the gate tests
GROSS alpha area, which is all that exists at recovery time. Measured on the
gate's own quantity the band is wider, not narrower.

**Why MIN_POINTS could not stay a raw 2000 (Emmett, 2026-07-26):** *"Point
density depends on flight altitude and overlap; bungalow was flown separately,
so 2000 points covers a different physical patch there. A raw 2000 is a
per-site constant in disguise."* Every other length threshold in this pipeline
is already a multiple of measured point spacing for the same reason. The
transferable form gives 1933 points on big_house against the adopted 2000, a
3.4 percent difference.

That 3.4 percent was not waved away. The floor is pushed into RANSAC as its
min_points and also controls the peel loop's break condition, so it can change
WHICH planes get peeled, not just which survive. The full state was rebuilt at
1933 and diffed against the 2000 state: bit-identical, 0 field differences
across 25 facets, all 25 inlier index arrays equal, all scalars equal.
Adopting the transferable form changes nothing on this cloud.

Because the floor is now computed from each run's own main facets it varies by
dataset, so the ACTUAL VALUE USED is written into every run's output file
(Emmett, 2026-07-26: *"A threshold nobody can audit is not a threshold."*).

**Rejected:**
- MIN_POINTS as a raw count. Transferable in appearance only; see above.
- Dropping the point floor as redundant. Algebraically the transferable form
  IS the area floor restated, and on this cloud the point floor never rejected
  anything the area floor did not already reject. But the two gates come apart
  where density varies BETWEEN facets: a sparse, spread-out sliver can span
  enough alpha area to pass while holding too few points for a stable fit. The
  measured per-facet density spread here is 0.23 to 0.999, a factor of 4.3, so
  that window is real even though nothing landed in it. Dropping a safety
  floor on one cloud's evidence is not warranted.
- Relaxing the fit-quality bar for small facets. Never on the table. Size is
  negotiable; planarity is not, because a small enough patch of anything is
  planar.

**Evidence:** `reports/big_house/floors-2026-07-26.json` (unfloored run, both
bands, per-facet density, the equivalence test),
`floor-equivalence-mp1933-2026-07-26.json` (the 1933 rebuild).

**Honest limit:** the FORM of both thresholds transfers, but the shared
constant 3704 was still chosen on big_house. What defends its value is the
empty band, not the form. On a new cloud the band must be re-measured, and if
it has closed, that must be reported rather than the constant adjusted to
recreate one.

**Cost if wrong:** Too high a floor discards real small dormer facets and
undercounts area; too low a floor readmits facets that cannot be reproduced
and reintroduces the instability the floor exists to remove. The band width
is the margin: on this cloud the floor could move anywhere from 668 to 10,621
points without changing a single facet.
