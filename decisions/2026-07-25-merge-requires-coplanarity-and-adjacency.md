### 2026-07-25: A merge requires coplanarity AND spatial adjacency

**Decision:** Two facets may be merged only if they are BOTH coplanar (small
normal-angle difference and small plane offset) AND spatially connected (their
plan footprints touch or overlap). Plane agreement alone is necessary but not
sufficient.

**Why (Emmett's words):** *"Only 19&22 is a real merge. Their plan boxes overlap
and their plane separation is 0.00058 cu, sub-millimetre. Blob 7 and blob 10 are
one physical dormer split into two residual blobs and fitted twice. 24 sits ~6 cu
away in X. It is coplanar but physically separate, almost certainly an identical
dormer elsewhere on the same slope. Merging it would report one facet where two
dormers exist... Identical dormers in a row will always look coplanar and must
remain separate facets."*

This is a property of houses, not a tuning choice: repeated identical dormers on
one roof slope are the normal case, and every one of them is coplanar with every
other by construction. A coplanarity-only rule would collapse them and
under-report facet count on exactly the roofs where dormers matter most.

**Rejected:** Merging on plane agreement alone, which the Task 5 pairwise matrix
would have supported: facets 19, 22 and 24 were mutually flagged (angles 0.413,
0.633 and 0.817 deg; offsets 0.00058, 0.01690 and 0.02302 cu, all well inside 2x
the assignment band). Taking that at face value would have merged three facets
into one and reported a single dormer where two exist.

**Evidence:** `reports/big_house/pairwise-2026-07-23.json`. Facets 19 and 22 sit
at short X[77.9, 79.8] and X[77.6, 78.7] with overlapping plan boxes; facet 24 is
at X[84.3, 85.6], roughly 6 cu away, at the same Y band and the same pitch.
Blobs 1 through 5 each produced exactly 2 facets with opposing normals, which is
5 gabled dormers correctly resolved and must not be touched.

**Status:** the rule is decided; it is NOT yet implemented. It must be applied to
the re-derived canonical facet state, since the facet indices above belong to the
superseded 2026-07-23 state.

**Cost if wrong:** If the adjacency test is too strict, one physical surface split
across two non-touching residual blobs stays split and facet count is
over-reported. If too loose, distinct dormers collapse. The adjacency tolerance
itself is **still unchosen**: no value has been picked, and the choice should
come from the observed gap between the 19/22 overlap and the 19/24 separation
rather than being picked in the abstract.
