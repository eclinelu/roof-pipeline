### 2026-07-26: Open3D's RANSAC is nondeterministic under a fixed seed; `probability=1.0` becomes the default

**Decision:** `find_roof_planes` and `discover_facets` default to
`probability=1.0`, which disables Open3D's adaptive early stop and forces the
full iteration count. This makes the whole segmentation pipeline reproducible.
`scripts/measure_roof.py` runs at 1.0 as well, since it does not pass the
argument.

**Why:** A fixed seed did not give a fixed answer. Open3D 0.19's `segment_plane`
evaluates candidates in PARALLEL, and its `probability` parameter is an adaptive
early stop that quits as soon as a running estimate, based on the best inlier
count found so far, says it has probably found the best plane. "Best so far"
depends on the order threads happen to finish, which the seed does not control.
In Emmett's words, on why 1.0 is the default rather than an argument or an
environment variable: *"The alternative fixes were an env var
(OMP_NUM_THREADS=1) or a non-default argument. Both fail the same way: they are
invisible at the call site and a caller who forgets silently gets the
irreproducible path. A default cannot be forgotten."*

**Rejected:**
- `OMP_NUM_THREADS=1`. Measured to work (it stabilised every variant, including
  the baseline), but it must be set before Open3D is imported, is invisible in
  the code, and costs the parallelism on the large main-facet fits too.
- A hard minimum facet size as the determinism fix. This was the original
  hypothesis and it was FALSIFIED: with the floor applied the facet count still
  varied (16 or 17 across 25 reps). It cut the number of distinct outcomes from
  four to two, which reads as partial success and is exactly the trap; the
  instability was never confined to the smallest facets (facet 15, at 53,023
  points, still moved 0.238 deg). The floor is retained on separate merit as a
  junk-facet filter, not as the reproducibility mechanism.
- Doing nothing and reporting the wobble as uncertainty. A pipeline that cannot
  reproduce its own output cannot be frozen, which is the whole basis of the
  pre-registration method.

**Evidence:** `reports/big_house/ransac-nondeterminism-2026-07-25.json`,
`determinism-2026-07-25.json`, `determinism-2026-07-25-1thread.json`,
`full-determinism-2026-07-25.json`, and the T1/T2 thread-invariance run
`thread-mt.json`. Key measurements: a 664-point facet returned 3 distinct planes
over 25 identically-seeded reps (spread 0.043 deg) while a 1,538,098-point facet
returned 1 over 8 reps; two identical full runs produced 26 and 25 facets;
baseline facet counts across 25 reps were [17, 18, 19, 20] multithreaded and a
stable [18] pinned to one thread; at `probability=1.0` the full pipeline gave 26
facets over 5 reps, bit-identical in point counts and 0.0 deg pitch spread.

**The frozen result is NOT restated.** At `probability=1.0` the eight main
big_house facets match `preregistered-2026-07-18.json` to 0.00043 deg worst
case, which is the SAME worst-case delta the old default produced. Main-facet
discovery was already bit-identical, because a 200k-point subsample with
dominant planes is over-determined enough that the early stop never faces a
close call. Pre-registration evidence is intact and the 313.188 cu^2 total
stands.

**What it DOES supersede:** the 2026-07-23 26-facet state is permanently
unrecoverable, and the deterministic pipeline produces a different decomposition
rather than reproducing it. Blob 0 now resolves into two clean facets (62,496
points at 23.59 deg, quality 0.758; 14,099 points at 10.51 deg, quality 1.597)
where the old run produced one bloated fit plus a 109,972-point spanning plane
rejected at quality 3.927. The quality bar was correct throughout and was not
touched. All Task 5 dormer-level numbers must be re-derived.

**Cost if wrong:** Wall-clock only, measured in T2. Forcing the full iteration
count removes an optimisation that was only ever safe when the answer was
unambiguous. If a parallel reduction can still produce exact ties, determinism
could break again in principle; 25 reps showed no such case, and single-threading
remains the belt-and-braces fallback.
