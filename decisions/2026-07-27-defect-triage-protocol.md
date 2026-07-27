### 2026-07-27: Defect triage protocol, declared BEFORE the review results are read

**Decision:** How defects from a visual review get triaged and fixed is fixed
HERE, before either Emmett or Claude has read the review results. The completed
review is on disk (`reviews/big_house/review-2026-07-27.json`, structurally
validated, 28 of 29 facets and 12 of 18 lines answered) and has deliberately not
been analysed.

**Why the ordering matters this much.** Rules chosen after seeing results are
rules chosen to produce a convenient answer. The specific temptation here is
named so it can be checked against later: **picking the fix that touches the most
facets instead of the one at the earliest stage.** A fix that visibly improves
twenty outlines is more satisfying to choose than one that corrects which points
belong to a facet, and if the second is upstream of the first then choosing the
first means doing the work twice and reporting a result built on a defect that
was known about.

---

**3a. TRIAGE IS BY MECHANISM, NOT BY FACET.**

The first pass over the review answers ONE question: **how many distinct
mechanisms explain all of this?** It does not answer "what do I fix". Every
recorded defect is attributed to a candidate mechanism, and mechanisms are ranked
by HOW MANY FACETS THEY EXPLAIN.

A mechanism that explains ONE facet is a SPECIAL CASE. Special cases do not get
fixed on a development site. Fixing them tunes the pipeline to this building,
which is the one thing a development site must not be used for, and there are
only two held-out sites to spend if it goes wrong.

**3b. FIX ORDER IS BY PIPELINE STAGE, NOT BY SEVERITY.**

Stages feed each other, so fixing downstream first means redoing it. The order is
fixed:

    1. MEMBERSHIP          which points belong to a facet
    2. DISCOVERY           which planes are found
    3. ACCEPTANCE          which planes are kept
    4. BOUNDARY            where the outline sits
    5. DERIVED GEOMETRY    intersection lines

A major-severity defect at stage 4 waits behind a minor-severity defect at stage
1. Severity determines what gets reported, never what gets worked on first.

**Intersection lines get NO WORK ITEM until the facets settle.** They are
computed FROM facet planes, so they cannot be fixed independently: a line is
wrong if either facet it derives from is wrong, and correcting the line without
correcting the facet just moves a wrong answer somewhere less visible.

**3c. EVERY MECHANISM FIX STILL NEEDS A CAUSE THAT WOULD HAVE BEEN TRUE IF
EMMETT HAD NEVER LOOKED, AND STILL NEEDS ITS OWN PLATEAU TEST.**

Visual review LOCATED the defects. It does not license setting a value. This is
the standing limit from `2026-07-27-development-vs-validation-split.md`, restated
here because this is the entry where it will actually bite.

The precedent that shows it has teeth is on record and is one day old: boundary
erosion was proposed from a correctly measured profile, tested as a population
property across all 29 facets, and REFUTED, because the quality bar fell 0.239
under symmetric erosion while blob 0 moved 0.001
(`2026-07-27-erosion-refuted-and-interior-retraction.md`). A defect being real
does not make the first proposed fix for it right.

**3d. THE LOOP.**

    fix ONE mechanism
      -> regenerate to a NEW artifact, superseded not overwritten
      -> re-render
      -> re-review

`canonical-2026-07-26-r2` is NEVER overwritten. Each pass produces its own dated
artifact and its own review file, so the sequence of what was known when stays
reconstructable.

One mechanism per pass, not several. Two fixes landing together cannot be
attributed, and the point of the loop is to learn which mechanism was responsible
for what.

**3e. STOPPING RULE, declared now, before anyone knows how many passes it takes.**

**Stop when a pass yields NO NEW MECHANISM, only new instances of mechanisms
already known.**

Not "when coverage reaches N", not "when the outlines look right", not "when we
run out of time". Without a rule declared in advance the freeze date is
arbitrary, and an arbitrary freeze date is chosen, in practice, on the day the
results look good.

**A MECHANISM THAT IS IDENTIFIED AND UNDERSTOOD BUT HAS NO FIX MEETING 3c IS
LOGGED AS A KNOWN LIMIT AND REPORTED WITH THE DELIVERABLE. IT DOES NOT BLOCK THE
FREEZE.**

