---
name: visual-pass
description: Run a visual review pass comparing one artifact's per-facet renders against the previous artifact's renders, side by side, to see what a single change did. Use when a change has been executed and its effect on segmentation needs to be graded by eye; when the user says "visual pass", "review pass", "grade the renders", "r2 vs X", or names two artifact stamps to compare; and before any claim that a change improved or damaged facet geometry.
---

# Visual pass

## Purpose

A visual pass grades ONE artifact's per-facet renders against the PREVIOUS
artifact's renders, side by side, to see what a single change did.

It is a measuring instrument pointed at geometry, not a review of the code that
produced the geometry. Its output is a human description of what the roof looks
like in each render and how the two renders differ.

## Where the process lives, and where the code lives

This file is the process and the invariants. It holds no commands and no code.

The harness is a script in the repo (`scripts/visual_pass.py`). Its flags,
paths, and defaults are documented by the script itself, in its module docstring
and its `--help`. Read them there.

This split is deliberate. The `odm-run` instruction was copied into three files
and all three drifted out of date, because a duplicated command is a command
that only one person remembers to update. There is exactly one copy of the
invocation details and it sits next to the code it describes. If you find
yourself about to paste a command line into this file, don't.

## Naming

Passes are named by artifact pair, never by number.

    r2-vs-grid-adopted          correct
    pass 2                      wrong

A number tells you nothing about what was compared and stops being unique the
moment two passes run out of order. The pair names its own content.

## One change per pass

A pass follows exactly one change.

Two changes at once make the diff unattributable. If both the grid phase and the
pitch floor moved between the two artifacts, no render can tell you which one
caused what you are looking at, and the pass produces a record that reads like
evidence but is not.

If two changes have already landed together, the pass can still run, but the
record must say on its face that the diff is unattributable, and no mechanism
claim may be drawn from it.

## Correspondence is computed, never assumed

**Do not pair facets by index number.** Facet 12 in the old artifact is not
facet 12 in the new one. Indices shift whenever a facet merges, splits, appears,
or vanishes, and they shift silently.

Facets own point index sets. Correspondence is computed from **set overlap
between old and new facets** — which points does this old facet share with that
new facet — and from nothing else.

Requirements:

- Every pairing in the record carries its overlap fraction, reported in both
  directions: the shared fraction of the old facet, and the shared fraction of
  the new facet. Both, because they differ, and the difference is what
  distinguishes a clean 1-to-1 from a facet that grew or shrank.
- Grouping is driven by the overlap values themselves, not by a tuned cutoff.
  A threshold picked to make this pass look tidy will silently mis-group the
  next one. Any cutoff that does exist may control what gets *printed*, never
  what gets *grouped*, and the record must say which is which.

Computed correspondence detects merges, splits, new facets, and vanished facets
automatically, with no hand-maintained list to fall out of date.

## Layout cases

All five are required. A pass whose harness cannot render one of them is not
finished, even if this particular artifact pair does not exercise it.

| Case | Cardinality | Layout |
|---|---|---|
| 1 to 1 | 1 old, 1 new | old left, new right |
| merge | N old, 1 new | all old stacked left, merged new right |
| split | 1 old, N new | old left, all new stacked right |
| new | 0 old, 1 new | empty labeled pane left, new right |
| vanished | 1 old, 0 new | old left, empty labeled pane right |

The empty pane is labeled, not blank. A blank half reads as a rendering failure;
a pane that says "no predecessor" or "no successor" reads as a finding.

**A vanished facet is a finding.** Index pairing hides it completely: old facet
20 disappears, new facet 20 exists as something unrelated, and the row looks
like a normal 1-to-1 that merely changed a lot. That failure is the reason index
pairing is banned, not a side effect of banning it.

Cardinalities beyond these five (N old to M new, both greater than one) are
real and must be reported as their own case rather than forced into a split or
a merge.

## Pixel diff

Above every row, before the images, state:

- whether the two files are **byte-hash equal**
- a **pixel diff summary** — how many pixels differ, and by how much

Both are printed so that "identical" is a stated fact and not something the
reviewer squints at and assumes.

### Caveat, and it must appear in the harness output

**Two renders can differ in pixels while the geometry is identical.** Axis
limits, colour scaling, annotation and label placement, font metrics, and
library versions all move pixels without moving a single point.

