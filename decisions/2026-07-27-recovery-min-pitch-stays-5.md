### 2026-07-27: Recovery keeps min_pitch = 5. One threshold, not two.

**Decision:** RECOVERY keeps `min_pitch = 5`, the same value MAIN DISCOVERY uses.
The open question raised in `2026-07-26-min-pitch-definition-not-filter.md` is
CLOSED. No code changes: 5 is already the default in both places.

**The question was measured, not waved off.** A full sweep re-ran the entire
pipeline at recovery `min_pitch` of 5.0, 4.5, 4.0, 3.7, 3.5, 3.0, 2.0 and 1.0,
holding main discovery at 5.0. A full re-run per value rather than one discovery
with a looped recovery, because Open3D's RANSAC draws from a single global stream
and a looped recovery would have measured stream position as well as pitch.

The result is a genuine wide plateau, and the plateau is not the problem:

    recovery min_pitch   facets   facet coverage
    5.0, 4.5                 29         88.40 pct
    4.0 down to 1.0          30         89.98 pct

The plateau spans 3.0 degrees and 6 sweep points, in BOTH facet count and
coverage. A value chosen inside it could not have been tuned to the result. The
cross-check row at 5.0 reproduces `canonical-2026-07-26-r2` exactly, 29 facets
and 21 recovered, so the sweep measures what it claims.

**What the whole plateau buys: one facet.** 2,623 points, 3.885 degrees, quality
2.147. Recovered gross surface goes from 35.6263 to 35.9524 cu^2. That is
**0.3261 cu^2**, 0.9 percent of what recovery already finds and 1.0 percent of
the 33.68 cu^2 still unexplained.

**Why that closes it.** `min_pitch` is a DEFINITION of what counts as a roof
surface, not a filter against error (2026-07-26). A definition that changes
depending on which pass happened to find the surface is not a definition. A
second threshold costs a second number to justify per site, a second number to
re-measure per cloud, and a second place for the two to drift apart. Emmett's
call, in his words: a wide plateau on a negligible payoff is not worth two
thresholds where one works.

**On the coverage column, flagged rather than relied on (Claude's reading, not
separately measured).** Coverage rises 1.58 points and unexplained plan area
drops 4.595 cu^2, both far out of proportion to 0.326 cu^2 of recovered surface.
The mechanism is visible in the code: `coverage_masks` calls `assign_to_planes`
with `max_dist=inf` and then thresholds by band, so a cell counts as explained if
its points lie within the band of a facet's INFINITE plane, whether or not that
facet's alpha surface covers the cell. A near-horizontal plane therefore collects
coverage credit across far more plan area than it contributes surface. This is
not the basis of the decision, which rests on the 0.326 cu^2, but it argues the
same way and it is a thing to watch when coverage is read as a quality score.

**Rejected:**
- Lowering recovery to 4.0 or below. Buys 0.326 cu^2 in exchange for a second
  threshold.
- Making recovery `min_pitch` a per-site config value. Defers the identical
  decision to every future site without resolving it, and hides it in a config
  file where nobody re-derives it.

**Cost if wrong:** 0.326 cu^2 of gross surface on a big_house-like roof, plus
whatever a genuinely flat section would contribute on a site that has one. Fully
recoverable: `scripts/probe_recovery_pitch.py` re-runs the sweep.

**HONEST LIMIT:** measured on ONE cloud. A building with a real flat roof section
between 1 and 5 degrees would pay a much larger price than 0.326 cu^2, and
nothing here detects that case automatically. Re-measure the sweep on any site
whose roof is not all steep-slope.

**Evidence:** `reports/big_house/recovery-pitch-sweep-2026-07-26.json`.

**Closes:** the open question in `2026-07-26-min-pitch-definition-not-filter.md`.

**Attribution:** the decision and its reason are Emmett's, stated directly. The
coverage-mechanism reading above is Claude's.
