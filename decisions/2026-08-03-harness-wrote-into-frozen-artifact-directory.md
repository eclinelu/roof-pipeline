### 2026-08-03: CONSTRAINT DISCOVERED THE HARD WAY: the review harness wrote INTO the frozen artifact directory it was reviewing. Reverted, and the guard test postdates the commit that did it

**Decision:** The 60 crop PNGs and the rewritten `review.html` that the
visual-pass harness placed inside
`reports/big_house/review/2026-07-30-grid-adopted/` are removed from that
directory, and `review.html` is restored to the `origin/main` blob
`f0e4873a147b`, byte-identical. Branch `review/harness` no longer changes any
path under `reports/`. The `--into-review` escape hatch that permitted the write
is **left in place and NOT fixed by this entry**, and is recorded below as an
open defect.

**Why:** A measuring instrument must not modify the thing it measures. That
directory is the canonical artifact for the adopted grid run. It is frozen
evidence, and `.gitattributes` pins its contents so that future byte-level
comparisons across machines mean something. A review page written beside the
renders also breaks the pass's own provenance rule: the folder's newest commit
becomes the pass's own, so the header would report that the renders were
produced by a commit that merely dropped a review page next to them. Provenance
answered with the wrong commit is worse than provenance refused, because it
looks authoritative.

**How it happened.** `guard_write_path` in `scripts/visual_pass.py` refuses any
path under `reports/` or `reviews/` for every caller, but it takes
`allow_artifact_dir=True` and, when set, returns the path unchecked before any
test runs. Commit `8f62576` used the flag and wrote 58 crops plus the rewritten
page into the artifact directory; `3fd06b5` added the two overview crops. The
guard blocks accidents, not intent, and its own docstring says so: "An accident
cannot reach it; only a flag can." **The guard test postdates the violating
commit.** `test_guard_refuses_artifact_and_review_directories` was added in
`8f62576` itself, the same commit that performed the write, so at no point did a
failing test stand between the harness and the frozen artifact.

**Why the revert was safe, stated as a measurement rather than a belief: no
render PNG was ever modified or deleted.** `git diff --name-status
origin/main...HEAD -- reports/` returned exactly one non-crop path,
`review.html`, with status M, and zero PNGs with status M or D. The harness only
ever added new files beside the renders and rewrote the page. The evidence
itself was never altered, which is what made a clean revert possible rather than
a reconstruction.

**Verified after the revert.** The frozen-artifact hash check recomputes the 8
main-facet digests from `canonical-2026-07-30-grid-adopted` and combines to
`e1df986ea6ac840be520663b398e9d6edd8d392a8dcc8a27dcd06a60eea64824`, equal to the
committed expected value and to the hash the artifact recorded about itself at
creation. The `.json` is pinned `text eol=lf` and git reports `i/lf w/lf`, so
the line-ending pinning is working; it does not affect the digest either way,
because the hash is taken over the `.npz` index arrays and the hex fields parsed
out of the JSON, never over the file's raw bytes.

**What had to happen before the revert could run.** The 29 per-facet overlap
fractions existed ONLY inside the rewritten `review.html`, and the `origin/main`
version of that file carries none of them. They were extracted to
`reviews/big_house/pass-r2-vs-grid-adopted.overlap.json` and committed and
pushed as `fd2fb28` BEFORE the revert. Because no history was rewritten,
`3fd06b5` also remains on the branch and on the remote, so the original page
stays retrievable independently of the extraction.

**OPEN DEFECT, recorded and NOT fixed.** `scripts/visual_pass.py` can still
write under `reports/`. The failing path is
`guard_write_path(path, allow_artifact_dir=True)`, which returns the path
unchecked, reached from the `--into-review` command-line flag and passed through
`build(...)` to the page write, the crop writes and the verdicts path. Every
other caller is still refused, and the test suite passes at 43 of 43, so the
suite does NOT cover this path in the sense of forbidding it; it asserts only
that the default refuses. This is left unfixed deliberately, so that the fix is
considered on its own terms rather than bundled into the pass that reverted its
damage. An unrecorded known defect is the thing to avoid, not an unfixed one.

Options noted and **none adopted**: remove the flag; point it at a copy or a
symlink of the renders rather than the renders themselves; or require the target
to contain no `canonical-*` file and sit outside any review render set.

**Cost if wrong:** low. The crops are build products that the harness
regenerates in one command, and this was verified rather than assumed. The
output directory was deleted outright and rebuilt after the revert, reproducing
58 of 58 crops byte-identically and all 29 overlap values with zero mismatches,
which also proves the harness does not depend on anything the revert removed.

**Attribution.** The violation is mine, from the session that built the harness.
The instruction to revert it, and the ordering that required the evidence be
extracted and pushed before anything was reverted, are Emmett's.
