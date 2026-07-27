### 2026-07-27: STANDING RULE: every diagnostic carries an assertion that fails loudly if it is measuring the wrong thing

**Decision:** Every probe, diagnostic and analysis script in this project MUST
carry at least one assertion that would FAIL LOUDLY if the probe were measuring
the wrong thing, and that assertion must be built from something known
INDEPENDENTLY of the probe's own result. The check is written into the output
file with its pass/fail state, not merely evaluated at runtime.

**Why: four silent failures in one day, none of which raised an error.** This is
logged as a pattern rather than as four incidents, because the incidents have
nothing in common except the failure mode, and the failure mode is the thing
that will recur.

    1. THE CONTAMINATED RE-PEEL
       Re-running an identical RANSAC call outside the production sequence
       returned a DIFFERENT plane, because Open3D draws from one global stream
       and the standalone call started at a different position in it. Output: a
       well-formed plane with a plausible quality of 2.91498, which happened to
       fall on the opposite side of the accept/reject boundary from the real
       answer of 2.94820.

    2. THE EROSION ON AN UNFILLED MASK
       A distance transform run on a hole-riddled occupancy mask measured
       distance-to-the-nearest-capture-hole rather than distance-from-the-edge.
       Output: an interior-only quality of 2.90857 that cleared the bar. It was
       the density correlation re-measured under another name, and it pointed
       the entire investigation at a mechanism that a later probe refuted.

    3. THE RANGE ACROSS TWO AXES
       `np.ptp` applied to an (N, 2) coordinate block returns the range across
       BOTH columns at once. In UTM that is northing minus easting, about four
       million cloud units, so every sample landed off the building. Output: a
       perfectly well-formed EMPTY LIST. Zero ridges on a pitched roof.

    4. THE EXIT CODE THAT WAS NOT THE EXIT CODE
       A run was piped through `tail`, so the reported exit status was `tail`'s
       and not the program's. Two runs that had died with a MemoryError were
       reported as exit 0. This belongs in the same list: it was a check that
       LOOKED like verification and verified nothing.

None of the four raised an exception. None produced a NaN, an infinity, or a
malformed value. All four produced output that formatted cleanly and read
plausibly, and three of them were reported before being caught.

**The common shape.** A wrong answer that is well-formed is invisible to every
generic defence: type checks pass, serialisation succeeds, plots render, and the
number sits in a believable range. Nothing in the machinery can tell that the
quantity being computed is not the quantity intended, because at the level of
arrays and floats it is a perfectly good computation of something else.

The only thing that catches it is a fact known INDEPENDENTLY of the computation.
Not a self-consistency check, which a wrong-but-coherent pipeline passes
happily. An external fact:

    a pitched roof HAS ridges              -> zero intersection lines is a bug
    a facet's points lie inside its
      own bounding box                     -> a fit that says otherwise is wrong
    an eroded region is a SUBSET of the
      uneroded one                         -> a superset means the mask is wrong
    a subset cannot score worse than its
      superset under the same estimator    -> it did, so the estimator differed
    this run must reproduce the canonical
      state it claims to extend            -> compared as index sets, bit for bit

**THIS GENERALISES AN INSTINCT THE PROJECT ALREADY HAD, AND THAT MATTERS MORE
THAN THE RULE.** Two existing habits are the same idea applied narrowly, and
both were already earning their keep before this entry was written:

- Reporting at full precision rather than three decimals. The 2.948-against-2.948
  "tie" dissolved the moment the numbers were printed as `repr`: a real margin
  of 2.0e-4 and 458,701,932,548 ulps apart, which killed the `>` versus `>=`
  reading outright. Rounding had been hiding a decisive fact.
- Embedded cross-checks in probe output. Every 2026-07-27 probe compared its own
  main facets against `canonical-2026-07-26-r2` as index sets and its own blob 0
  candidate against `blob0-rejection-2026-07-26.json`. One of those checks FAILED
  on first run, and that failure is what exposed the contaminated re-peel. It was
  not a bug in the check; it was the probe correctly reporting that its own
  method was unsound.

The rule is those two habits made general and mandatory, not a new discipline
imported from outside.

**How to choose the assertion, since a badly chosen one is worse than none.**
It must be independent of the result. A check derived from the same computation
it is checking will pass whenever that computation is self-consistently wrong,
and its passing then reads as confirmation. Prefer, in order: a comparison
against a previously committed artifact; a physical or domain fact about the
building; a mathematical invariant of the operation (subset, monotonicity,
conservation); a magnitude range stated BEFORE the run.

**When an assertion fails, the first hypothesis is that the NEW WORK is wrong,
not that the check is wrong.** Instance 2 above was caught exactly this way, and
the natural instinct in the moment was to relax the check.