A changed flag means **look closer**, not **something moved**.

This is not a theoretical caveat. It fires on real data: a pair of renders whose
underlying point index sets were bit-identical still differed across a large
fraction of their pixels, entirely because the artifact stamp in the title was a
different length and the line labels had been laid out around a different set of
neighbouring facets.

So the pixel diff is never read alone. It is read next to the overlap fraction,
which is computed from geometry and is the one of the two that can settle the
question. When the overlap is 1.000 in both directions and the pixels differ,
the geometry did not change and the record must say so.

### Provenance

Record which commit produced each render set. If it cannot be determined —
uncommitted renders, a dirty tree, renders with no git history — say so plainly
in the output. An undated render set compared against a dated one produces a
diff nobody can attribute later, and the honest failure mode is to print
"provenance unknown" rather than to let the row imply the diff is trustworthy.

## Verdicts

**Free text only.** No multiple choice, no dropdown, no preset codes, no
pass/fail field, no autocomplete from prior verdicts, no suggested wording.

This is a rule with a cost attached, and the cost has already been paid. Pass 1
used coded options, the codes were used in contradictory senses across facets,
and that part of the record is now partly unusable. A code compresses an
observation before anyone knows which distinction will matter, and the
compression cannot be undone afterwards.

Free text also protects against the subtler failure: a fixed vocabulary can only
express the problems someone anticipated. The findings worth having are the ones
nobody had a word for yet.

Further requirements:

- **A comparison note is a SEPARATE field from the verdict.** The verdict
  describes what the new render shows. The comparison note describes how it
  differs from the old one. Collapsing them produces entries where nobody can
  later tell whether "the west edge is short" was observed in the new artifact
  or inherited from the old.
- **Verdicts persist to disk as they are entered**, not on a save action at the
  end. A pass over thirty facets is a long sitting, and a record that only
  exists in a browser tab is a record one crash away from being re-done from
  memory.

## Blindness

Side by side means **the pass is NOT blind**. The grader can see the old render
while grading the new one, and knows which is which.

State this as a property of the record. It is a known, accepted limitation of
this instrument, recorded so that nobody later reads the pass as blind evidence.
No further discussion is needed and no correction is available.

## Completeness

The harness refuses to report a pass complete while any facet row or any line
row lacks a verdict, and it lists exactly what is missing.

Partial passes are legitimate — a pass can be interrupted. What is not
legitimate is a partial pass that reports as finished, because the ungraded rows
then read as "nothing to report" instead of "never looked at".

## What a pass cannot do

**Standing rule 7.** Visual review can establish THAT something is wrong, and
WHAT it is physically. It can never set a parameter value.

A render can show that an outline stops inside the real roof edge. It cannot
tell you that the distance threshold should be 0.04. The description travels to
the next site and the next artifact; the number does not, because the number was
fitted to this cloud at this scale.

Verdicts that name a threshold, a parameter, or a fix are out of scope for the
instrument. Findings feed triage; triage proposes mechanisms; mechanisms get
tested. The pass stops at the physical description.

## Anti-null assertions

A diagnostic that cannot fail is not a diagnostic. Every visual pass carries
assertions that are independent of the pass's own result, and they fail loudly
rather than warning:

- Overlap fractions are computed from real point index sets, not from indices.
  This is checkable: relabelling the facets of an artifact and re-running
  correspondence against the original must recover the relabelling. An
  index-based implementation returns the identity instead, and fails.
- Every old facet and every new facet appears in exactly one row.
- An empty verdict, or a verdict matching a known preset string, is refused.
- The verdict count matches the facet count in the artifact.
- Writing into an artifact directory fails.

See the silent-failure register for why every diagnostic carries an assertion
independent of its own result.

## Read-only contract

A pass **reads** existing renders and artifacts and **writes** only its own
output directory.

It never generates a PNG, never modifies a PNG, never imports render code, and
never writes into a directory holding canonical or frozen artifacts or existing
review records. Render code is frequently in use by another run while a pass is
being built; artifacts are frozen evidence. Neither is the pass's to touch.

Prior passes' verdicts are not displayed, not pre-filled, and not imported. The
grader grades what is on the screen.
