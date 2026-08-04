### 2026-08-03: KNOWN RECURRING COST: every branch that adds a decision entry conflicts on `decisions/README.md`. Structural, not accidental, and left unaddressed on purpose

**Defect:** `decisions/README.md` is an append-at-the-top index, and entries are
newest first. Any two lines of development that each add an entry both insert at
the same point, the first line under `## Entries (newest first)`. Git sees
competing insertions at one location and reports a content conflict. This is a
property of the file's shape, not a mistake by either side, and it will recur on
**every** branch that adds an entry.

Observed concretely today. The `review/harness` merge produced exactly one
conflict across 11 changed files, on `decisions/README.md`, while `.gitignore`,
`.gitattributes` and every content file merged cleanly. A rehearsal run before
the merge predicted it on the same path. Resolution was mechanical: keep all six
lines from both sides, order them, delete nothing.

**Why record a cost that is merely annoying.** Two reasons, and the second is
the one that matters.

1. It is predictable, so it should be predicted. A conflict that surprises
   someone mid-merge invites a hurried resolution.
2. **The failure mode is silent and irreversible in the direction that hurts.**
   The index is the record of ORDER, because several entries share a date and
   sorting filenames cannot recover the sequence they were written in. The
   natural way to end a conflict quickly is to take one side. Taking one side
   here DELETES the other side's index lines while leaving their entry files on
   disk, which produces exactly the state
   `verify_decisions_split.py` is built to catch: the index and the files
   disagree. The log is append-only, so a dropped line is repaired by another
   commit rather than by an edit, and the ordering information may not be
   recoverable at all if nobody notices promptly.

The mitigation that already exists is the verifier. Running
`python scripts/verify_decisions_split.py` after resolving reports the indexed
count against the on-disk count and diffs the reassembled pre-split baseline.
It returned 72 and 72 with an empty diff after today's merge. **Running it
before committing any merge that touches the index is the practice this entry
records**, and it is the reason the failure above is catchable rather than
merely likely.

**POWER CHECK, could this have come out the other way.** Yes, and the test was
run rather than reasoned about. A dry merge of `review/harness` into
`origin/main` was rehearsed and then discarded specifically to find out which
paths conflict. It could have reported zero conflicts, which would have made
this entry unnecessary, or conflicts on content files, which would have been a
different and more serious finding. It reported exactly one, on the index, which
is what a structural insertion collision predicts and what distinguishes it from
an accidental one.

**Cost if wrong:** very low. This entry changes no file and no procedure beyond
naming a practice already followed.

**NOT DONE, on instruction and worth stating explicitly.** No merge driver is
implemented, no `.gitattributes` entry is added for this path, and the index is
not restructured into one-file-per-entry or any other conflict-free shape.
**Emmett has noted that a `union` merge attribute on `decisions/README.md` is an
available option and has NOT chosen it.** Recording that the option was seen and
declined, so a later reader does not mistake the absence of a fix for the
absence of an idea. A union merge would also concatenate both sides
automatically and thereby decide ordering by merge mechanics rather than by
judgement, which is a real cost against the file whose job is to carry order.

**Attribution.** The structural reading and the silent-deletion failure mode are
mine. The decision to leave it unaddressed, and the observation that a union
merge attribute is an available and unchosen option, are Emmett's.
