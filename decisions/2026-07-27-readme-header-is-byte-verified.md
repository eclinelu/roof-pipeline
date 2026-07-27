### 2026-07-27: Constraint discovered the hard way: nothing may be added above `## Entries` in decisions/README.md

**Constraint:** In `decisions/README.md`, EVERYTHING ABOVE the
`## Entries (newest first)` marker is inside the byte-verified block. Adding text
there breaks `scripts/verify_decisions_split.py` and is reported as A PRE-SPLIT
ENTRY HAVING BEEN EDITED, which is alarming and misleading, because no entry has
been touched.

**Notes, policies and working-method statements go BELOW the index**, in the
`## Working method` or `## How this directory works` sections.

**Why it happens.** `verify_decisions_split.py` reassembles the original
`DECISIONS.md` from the split files and diffs it against the last committed
version. To do that it needs the original file's header, and it takes it from
README:

    head, _, listing = readme.partition("## Entries (newest first)")
    ...
    return names, head.rstrip("\n") + "\n\n"

So `head` is not a preamble to the index. IT IS THE ORIGINAL LOG'S HEADER, and it
is compared byte for byte. Anything added there becomes a diff against a file
committed at `ab39d3530`, which nothing written today can legitimately change.

**How it was found.** A one-paragraph note about the project's working method was
added directly under the "Append only" line. The verifier failed on the next run
with `DIFF -- a pre-split entry HAS been edited`, showing the added paragraph as
the diff. Nothing was wrong with the entries; the note was in the wrong place.

**THE FIX WAS TO MOVE THE CONTENT, NOT TO TOUCH THE VERIFIER**, and that is the
part worth writing down. The verifier's complaint was correct and its strictness
is the whole point: it is the mechanism that turns "these entries were never
edited" from a promise into a checkable claim. A check that gets relaxed the
first time it is inconvenient does not verify anything afterwards, and the next
person to hit this will be tempted to widen the exclusion rather than move two
sentences.

**Rejected:**
- Excluding the header from the comparison. It would silently permit the header
  itself to drift, and the header carries the log's own rules ("Append only.
  Newest at the top. Past entries are never edited."). Those rules being
  byte-stable is worth more than the convenience of writing above the index.
- Adding an "ignore this region" marker. Same defect with more machinery, and it
  creates a place where anything can be hidden from the check.
- Leaving it undocumented on the grounds that the error message points at the
  cause. It does not. It says a pre-split ENTRY was edited, which sends a reader
  to look at the entry files, where nothing is wrong.

**Cost if wrong:** none. The constraint is a placement rule, and the section
below the index is equally visible to a human reader.

**Evidence:** `scripts/verify_decisions_split.py` (the `index_names` function and
the `INDEX_MARKER` partition); the failing run on 2026-07-27 and the passing run
after the content was moved (45 entries indexed, 29 pre-split byte-identical, 16
appended above).

**Attribution:** Emmett directed that this be logged as a constraint discovered
the hard way, and stated the reason: without it written down the next person to
hit it will be tempted to loosen the verifier instead of moving the content. The
diagnosis and the wording are Claude's, who caused the failure.
