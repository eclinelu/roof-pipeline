### 2026-07-21: Dormer area ownership is highest-surface-wins, and the parent is charged only the overlap it actually counted

_Written 2026-07-26, late, for the same reason as
2026-07-21-coverage-replaces-expected-facets.md: the decision was made and
implemented on 2026-07-21, is cited in `roofkit/coverage.py`, and no entry was
ever written. Reconstructed from `TASK4-COVERAGE-HANDOFF.md` (written
2026-07-22), which records Emmett's override explicitly._

**Decision:** When two facets contest the same plan cell, the HIGHEST surface
owns it. A dormer roof is physically above the main slope and the main slope
does not exist beneath it.

The parent is NOT charged the dormer's full footprint. It is charged only the
plan cells its own alpha surface ACTUALLY counted and a higher facet also
covers. So:

    gross    = the facet's alpha area, holes left open
    occluded = the counted overlap, converted to slope at the parent's pitch
    net      = gross - occluded

**Why (Emmett overrode the original rule on the evidence):** the first design
subtracted the full child footprint from the parent. A gate measurement showed
that over-corrects, because the parent's alpha shape ALREADY leaves the dormer
hole open. Measured: only 8.9 percent of dormer plan area (2.87 of 32.4 cu^2)
sits inside any accepted facet's counted alpha surface, and the five real
dormers overlap host area by only 5 to 14 percent, with the biggest blob
overlapping 0 percent. Subtracting the full footprint would have removed area
the parent had never counted in the first place.

The 2026-07-22 note records this as *"Emmett OVERRODE the original
area-ownership rule in favour of the evidence-adjusted rule"* and the adjusted
rule as *"(Emmett approved)"*. The decision and the override are his; the
wording of the reasoning above is reconstructed.

**Why the two rules pull opposite ways, by design:** coverage takes the SET
UNION of explained cells, where overlap is harmless, because it only asks
whether each cell is explained at all. Area needs the opposite: each plan cell
must belong to exactly ONE facet or the total double-counts. The same cells are
treated differently by the two calculations on purpose, and that is documented
where the code does it.

**How the restated total must be framed:** as the pipeline IMPROVING, with a
line-by-line decomposition (`new_total_net = frozen 313.188 + dormer_gross -
occlusion`), never as a regression and never as a silent correction. The frozen
file stays untouched; the comparison lives in a new file. That framing was a
condition of the decision, not a presentational choice.

**Rejected:**
- Subtracting the full child footprint from the parent. Over-corrects, by the
  measurement above.
- Letting both facets count the contested cells. Double-counts area, which is
  the single most sensitive output of the pipeline.
- Lowest-surface-wins, or splitting contested cells evenly. Neither corresponds
  to anything physical; a roof under a dormer is not there.

**Evidence:** the double-count gate measurement quoted above (8.9 percent
counted overlap; per-dormer host overlap 5 to 14 percent, biggest blob 0
percent), recorded in `TASK4-COVERAGE-HANDOFF.md` on 2026-07-22 and implemented
in `roofkit/coverage.py::area_accounting`.

**Cost if wrong:** Area error in both directions. Under-charging occlusion
double-counts the dormer footprint and inflates the total; over-charging it
removes roof that exists. Area is the most scale-sensitive number this project
reports, so an ownership error propagates straight into the headline figure.