The stopping rule as first drafted assumed every mechanism found gets fixed, and
that assumption is already false. **Blob 0 is the counterexample and it exists
today**: confirmed real roof, three mechanisms proposed, three dead, and no
defensible fix. Without this clause the protocol blocks the freeze indefinitely
on exactly the defects that are best understood, and it pushes toward INVENTING A
FIX TO CLEAR THE GATE, which is the failure mode the whole protocol exists to
prevent.

**The clause is constrained so that using it costs something.** A known limit
MUST be stated in any report that quotes a number affected by it. Not in an
appendix, not once at the front: attached to the affected number. That price is
what stops "known limit" becoming a dumping ground for anything inconvenient,
because every use of it makes a deliverable harder to read and a claim weaker,
and those are visible to the reader.

A known limit is not a lower standard than a fix. It is a different, honest
answer: this is understood, this is what it costs, and no change we can justify
improves it.

**3f. BIAS LIMIT ON THE INSTRUMENT.**

A second review pass is NOT independent of the first. Emmett will remember what
he marked, and the second pass will inherit the first pass's framing. This is
acceptable on a DEVELOPMENT site, where the review is a search instrument rather
than a score.

It is stated here rather than left for a reader to find, and it is a further
reason no accuracy claim can come from big_house: the review that guided the
fixes cannot also certify them. Certification is what bungalow and cove_house are
for, once each, after the freeze.

---

**3g. TWO CANDIDATE MECHANISMS ALREADY VISIBLE. HYPOTHESES ONLY, NOT TESTED IN
THIS TASK.**

Recorded now so that if they turn out to be right, the record shows they were
suspected before the triage pass rather than constructed to fit it. Neither is
probed here.

**H1: facet membership includes disconnected fragments remote from the main
body.** Observed on facet 0. The mechanism would be that `assign_to_planes` gives
every point to its nearest plane by distance to an UNBOUNDED plane, with no
requirement that the point be anywhere near the facet's actual extent. Nothing
downstream catches it: `assert_single_ownership` checks that no point is owned by
TWO facets, which a thin remote sliver satisfies perfectly well, and the
project's existing contiguity rule (`2026-07-18-contiguity-rule-run2.md`) is
applied to the scale-span extent, not to facet membership.

IF TRUE, THE CONSEQUENCE IS LARGE AND MUST BE STATED BEFORE IT IS CONVENIENT TO
STATE: every plane fit is contaminated by points that are not on that surface, so
**every quality score is suspect, INCLUDING blob 0's**. The blob 0 question would
then not be well-posed in its current form, because both sides of the comparison,
the candidate at 2.94820 and the bar at 2.94800, are computed from
possibly-contaminated membership. H1 sits at stage 1, the earliest stage, which
under 3b puts it first if it survives.

**H2: dormer roof planes are absorbed into large main-roof facets instead of
forming their own.** Of the three dictated missing facets, MF2 and MF3 are dormer
sides on two DIFFERENT dormers, never discovered at all. Independently, the
2026-07-15 refutation of the predicted primary span was caused by dormer
contamination of facet 0 (`2026-07-15-dormers-unresolved-this-run.md`), and facet
0 is the same facet now showing remote fragments.

That is potentially ONE CAUSE WITH TWO SYMPTOMS separated by twelve days: dormer
points absorbed into a host facet both corrupt that facet's geometry and leave
the dormer's own planes undiscovered. H1 and H2 may also be the same mechanism
seen from two sides, which is exactly the kind of question 3a exists to ask.

---

**What this entry does NOT do.** It assigns no defect to a stage, ranks no
mechanism, and reads no verdict. The review results are unanalysed as of writing.

**Cost if wrong:** the protocol could turn out to over-constrain, for instance if
a stage-4 defect is genuinely independent of a stage-1 one and could safely have
been fixed in parallel. The cost is some wasted ordering, paid in time. The cost
of the opposite error, fixing downstream first and rebuilding on a defect, is a
result that has to be withdrawn.

**Evidence:** `reviews/big_house/review-2026-07-27.json` (completed, validated,
unread); `2026-07-27-development-vs-validation-split.md`;
`2026-07-27-erosion-refuted-and-interior-retraction.md`;
`2026-07-15-dormers-unresolved-this-run.md`.

**Attribution:** every rule in 3a through 3g, the known-limit clause in 3e and
its constraint, and both candidate mechanisms in 3g including the consequence for
blob 0, are Emmett's, dictated before the results were read. The code references
locating H1 in `assign_to_planes` and distinguishing the existing contiguity rule
from facet membership are Claude's.
