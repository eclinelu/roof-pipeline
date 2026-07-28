# Silent failure register

Well-formed, plausible, silent, wrong. Output that formats cleanly, sits in a
believable range, raises no exception, and is not the quantity intended.

Started 2026-07-27 after six instances in one day, two of them inside the
instruments built to catch the others. The pattern is the finding; the count is
how the pattern is tracked. The standing rule that came out of it is
`decisions/2026-07-27-silent-failure-standing-rule.md`, which stays fixed. THIS
file is the running list, so the entry does not keep growing.

**Every diagnostic carries at least one assertion that would fail loudly if it
were measuring the wrong thing, built from something known INDEPENDENTLY of the
probe's own result.**

| # | date | where | what happened | what it output | caught by |
|---|------|-------|---------------|----------------|-----------|
| 1 | 2026-07-27 | `probe_blob0.py` | RANSAC re-peel outside the production sequence drew from a different position in Open3D's global stream | a plausible plane at quality 2.91498, on the opposite side of the accept/reject boundary from the true 2.94820 | an embedded cross-check that FAILED |
| 2 | 2026-07-27 | `probe_blob0_residuals.py` | distance transform run on a hole-riddled mask measured distance-to-nearest-capture-hole, not distance-from-edge | interior-only quality 2.90857, appearing to clear the bar | a later probe contradicting it |
| 3 | 2026-07-27 | `review_render.py` | `np.ptp` over an (N,2) UTM block returned the range across BOTH columns, about 4 million cloud units | a well-formed EMPTY LIST: zero ridges on a pitched roof | domain knowledge |
| 4 | 2026-07-27 | shell | run piped through `tail`, so the reported exit status was `tail`'s | exit 0 for two runs that died with MemoryError | noticing renders were stale |
| 5 | 2026-07-27 | `review_ui.py` | `el('<tr>')` returned null because the HTML parser discards table rows outside table context; `appendChild(null)` threw and `render()` aborted | two lists silently stayed empty through a full 29-facet review pass | the reviewer, afterwards |
| 6 | 2026-07-27 | `validate_review.py` | the note-without-verdict check was applied to facet rows only, not to the sibling line rows | "structurally intact" while six line rows carried unambiguous notes and no verdict | reading the rows during triage |
| 7 | 2026-07-28 | `probe_production_phase.py`, the integer-offset check | the perturbation was ALIGNED WITH THE DEFECT'S OWN PERIOD: an integer cell shift changes `nx` by the same integer, so `plan_grid`'s bin-pitch error very nearly cancels and the test is structurally blind to the thing it was checking | a 0.01-point move against a 5.20-point spread, read out loud as "the bin-pitch defect is NOT the driver". The direct counterfactual then showed it caused 97 pct of it | running the counterfactual anyway |
| 8 | 2026-07-28 | `probe_grid_phase.py`, first version | perturbed the raster phase by translating the POINTS. `connected_core` derives its origin as `xy.min()`, so the origin translated with them and the binning was bit-identical every time | a spread of EXACTLY 0.000000 on all 40 facet-scale pairs, with three sanity checks passing. A null result that looked STRONGER than a real one, because zero spread is cleaner than any true measurement | the number being too clean to believe |

## A named CLASS, from 7 and 8: the perturbation that cannot see the defect

Rows 7 and 8 are the same family and it is worth naming, because both produced a
confident WRONG NEGATIVE and a wrong negative closes an investigation.

**A test that perturbs a system to detect a defect is blind whenever the
perturbation is aligned with the defect's own period or symmetry.**

- **7**: the defect scales with the bin count; the perturbation changed the bin
  count by the same amount. The error rode along and cancelled.
- **8**: the defect is a phase; the perturbation was a translation, and the
  quantity being perturbed was re-derived FROM the translated data. The phase
  rode along and cancelled.

**The guard, in two parts:**

1. **Anti-null.** A probe that perturbs a parameter must assert that at least one
   perturbation changed at least one output. Well-formedness checks (in range,
   reproduces the reference, invariant where it should be) all pass happily on a
   probe that is perturbing nothing. Row 8 carried three of them.
2. **Prefer the direct counterfactual.** When the suspected cause can be TOGGLED,
   toggle it and measure, rather than reasoning about it through a proxy. And
   before trusting a proxy that returns "not the cause", state explicitly what
   would make that proxy blind. A negative from a proxy deserves more scepticism
   than a positive, because only the negative ends the search.

## What the list is for

Two of six were in instruments built to enforce the rule. That is the useful
number, and it is why the rule applies to diagnostic code exactly as to
production code. "It is only a probe" is precisely when the guard gets skipped.

Add a row when it happens. If a row cannot name what CAUGHT it, that is worth
more attention than the failure itself.
