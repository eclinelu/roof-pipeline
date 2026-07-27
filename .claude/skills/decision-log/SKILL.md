---
name: decision-log
description: Record significant project decisions in decisions/ and current state in STATE.md. Use this skill whenever a design choice is made, an approach is selected over alternatives, an earlier decision is reversed, a blocker is resolved, or the project phase changes. Also use it at the end of any working session, and whenever the user says "log this", "record this decision", "update decisions", or asks what was decided and why. Consult this before ending a session in which anything was chosen, rejected, or changed.
---

# Decision log

The `decisions/` directory is the project's memory of WHY, not WHAT. The code shows what was built. These entries explain why it was built that way, what was rejected, and what would have to be true for the choice to be wrong.

For this project the decision log is not bookkeeping. It IS the deliverable that gets defended. Anyone can produce a roof area number. The defensible thing is the reasoning chain that produced it. Treat these entries as a primary artifact, not as documentation overhead.

## What counts as significant

The test:

> Would a future reader ask "why did they do it that way?" and be worse off without an answer?

If yes, log it. If it is just something that happened, do not.

### Qualifies

- An approach chosen over a named alternative (RANSAC over region growing)
- A threshold or parameter set to a specific value for a stated reason
- An earlier decision reversed
- A scope boundary drawn (this is in, that is deferred)
- A constraint discovered the hard way (a stage that does not do what its name suggests; a filter that fails on a class of input)
- A definition that changes a number (does a dormer count as its own facet?)
- An accuracy or validation choice

### Does not qualify

- File moves, renames, installs, environment setup
- Anything with no alternative that was seriously considered
- Routine implementation that follows directly from a decision already logged

The difference: significant decisions have a REASON THAT COULD HAVE GONE THE OTHER WAY. Everything else is just events.

Bias toward logging fewer, better entries. A log full of noise stops being read, and an unread log is worse than no log because it creates false confidence that the reasoning was captured.

## File structure

The record lives in two places with OPPOSITE update rules. Do not mix them.

```
STATE.md                              current state, overwritten in place
decisions/
  README.md                           the log's rules + the ordered index
  2026-07-26-ransac-nondeterminism-probability-1.md
  2026-07-25-persist-geometry-and-diagnostics.md
  ...                                 one entry per file, never edited
```

These were one file (`DECISIONS.md`) until 2026-07-26. The split changed no entry text; `python scripts/verify_decisions_split.py` reassembles the original from the pieces and diffs it against the last committed `DECISIONS.md` to prove it. Keep that script passing: it is what makes "these entries were never edited" a checkable claim instead of a promise.

### STATE.md: overwrite in place

Always short, always true right now. Stale state is worse than no state. Rewrite it; never append to it.

```markdown
## Current state

- Phase:
- Active blocker:
- Last thing verified working:
- Next action:
```

### decisions/: append only, one file per entry

Filename is `YYYY-MM-DD-short-slug.md`, from the entry's date and title. A new entry is a NEW file plus a new line at the TOP of the index list in `decisions/README.md`. That list is the record of order: several entries share a date, so sorting filenames cannot recover the sequence they were written in.

NEVER edit or delete a past entry file. Its value is that it is evidence. A log that gets rewritten stops being a record and becomes a story. One file per entry makes this easier to hold to, because any change to a past decision now shows up as a modified file in `git status` instead of hiding inside a diff to one large file.

If a past decision turns out to be wrong, do not fix it in place. Write a NEW entry that reverses it and references the original by filename. The reversal is more interesting than either position alone.

**A reversal is not finished when the entry is written.** The rule you just reversed usually lives in other instruction-bearing layers too: project instructions (CLAUDE.md), agent memory, other skills, reusable plan templates. Editing only this log leaves those stale layers to silently reassert the old behavior on the next session that reads them, and the agent re-applies whichever layer it read most recently. So when you write a reversal, sweep every instruction-bearing layer for the old rule and update each one in the same pass, and record in the entry which layers you changed. This project has been burned by exactly this failure: an instruction the decision log had already reversed survived in CLAUDE.md, agent memory, and a plan file, and kept resurrecting until every layer was found and fixed.

## Entry format

One entry per file in `decisions/`, using this exact template. The `###` heading is kept (rather than promoted to `#`) so entry text stays identical to how it was written when the log was a single file:

```markdown
### YYYY-MM-DD: One-line statement of the decision

**Decision:** What was chosen. One or two sentences.

**Why:** The reasoning. This is the field that matters. A future reader who disagrees should still understand the logic.

**Rejected:** What else was on the table and why it lost. If nothing was seriously considered, the decision probably was not significant.

**Evidence:** What this was based on. A log file, a test result, a measured number, a visual check. If it was based on assumption, say so explicitly.

**Cost if wrong:** What breaks, and how expensive is the recovery.

**Reverses:** (only if applicable) The date, title, and filename of the entry this overturns.
```

Not every field applies to every entry. Omit rather than pad. But "Why" and "Rejected" are close to mandatory: an entry without them is a note, not a decision.

## Evidence over assertion

The "Evidence" field exists because this project has already been burned by a confidently written, wrong lesson: the documentation asserted that ODM should stop at odm_filterpoints, which produced no point cloud on two separate runs, because the .laz is actually written by a later stage. The claim was never checked against the ODM log.

So: when logging a decision that rests on how a tool actually behaves, cite the log, the output, or the test. If a decision rests on assumption, write "Assumption, not verified" in the Evidence field. That is not a weakness in the entry, it is the most useful thing in it, because it tells a future reader exactly where to look first when something breaks.

## Workflow

1. Read `decisions/README.md` before proposing an update, plus any entry files it points to that look related, so entries are consistent and no decision is logged twice. The index is short by design; read it first rather than every entry.
2. Draft the entry.
3. SHOW IT TO THE USER BEFORE WRITING. The user owns the reasoning; do not put words in their mouth. If the "Why" is not something they actually said or agreed to, it does not go in.
4. Update `STATE.md` if the state changed.
5. If this entry reverses or changes a standing rule, sweep every instruction-bearing layer (CLAUDE.md, agent memory, other skills, reusable plan templates) for the old rule and update each in the same pass; list the layers you changed in the entry. A reversal logged but not propagated leaves stale layers that resurrect the old behavior on the next session that reads them.
6. Write the new file in `decisions/`, and add its line to the TOP of the index list in `decisions/README.md`. Both, or the entry is invisible.
7. Commit, with a message naming the decision.

## At the end of a session

Ask: was anything chosen, rejected, reversed, or discovered today?

If yes, propose the entries before the session ends. Decisions not written down the day they are made get reconstructed later from memory, and reconstructed reasoning is not evidence.
