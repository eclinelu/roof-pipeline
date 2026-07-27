### 2026-07-13: Assumption A3 held: one global height cutoff cleared sloped terrain

**Decision:** The staged isolation (crop, height cutoff at z_min 246.5, ExG color filter, planarity filter) is accepted as verified for big_house. `roof.npy` (9,293,239 points) is the input to segmentation. Assumption A3, that a single global z_min removes all ground on a sloped woodland site, held and is no longer an open risk.

**Why:** A3 was the isolation design's open risk: on sloped terrain, a cutoff low enough to keep the eaves could have let uphill ground through. The z_min was deliberately biased toward the eave (1.4 m below the lowest eave pick, 3.6 m above the uphill ground pick) to buy margin against unsampled terrain, and the margin proved sufficient.

**Evidence:** Emmett's stage-by-stage visual verification at the viewer, 2026-07-13. No uphill terrain survived stage 2. Counts: raw 21,325,293, crop 21,308,532, height cutoff 17,303,825, color 16,885,409, planarity 9,293,239. Two counts that look wrong but are correct: the crop removed only 0.08% because ODM reconstructed only the immediate surroundings (no woodland existed to cut), and ExG removed only 2.4% because this canopy is mostly dark and brown, leaving the residue for the planarity filter exactly as the two-filter design intended.

**Cost if wrong:** If the visual check missed surviving ground or foliage, the contamination surfaces in the 7a per-facet areas, which is the integration test's job to expose.
