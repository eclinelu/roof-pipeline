### 2026-07-12: Claude Code writes the analysis code; the gate is explanation, not authorship

**Decision:** Claude Code writes the analysis core (segmentation, geometry, measurement). Emmett no longer hand-types it. The acceptance gate is that no code enters `roofkit/` unless Emmett can explain the approach, justify every threshold, and state whether it is scale-dependent.

**Why:** The original rule required hand-typing the analysis core so it could be defended in an interview. On reflection, typing was a means to understanding, not the source of it, and a slow one. The defensible content of this project is the design: the ODM-versus-own-code seam, the isolation strategy, the facet definition, the error analysis. That survives a change of authorship. The ability to explain does not survive skipping the gate.

**Rejected:** Continuing to hand-type. Rejected on speed. Also rejected: dropping the gate entirely, which would turn a portfolio project into a demo.

**Cost if wrong:** If the gate is not actually enforced, this becomes code that cannot be defended under questioning, and the project loses its entire purpose.

**Reverses:** The original project rule that Emmett writes all analysis code by hand.
