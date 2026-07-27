### 2026-07-27: A probe run with altered parameters does not measure the production configuration. Standing rule, plus one claim withdrawn.

**Why this exists alongside the existing correction.** The arithmetic is already
corrected in `2026-07-26-correction-min-pitch-exclusion-figure.md` (19.04 cu^2 /
166,015 pts -> 0.326 cu^2 / 2,623 pts). This entry does two things that one does
not: it states the root cause as a STANDING RULE for clouds not yet analysed, and
it withdraws a SECOND claim that came from the same contaminated source and has
not yet been flagged.

---

**PART 1, the standing rule.**

`find_roof_planes` does not end when the peeling loop ends. It ends with a
REASSIGNMENT PASS: every point in every KEPT plane is pooled, each point is
handed to its nearest plane, and each plane is refitted to its final members. The
pitch window therefore does not merely select among planes. It decides WHO IS IN
THE POOL.

The consequence, stated generally: **widening the pitch window changes the
membership and the fitted normal of planes that would have survived either way,
not only which planes survive.** A run with altered parameters is not the
production run minus a filter. It is a different configuration that happens to
share most of its parameters, and any plane it reports is a plane that only
exists under it.

The rule that follows: to ask "what would relaxing gate G recover?", relax G and
**re-run the pipeline**, then diff the outputs. Never re-peel a residual with the
gate opened and measure what comes back. The recovery-pitch sweep did it the
right way and that is why it caught the error.

**A second instance, measured 2026-07-27, different mechanism, same lesson.**
Blob 0's candidate was needed at full precision. The obvious approach, re-peeling
blob 0 outside `recover_facets` with identical arguments, was run and compared:

    inside recover_facets   1 plane kept, no reassignment, 162,938 pts, quality 2.94820  -> FAILS the bar
    standalone repeat       2 planes kept, reassignment RAN, 157,358 pts, quality 2.91498 -> PASSES the bar

Same 180,861 candidate points, same arguments, same `probability=1.0`. The only
difference is the position in Open3D's global RANSAC stream. The same physical
surface gets the opposite verdict.

This is NOT a determinism failure of the pipeline. The production sequence is
fixed and reproduces exactly: verified the same day, all 8 main facets
bit-identical to `canonical-2026-07-26-r2` as index sets, and blob 0's candidate
reproducing `blob0-rejection-2026-07-26.json` to the logged digit. It is a
property of measuring OUTSIDE that sequence. The correct instrument was to
capture the value where production code computes it (wrap `cov.facet_quality` for
the duration of the call, restore it immediately) rather than to re-derive it.

**This will recur on bungalow and roger.** Both are unanalysed, both will raise
the same "what is this threshold costing us?" question, and the same wrong
instrument is the natural first reach.

---

**PART 2, a claim withdrawn: blob 0 at quality 2.833.**

`2026-07-26-min-pitch-definition-not-filter.md` states that blob 0's large
near-flat plane "CLEARS the quality bar (2.833)" and uses that to separate it
from the 4.04 degree spanning artifact, which fails at 3.076. That 2.833 came
from the SAME contaminated re-peel that produced the 19.04 cu^2 figure: it is the
first row of the same table, 147,505 pts at 3.743 degrees.

Under the real recovery pass the same physical surface is **162,938 points at
3.821 degrees, quality 2.94820 against a bar of 2.94800. It FAILS.**

Status: **NOT REFUTED, NO LONGER SUPPORTED.** The underlying claim, that blob 0's
plane is well-fitted enough to be a real roof surface rather than an artifact,
may still be true. The number offered as proof of it does not survive its own
source. A future reader must not carry 2.833 forward, and must not read "clears
the bar" as an established fact about blob 0.

**The other half of that paragraph stands.** The argument that blob 0's plane is
confined to a single residual region rather than threaded across the building,
unlike the spanning artifact, does not depend on the contaminated re-peel and is
independently confirmed: blob 0 has ZERO plan-cell overlap with 5 of the 8 main
facets and at most 0.04 percent with any of them, against the artifact's
signature of touching all 8.

---

**`min_pitch = 5` is unaffected by either part.** The spanning-artifact argument,
the A3 quality evidence, the 1.8 degree plateau limit and the low-slope label all
rest on their own measurements.

**Cost if wrong:** none beyond the record. Every figure above is on disk with the
run that produced it.

**Evidence:** `reports/big_house/quality-bar-tie-2026-07-27.json` (both the
production reading and the stream-position re-peel, with all five cross-checks
recorded pass/fail), `blob0-rejection-2026-07-26.json`,
`recovery-pitch-sweep-2026-07-26.json`.

**References, edits neither:** `2026-07-26-min-pitch-definition-not-filter.md`
(withdraws one figure from it), `2026-07-26-correction-min-pitch-exclusion-figure.md`
(the arithmetic correction, already logged).

**Attribution:** Emmett directed both parts and stated the reusable-point
framing. The 2026-07-27 re-peel evidence and the wording are Claude's.
