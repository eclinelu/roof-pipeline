### 2026-07-26: Blob candidates are selected by CELLS, not bounding box; a permanent assertion enforces single ownership

**Decision:** `recover_facets` selects a residual blob's candidate points by the
blob's OWN CELLS, never by its bounding box. Additionally, every run asserts
that no point index appears in two facets' index arrays, and fails loudly if one
does.

**Why:** Facets 20 and 23 of the canonical 2026-07-26 state shared 9,739 actual
points, 68.5 percent of the smaller facet; facets 21 and 23 shared 90 more.
9,829 duplicated point entries in total, 0.14 percent of the state.

Two causes compounded. `recover_facets` selected candidates with a bounding-box
test, and connected-component labelling guarantees blobs are disjoint as CELL
SETS but says nothing about their bounding BOXES, which can overlap or nest.
Blob 7's and blob 10's overlapped by 73.25 percent of the smaller. Second,
`dist` is computed once against the main facets before recovery starts and is
never updated as recovered facets are accepted, so a point already claimed by an
earlier blob still read as unexplained to a later, box-overlapping one.

Cell-based selection makes duplication impossible BY CONSTRUCTION rather than
unlikely: blobs share no cell, and every point falls in exactly one cell, so no
point can be offered to two blobs. That is a structural guarantee, which is
worth more than a fix that removes only the observed case.

**Why the assertion matters more than the fix (Emmett, 2026-07-26):** *"Now that
R1 persists inlier indices, ADD A PERMANENT ASSERTION that no point index
appears in two facets' index arrays. Run it on every future run, fail loudly.
That makes this whole class of defect self-detecting forever. Same principle as
ground-truth-is-audit-only, applied to code: measure the overlap, never let it
feed back."*

The fix closes one leak; the assertion closes the category. It is only possible
because standing rule R1 persists inlier indices: with summary rows alone,
double ownership is invisible, which is exactly why this survived a full
diagnostic pass undetected and was found only by chance while investigating an
unrelated merge question.

**Rejected:** Updating `dist` as each recovered facet is accepted. It works, and
it is the more general fix, but it makes the result depend on the order blobs
are processed. A week was just spent removing order-dependence from this
pipeline (see 2026-07-26-ransac-nondeterminism-probability-1.md); reintroducing
it through a different door would trade a known defect for a subtler one.

**Evidence:** `reports/big_house/duplicate-points-2026-07-26.json`. Shared index
arrays measured directly by intersection, not inferred; the blob bounding-box
overlap matrix; and the area impact, which is that summing the pair naively
overcounts gross area by 0.489 cu^2, 31.9 percent of their union.

**What was and was not affected:** the reported NET total is largely protected,
because area accounting resolves contested plan cells by highest-surface-wins
and charges the loser an occlusion. The facet COUNT is not protected: it was
inflated by one, and facet 23's per-facet numbers described a fragment of facet
20 rather than a surface of its own.

**Kept runnable on purpose:** the bounding-box path survives as
`selection="box"`, documented as the defect. Superseded states have to be
reproducible for the coverage change to be attributed step by step, and a
defect that can still be run is a defect that can still be demonstrated.

**Cost if wrong:** If cell-based selection is too tight, a facet whose points
sit just outside its blob's cells becomes unrecoverable, which would show as
coverage that does not improve where a blob clearly holds a surface. The
assertion has no failure mode other than stopping a run, which is the point.