**Rejected:**
- Relying on code review to catch these. All four passed review by the person
  who wrote them, in the same session, minutes after writing them. Three of the
  four were caught by measurement, and the fourth by a domain fact.
- A generic validity layer (type checks, NaN guards, range clamps). Every one of
  these four failures produces valid types, finite numbers, and plausible
  ranges. A generic layer cannot know what was intended.
- Applying the rule only to production code. Instance 2 reintroduced, inside a
  probe, a defect that had already been found and fixed in production on
  2026-07-26. Diagnostic code is where reported numbers come from, so it gets
  the same treatment. "It is only a probe" is precisely when the guard is
  skipped.

**Cost:** a few lines per probe, and occasionally a run that stops instead of
producing a plot. Against that, three of today's four failures reached a written
report before being caught, and one of them redirected a whole line of
investigation into a mechanism that was later refuted.

**Cost if wrong:** the rule is additive and cannot make a correct probe
incorrect. The real risk is a badly chosen assertion creating false confidence,
which is why the independence requirement above is part of the rule rather than
advice.

**Evidence:** `reports/big_house/quality-bar-tie-2026-07-27.json` (the
full-precision comparison and the five embedded cross-checks, one of which
failed on first run); `reports/big_house/boundary-erosion-population-2026-07-27.json`
(the refutation that exposed instance 2); `decisions/2026-07-27-reassignment-pass-contamination.md`
(instance 1); `decisions/2026-07-27-erosion-refuted-and-interior-retraction.md`
(instance 2 and its retraction).

**Attribution:** the decision to log this as one pattern rather than three
incidents, the standing rule, the three worked examples of independent facts,
and the instruction to state that the precision and cross-check habits are the
right instinct being generalised, are all Emmett's, stated directly. The
four-instance write-up and the guidance on choosing an assertion are Claude's.

**APPENDED THE SAME DAY: a FIFTH instance, and it was in the review instrument
itself.** (Emmett called this the fourth; the entry above already enumerates
four, of which the `tail` exit code is number 4, so this is the fifth. Noted
rather than silently renumbered, because the count is the entry's headline.) The "add a missing facet" and "add a missing line" buttons in
`review.html` did nothing. `el('<tr>...')` returned `null`, because the HTML
parser DISCARDS `<tr>` and `<td>` assigned to a `<div>`, table rows outside table
context not being valid content; `appendChild(null)` then threw and `render()`
aborted with no visible failure. Emmett completed a full 29-facet review pass
before the loss was noticed, and the two lists had to be reconstructed by
dictation (`reviews/big_house/review-2026-07-27.json`, marked
`source: "dictated, UI capture failed"`).

Two things make this worth appending rather than filing separately. First, THE
RULE WAS VALIDATED THE SAME DAY IT WAS WRITTEN, by an instance it would have
caught: an empty list where the reviewer had entered items is precisely the
"well-formed, plausible, silent, wrong" shape described above, and it occurred in
the instrument being used to GRADE the pipeline rather than in the pipeline.
Second, the fix applied is EXACTLY the assertion this rule requires: after adding
a row, the code now compares the on-screen row count against the length of the
state array and alerts the reviewer if they disagree. That check is independent
of the code that failed, which is the property the rule insists on.

**APPENDED: a SIXTH instance, this one inside the validator written to enforce
this rule.** `scripts/validate_review.py` checks for the "note written but no
verdict recorded" shape, which is what a dropped click looks like. It applied
that check to FACET rows only. Six INTERSECTION LINE rows (L1, L3, L5, L6, L7,
L8) carried the unambiguous note "does not exist" with no verdict recorded, and
the validator reported the file as structurally intact. The gap was found by
reading the rows during triage, not by the check.

The lesson is narrower than the rule and worth stating separately: a check
applied to one collection does not cover a sibling collection, and the sibling
is exactly where it will be forgotten. The fix extends the same test to line
rows. The six verdicts have NOT been inferred from their notes; they are left
blank for pass 2, because reconstructing a reviewer's verdict from their prose
is the analyst substituting a judgement for the reviewer's.

Six instances in one day, all silent, all well-formed. Two of them were in the
instruments built to catch the others. Recorded here rather than as separate
entries because the pattern, not the count, is the finding; if this list grows
much further it should move to its own running record rather than continuing to
extend this entry.

**THE INSTANCE LIST MOVES OUT, 2026-07-27 (Emmett).** Six instances in one day,
two of them inside instruments built to catch the others, is a pattern with its
own life, and this entry should not keep growing an appendix. The running list
now lives at `reports/silent-failures/README.md`, with a row per instance naming
what it output and WHAT CAUGHT IT. **This entry is fixed from here: the rule
above does not change, only the register does.** Instances 1 through 6 are
recorded there, including the two appended above.
