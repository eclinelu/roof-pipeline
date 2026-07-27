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
