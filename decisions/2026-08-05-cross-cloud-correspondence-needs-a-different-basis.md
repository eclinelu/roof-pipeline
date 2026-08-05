### 2026-08-05: The visual pass's point-index correspondence is INVALID between artifacts from different clouds, and it fails silently. A guard is required; a geometric basis is approved but unbuilt

**Decision:** Index-set correspondence is declared valid ONLY between artifacts
that share a source cloud. A cross-cloud pass must ASSERT that precondition from
the recorded `replay.source_cloud_sha256` and fail loudly when it does not hold.
Where a cross-cloud comparison is genuinely wanted, it uses a DIFFERENT
correspondence basis -- world-space footprint-cell overlap on one shared XY grid,
still grouped by mutual best match -- and the basis in force is DECLARED on the
page. Falling back to it silently is forbidden. Emmett approved this shape on
2026-08-05; it is recorded here and is NOT yet built, because the ultra pass it
was needed for is held (see
`2026-08-05-planarity-score-leaves-its-range-and-depends-on-enumeration-order.md`).

**Why:** The pass's central invariant, logged at
`2026-08-03-visual-pass-correspondence-by-overlap.md`, is that facet
correspondence comes from point-index-set overlap and from nothing else. That is
correct, and it is what makes merges, splits and vanished facets fall out of the
arithmetic. But it carries an UNSTATED precondition: both artifacts must index the
SAME point array. The stored indices are row numbers into one cloud's leveled roof
array, so they are only meaningful inside the numbering that issued them.

`canonical-2026-07-30-grid-adopted` records `source_cloud_n: 9293239`. An ultra
artifact indexes a different, roughly 4x larger array. Row 5000 in each names a
different physical point, so `len(a & b)` at `scripts/visual_pass.py:303` would
intersect two unrelated numberings. It does not error. It returns plausible
nonzero counts and builds plausible-looking 1-to-1 rows, and every existing
anti-null passes on that input: `load_artifact` checks only that the indices are
integers, non-duplicate, and within THEIR OWN cloud's range, and the count matches
the json. The artifact already records `source_cloud_sha256`, and the harness
never reads it.

The self-test cannot catch this by construction. It permutes ONE artifact against
itself, so both sides always share a source cloud; the precondition it needs to
test is the one thing it holds fixed. That is the general shape worth keeping: a
self-comparison test cannot detect a fault in an assumption it does not vary.

**Rejected:**

- **Refuse cross-cloud passes entirely** and review the ultra artifact on its own.
  Rejected by Emmett as too restrictive: it gives up the side-by-side comparison
  that is the whole point of a pass, and cross-cloud comparison is exactly what
  the ultra work is for.
- **Let the geometric basis kick in automatically when the hashes differ.**
  Rejected. A silent basis switch reproduces the original defect one level up: the
  page would look identical while the meaning of every overlap number changed. The
  basis must be stated on the page.
- **Pick a distance cutoff and pair facets by centroid proximity.** Rejected for
  the same reason the original design rejected an overlap cutoff: it introduces a
  tuned threshold with no principled value, and one tuned to make this pass look
  tidy will mis-group the next. Mutual best match is a comparison, not a
  magnitude, and is kept for that reason.

**Evidence:** Read directly from the code and the artifact, 2026-08-05.
`correspond()` at `scripts/visual_pass.py:303` computes `len(a & b)` on raw index
sets. `grep` over `scripts/visual_pass.py` returns exactly one `source_cloud`
reference, `source_cloud_n` at line 197, used only as a per-artifact upper bound.
`canonical-2026-07-30-grid-adopted.json` carries
`replay.source_cloud_sha256 = 1e04669c...b27335` and `source_cloud_n = 9293239`.
No cross-cloud pass has been run, so the failure is demonstrated by construction
rather than by a wrong result already produced -- which is the point of catching
it now.

**Cost if wrong:** If the geometric basis turns out to be the wrong model, the
cost is one instrument change, reversible, with no artifact depending on it yet.
If the guard had NOT been added and a cross-cloud pass had been run, the cost is a
complete pass record -- rows, overlap fractions, verdicts, graded by hand -- that
reads as evidence about how ultra changed the segmentation while actually
reporting an artifact of two unrelated numberings. Verdicts are expensive to
produce (47 in the last pass) and there would be no signal afterwards that they
were meaningless.
