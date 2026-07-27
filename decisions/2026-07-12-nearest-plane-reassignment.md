### 2026-07-12: RANSAC peeling gets a nearest-plane reassignment pass

**Decision:** `find_roof_planes` reassigns all facet points to their nearest plane after peeling, then refits each plane by least squares (SVD).

**Why:** Greedy peeling is order-dependent: the first-found plane absorbs the neighboring plane's points inside its distance band. At a synthetic gable ridge this stole 424 of 16000 points, inflating one facet's area, deflating the other's, and tilting the first fit by 0.2 degrees. Real roofs have this geometry at every ridge, hip, and valley.

**Rejected:** Tightening the RANSAC band (shrinks the theft strip but throws away legitimate noisy inliers, and turns a geometry problem into threshold tuning). Loosening the test tolerance (hides the bias instead of removing it).

**Evidence:** Stage-by-stage area accounting on the synthetic scene: facet point counts 8300 vs 7592 where 8000/8000 is truth; areas +1.8% and -5.1% against a known 34.641. After the fix: balanced within 3%, pitch within 0.1 degree. Test `test_ridge_points_are_not_stolen_by_the_first_plane` pins it.

**Cost if wrong:** If reassignment is somehow harmful (for example, coplanar facets on separate wings swapping distant points), per-facet membership shifts, though the alpha shape discards isolated distant points so 7a areas are largely protected. The synthetic suite would not catch a regression on non-gable geometries until 7b's dimension checks exist.
