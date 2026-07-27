### 2026-07-26: Decision entries are written without waiting for approval

**Decision:** Claude writes decision-log entries directly, at the moment the
decision is made, without pausing for Emmett to approve them first. The
approval gate is removed. The separate rule against inventing Emmett's
reasoning is NOT removed and is strengthened in its place.

**Why (Emmett, 2026-07-26):** *"i approve this decision entry and you should no
longer look for my approval on any future decision entries."*

The gate cost a round trip on every decision and bought little. An entry is a
RECORD of what was decided, not a request for permission to decide it; the
decision has already been made by the time the entry exists. And the log is
append-only, which means a wrong entry is not a permanent problem: it is
corrected by a later entry, and both stand as the record. That mechanism was
exercised the same day (see
2026-07-26-correction-min-pitch-exclusion-figure.md), and it worked exactly as
intended, which is the argument for trusting it rather than gating ahead of it.

The cost of the gate was also visible: several entries this session sat drafted
in conversation across multiple turns before being written, and a correction to
a factual error waited on approval while the error stayed committed.

**What is NOT removed.** Attribution honesty. Never put words in Emmett's mouth.
Where he stated the reasoning, quote him and say so. Where he did not, write the
best available reasoning and mark it explicitly as Claude's, for example
"Reasoning not stated by Emmett; this is the measured case." The two rules were
tangled together in one workflow step and are now separate, because they protect
different things: approval was about control over the record, attribution is
about the record being true. Removing the first does not license relaxing the
second. A "Why" silently attributed to Emmett that he never said would destroy
the log's entire value, which is that it says what was actually thought at the
time.

**Rejected:** Keeping a lighter gate, such as approval only for entries that
reverse a previous decision. It reintroduces the round trip exactly where speed
matters most, and reversals are the entries most worth capturing while the
reasoning is fresh.

**Layers swept, as the reversal-propagation rule requires:**
- `.claude/skills/decision-log/SKILL.md` workflow steps 2 and 3, and the
  end-of-session section ("propose the entries" becomes "write the entries").
- Agent memory: `draft-full-why-in-decisions.md` (its "show it for approval"
  instruction) and `session-closeout-workflow.md` (its "draft ... only with his
  stated Why" step).
- Checked and left unchanged: `CLAUDE.md`, which points at the skill and carries
  no approval language of its own.
- FLAGGED, NOT CHANGED: the global `session-closeout` skill at
  `~/.claude/skills/session-closeout/SKILL.md` carries the same gate ("only
  WRITE the ones whose reasoning the user actually stated"). It sits outside
  this repo, and Emmett installs skill changes to his global directory himself,
  so it is reported to him rather than edited here. Until he applies it, that
  layer can still reassert the old behaviour at session close, which is exactly
  the failure mode the propagation rule exists to prevent.

**Evidence:** Emmett's instruction, quoted above.

**Cost if wrong:** Entries get written that Emmett would have worded
differently, or that record a decision he had not actually settled. Both are
recoverable by a correcting entry, which is the mechanism the append-only log
already provides. The unrecoverable failure would be an entry attributing
reasoning to him that he never gave, which is why that rule is kept and
sharpened rather than relaxed alongside this one.

**Reverses:** the approval gate in the `decision-log` skill's workflow step 3,
which had stood since the skill was written.
