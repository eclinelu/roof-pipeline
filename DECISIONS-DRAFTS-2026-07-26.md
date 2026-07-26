# DECISIONS.md drafts, 2026-07-26 — NOT YET WRITTEN

Emmett asked for these to be drafted and shown before writing (Task 6 message,
"DECISIONS.md, DRAFT AND SHOW ME BEFORE WRITING"). Nothing here has been added
to `DECISIONS.md`. Only the **Current state** block there was updated, which is
routine maintenance.

Paste-ready. Newest-at-top order, so insert in the order shown, directly under
the `_Append only..._` line. Delete this file once they are in.

**Sourcing note.** Entry 1's *Why* is quoted from the docstring Emmett wrote
himself in `roofkit/segment.py`. Entries 2 and 3 are quoted from his Task 5 and
Task 6 instructions. No reasoning below is invented; anything I could not source
to his own words is marked `[NEEDS EMMETT'S WHY]`.

---

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
`full-determinism-2026-07-25.json`, and Emmett's own T1/T2 thread-invariance run
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

---

### 2026-07-25: Facet geometry is persisted every run (R1), and actionable diagnostics go to a file (R2)

**Decision:** Two permanent standing rules. **R1:** every run writes per-facet
plane coefficients and inlier point indices to `reports/<dataset>/`, so any run
is exactly replayable from its own output, independent of whether the fit is
deterministic. **R2:** any diagnostic Emmett is expected to act on is written to
a file under `reports/<dataset>/`, never to stdout only.

**Why (Emmett's words):** For R1, *"Summary rows alone are not enough: the
2026-07-23 state is unrecoverable purely because geometry was never saved. Any
run must be replayable exactly from its own output, independent of whether the
fit is deterministic."* For R2, *"The pairwise matrix from Task 4 went to
stdout, the log was deleted, and it is now lost. That does not happen again."*

The two rules cover different failure modes and the same week produced both. R2
lost a diagnostic that could have been regenerated. R1 addresses the worse case
found immediately afterwards: the underlying state could not be regenerated
either, because the fit that produced it was nondeterministic and its geometry
existed nowhere. Persisting geometry makes replay independent of reproducibility,
so it keeps working even if a future library reintroduces nondeterminism.

**Rejected:** Relying on determinism alone to make runs replayable. The
determinism fix (2026-07-26 entry) is a property of one library version and one
set of arguments; R1 holds regardless.

**Evidence:** The Task 5 reconstruction attempt. 25 of 26 facets could be
re-derived, the 26th could not, and the comparison file held only pitch, gross,
occluded and net per facet, which is not enough to reconstruct a plane.

**Cost if wrong:** Disk only. Inlier index arrays for a 9.3M-point cloud are
tens of megabytes per run.

---

### 2026-07-25: A merge requires coplanarity AND spatial adjacency

**Decision:** Two facets may be merged only if they are BOTH coplanar (small
normal-angle difference and small plane offset) AND spatially connected (their
plan footprints touch or overlap). Plane agreement alone is necessary but not
sufficient.

**Why (Emmett's words):** *"Only 19&22 is a real merge. Their plan boxes overlap
and their plane separation is 0.00058 cu, sub-millimetre. Blob 7 and blob 10 are
one physical dormer split into two residual blobs and fitted twice. 24 sits ~6 cu
away in X. It is coplanar but physically separate, almost certainly an identical
dormer elsewhere on the same slope. Merging it would report one facet where two
dormers exist... Identical dormers in a row will always look coplanar and must
remain separate facets."*

This is a property of houses, not a tuning choice: repeated identical dormers on
one roof slope are the normal case, and every one of them is coplanar with every
other by construction. A coplanarity-only rule would collapse them and
under-report facet count on exactly the roofs where dormers matter most.

**Rejected:** Merging on plane agreement alone, which the Task 5 pairwise matrix
would have supported: facets 19, 22 and 24 were mutually flagged (angles 0.413,
0.633 and 0.817 deg; offsets 0.00058, 0.01690 and 0.02302 cu, all well inside 2x
the assignment band). Taking that at face value would have merged three facets
into one and reported a single dormer where two exist.

**Evidence:** `reports/big_house/pairwise-2026-07-23.json`. Facets 19 and 22 sit
at short X[77.9, 79.8] and X[77.6, 78.7] with overlapping plan boxes; facet 24 is
at X[84.3, 85.6], roughly 6 cu away, at the same Y band and the same pitch.
Blobs 1 through 5 each produced exactly 2 facets with opposing normals, which is
5 gabled dormers correctly resolved and must not be touched.

**Status:** the rule is decided; it is NOT yet implemented. It must be applied to
the re-derived canonical facet state, since the facet indices above belong to the
superseded 2026-07-23 state.

**Cost if wrong:** If the adjacency test is too strict, one physical surface split
across two non-touching residual blobs stays split and facet count is
over-reported. If too loose, distinct dormers collapse. The adjacency tolerance
itself is `[NEEDS EMMETT'S WHY]`: no value has been chosen, and the choice should
come from the observed gap between the 19/22 overlap and the 19/24 separation
rather than being picked in the abstract.
