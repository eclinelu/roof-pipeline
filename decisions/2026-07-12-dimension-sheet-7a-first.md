### 2026-07-12: Deliverable is a dimension sheet; area ships first as stage 7a

**Decision:** Lengths (eave, ridge, rake, hole dimensions) are the primary reported quantity; areas are derived from them. Measurement is split into 7a (polygon area per facet via alpha shape, built first) and 7b (edge fitting and dimensions, built second). 7a plus per-facet pitch satisfies the done-definition on its own.

**Why:** A tape measure validates lengths directly, so the error report compares like with like. Length errors are linear where area errors are quadratic, so a dimension sheet localizes error to a specific edge instead of hiding it in an aggregate. 7a is built first because edge extraction from a ragged, tree-occluded boundary is likely the hardest stage in the pipeline, and 7a is the afternoon-scale integration test that catches upstream contamination before a week is spent on 7b. Once both exist, 7b-derived areas and 7a polygon areas cross-check each other.

**Rejected:** Area-only definitions (holes-open undercounts by point density rather than geometry; holes-filled is validatable but hides error structure; dormers-as-facets adds small fragile segments). Also rejected: building 7b directly, because the better version must not prevent the finished version.

**Evidence:** Reasoning, not measurement. The claim that 7b is the hardest stage is a judgment call.

**Cost if wrong:** If 7b proves intractable, the project still finishes at 7a. That is the point of the split.
