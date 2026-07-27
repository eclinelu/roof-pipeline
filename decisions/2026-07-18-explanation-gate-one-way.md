### 2026-07-18: The explanation gate points one way: Claude explains, Emmett is never quizzed or blocked

**Decision:** Amends the 2026-07-12 authorship entry: its authorship half stands (Claude Code writes the analysis core), and its gate mechanics are now explicit. Claude explains the approach, every threshold, and its scale-dependence in plain language, invites questions, and moves on. Claude never quizzes Emmett, never asks him to explain the why back, and never refuses to proceed until he supplies a reason. The walkthrough stays; every form of comprehension check on Emmett is gone.

**Why:** The gate exists so the design can be defended in an interview. A clear walkthrough with invited questions serves that; demanding the why back adds friction, not understanding. This had been rejected once already (the no-quiz feedback of 2026-07-12) but kept resurfacing, because the old rule was encoded in several instruction layers at once: CLAUDE.md still carried the pre-reversal wording requiring Emmett to hand-write and defend the core, the agent's memory carried the gate framing, and the 2026-07-12 entry in this log reads as a gate ON Emmett. A behavior change is only real when every layer that encodes the old rule is updated together; this entry records that alignment.

**Rejected:** Keeping any comprehension check (quiz-backs, recite-the-why, proceed-blocks). Also rejected: dropping the explanation practice itself; the walkthroughs stay, because clear explanations are what make the design defensible.

**Evidence:** Emmett's direct instruction of 2026-07-18, after a repo-wide audit found the old rule in CLAUDE.md (wording superseded 2026-07-12 but never removed there), the agent memory, and the 7a plan's per-task gates. CLAUDE.md and the agent memory were updated the same day; the historical plans and specs are records and stay as written.

**Cost if wrong:** If explanation without any check leaves gaps in understanding, they surface in an interview, the one place they must not. The mitigation is the standing invitation: questions are always welcome, and Emmett owns asking them.

**Amends:** 2026-07-12 "Claude Code writes the analysis code; the gate is explanation, not authorship."
