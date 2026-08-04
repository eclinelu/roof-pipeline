### 2026-08-03: PASS RESULT r2-vs-grid-adopted: the 8 main facets are untouched to the bit, and ALL 21 recovered facets shifted membership. Worst overlap 0.7603

**Decision:** Recorded as the result of the first completed visual pass. The
grid adoption left the deliverable facets exactly alone and moved every
recovered facet. No parameter is set here and nothing is adopted from this
entry; under standing rule 7 a visual pass cannot set a value.

**Why:** The grid adoption was already scored against five pre-registered
predictions and passed all five, but that scoring was numeric and aggregate.
This pass asks the question the numbers cannot answer: what did the change do to
the geometry, facet by facet, as seen. It is the evidence that the adoption's
effect is confined to the recovered set rather than merely summing to the same
total, which is a claim the deliverable depends on and which no total can
establish.

**Evidence:** `reviews/big_house/pass-r2-vs-grid-adopted.json`, 47 verdicts,
`complete: true`, `refused: {}`. Per-facet overlap in
`reviews/big_house/pass-r2-vs-grid-adopted.overlap.json`, extracted verbatim
from the harness output before the artifact directory was reverted, with each
row carrying the literal source string alongside the number so the record does
not depend on float printing.

- Facets 0 through 7, the 8 main facets: overlap exactly
  1.00000000000000000 in both directions. Same points, no gain, no loss.
- Facets 8 through 28, all 21 recovered facets: overlap below 1.0 in both
  directions, without exception.
- The worst pair is facet 10, of old **0.76034294053265228**, of new
  **0.72012024463563806**, on 20,841 shared points, with 885 points leaking to
  new facet 8 and 819 to new facet 9.

The grader's verdicts agree with the arithmetic and were written without reading
it. Facets 0 through 7 are recorded as "identical images, nothing changes when
bin-pitch was fixed". The recovered facets are recorded as "boundary has shifted,
but neither in a good or bad way", several adding that the facet is still split
in half.

**This pass is NOT blind.** Side by side, the grader saw the old render and knew
which was which. This is a known and accepted limitation of the instrument,
recorded as a property of the record so that nobody later reads the pass as
blind evidence. No correction is available and none is proposed.

**POWER CHECK, could this have come out the other way.** Yes, in both
directions, and the instrument was not free to return this answer. The 8 main
facets were free to move: overlap is computed from the point index arrays, and
any membership change at all would have driven their fractions below 1.0. The 21
recovered facets were free to stay: 8 of the 29 pairs did return exactly 1.0, so
a run in which the recovered facets also held still would have printed 29 exact
pairs rather than 8. The result is therefore a measurement, not a foregone
conclusion of the method.

**Not established by this pass:** that the shift is an improvement. Twenty-one
facets moved and the grader declined to call the movement good or bad in every
single case. The split-in-half complaint is unchanged from pass 1, so the
adoption did not fix it. Facet 4 remains ungradable as rendered, now attributed
to render resolution and label placement rather than to geometry, and that
render defect is still open.

**Cost if wrong:** low. Nothing is adopted here. The overlap values are
recomputable from the canonical `.npz` index sets and were reproduced exactly,
with zero mismatches across all 29 facets, when the pass was regenerated from
scratch after the artifact revert.

**Attribution.** All 47 verdicts are Emmett's own free text. The overlap
computation, the extraction to a durable record, and the reading of the 8
versus 21 split are mine.
