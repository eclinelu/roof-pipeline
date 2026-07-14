# Decisions and State

## Current state

- **Phase:** 7a complete on the leveled cloud. Tape-scale validation: cloud side done, waiting on Emmett's field visit.
- **Active blocker:** Emmett must (1) run `python scripts/wall_recon.py C:\odm\datasets\big_house` and identify the painted walls physically: the candidate span is face 7 (brown) to the near-coplanar 0/2/4 facade plane (blue/green/cyan), ~6.93 cu, near dx=24 dy=36; (2) report reachability, what connects the two planes (square or oblique face), and corner trim construction; (3) tape it, ~1 cm accuracy; (4) run `measure_scale.py --click-spread` (5 clicks on one corner) so the old click instrument's error is a measured number.
- **Last thing verified working:** wall_recon.py full run on big_house (2026-07-14): 8 wall faces, 0 derivable corners, 3 parallel-plane readings of the one candidate span, split-half repeatability 0.9-2.4 mm, predicted ~0.3% area error. 32 tests green. Everything committed through `506a302`.
- **Next action after the tape number arrives:** put `scale_span_cu` (evaluated at the taped location, using pos-sens) and `scale_true_m` into `C:\odm\datasets\big_house\roofkit.json`; `measure_roof.py` then prints the 7a report in m^2 plus the measured GPS scale error, which gets its own log entry (the last untested georeferencing assumption; rotation is already measured and corrected). Fallbacks if unreachable: `measure_scale.py` manual patch picking on any reachable wall pair, or force-evaluating the face 3/5 pair (wing D width) that the overlap gate excludes.
- **Note on the 7a numbers:** current totals are 313.00 cloud units^2, pitch floor 0.20 deg, pitch classes ~5:12 and ~8:12; leveling values live in roofkit.json (1.083 deg, uphill az 75.1).

---

## Decision log

_Append only. Newest at the top. Past entries are never edited. A reversal is a new entry that references the one it overturns._

### 2026-07-14: Constraint discovered: this cloud has no derivable wall corner; parallel-plane separation is the scale instrument

**Decision:** The scale span for big_house is the perpendicular separation between wall face 7 and the near-coplanar 0/2/4 facade plane (~6.93 cloud units, three readings 6.931/6.934/6.960 whose 26 mm spread is the real offset within the coplanar family), pending Emmett's reachability check. The corner-to-corner instrument is retired for this dataset: it has no target.

**Why:** The north/south-facing wall sets never reconstructed (nadir grid capture; confirmed with relaxed gates and 30 RANSAC peels, not just default thresholds), and every geometrically possible corner pair failed contact validation with zero points near the intersection line: the reconstructed walls do not physically adjoin. A parallel-plane separation needs no corner anywhere; taping it flat across a connecting face introduces only sec(skew), and the skew is measured from the cloud when the connecting face reconstructed, not assumed.

**Rejected:** Deriving corners by extrapolating wall planes to intersections without contact support (a jog or plane change beyond the reconstructed patch would be invisible). Relaxing corner gates further (the walls are absent, not filtered).

**Evidence:** wall_recon.py runs of 2026-07-14: 8 wall faces, scatter 0.003-0.006 cu, all facing ~E/W; corner contact counts 0/0 for every candidate pair; split-half repeatability of the candidate span 0.9-2.4 mm; predicted error ~0.15% linear, ~0.3% on area, versus 2-6% for clicked corners.

**Cost if wrong:** If the taped faces do not match the derived planes (proud corner trim, hidden jogs), the scale factor carries a centimeter-scale systematic; the three near-coplanar readings 26 mm apart exist to catch exactly that, and the trim construction is recorded at taping time.

---

### 2026-07-14: Scale span is derived from wall-plane geometry, never from clicked corners; reconnaissance runs before the tape

**Decision:** Cloud-side scale endpoints are never clicked. Spans are derived from plane fits to well-reconstructed wall interiors (the ridge instrument's logic pointed at walls), and wall_recon.py runs BEFORE the tape measurement so the tape goes to the edge the cloud measures best. The predicted error of a candidate is computed from its split-half repeatability plus the tape's centimeter, and the choice is made on that number.

**Why:** A corner in a point cloud is a fuzzy cluster where two fuzzy surfaces meet, and ODM reconstructs edges worse than surfaces; clicking one samples the scene's worst data (est. 5-15 cm per end, 2-6% on area, alone exceeding the 5% budget). A plane fit to thousands of surface points puts the derived geometry at millimeter repeatability. The cloud is the fixed thing and the tape is the flexible thing, so the measurement site is chosen by the instrument, not by habit.

**Rejected:** Taping first and reconstructing whatever was taped. Clicking endpoints with a repeat-click spread as the error bar (quantifies the noise instead of removing it).

**Evidence:** Split-half repeatability 0.9-2.4 mm on a ~7 m span (2026-07-14 runs). The click-spread control experiment (measure_scale.py --click-spread) is still to be run so the old instrument's error is measured, not estimated.

**Cost if wrong:** If wall surfaces are systematically biased (vegetation shadowing, siding relief), plane-derived spans inherit it invisibly; the tape comparison itself is the check, since a factor far from 1.0 beyond GPS-plausible scale error would expose it.

---

### 2026-07-13: Leveling applied from the three-ridge least squares; null check passed; pitch floor is 0.20 degrees

**Decision:** big_house is leveled by 1.083 degrees, uphill azimuth 75.1: the least-squares tilt over all three validated ridges, applied in measure_roof.py before any coordinate is read, from values stored in roofkit.json. The pitch uncertainty floor is 0.20 degrees, the worst residual ridge inclination after leveling. Diagnostics now print in cloud units, never cm/m, because labeling unverified GPS scale as a real unit presents an assumption as fact.

**Why:** A third true ridge pair (4,5, ridge azimuth 112.6, contact fractions 0.99/0.99, ~15k contact points) validated and read +0.66 where the two-ridge model predicts ~1.05, so the three ridges are inconsistent with a single rigid tilt at the ~0.2 degree level. Using only the two ridges that match the previously approved answer would be anchoring, the exact failure mode this log keeps recording. The scatter across all three is the instrument's honest limit and becomes the reported floor.

**Rejected:** Leveling by the approved two-ridge vector (logged as 1.25 at azimuth 81.3; reproduced by the committed instrument as 1.24 at 80.6). It forces the full 0.39 degree inconsistency onto pair 4,5 by construction instead of exposing it as shared instrument scatter.

**Evidence:** Post-leveling, the ridges re-read +0.18 / -0.20 / +0.08 and the residual tilt vector reads 0.001 degrees: the null check the reversal entry required, passed. "Uphill azimuth" in that entry is empirically confirmed by the null (the opposite sign would have doubled the readings to ~2.5). HYPOTHESIS KILLED, recorded rather than quietly dropped: the reversal's prediction that ~1.2 degrees of genuine building asymmetry would survive on pair 1,3 (Emmett's hypothesis) did NOT reproduce. Observed 0.47, and every pair asymmetry collapsed after leveling (0.72 to 0.47, 0.84 to 0.18, 1.17 to 0.12). The building is substantially more symmetric than that entry estimated. Seed-pinned runs of 2026-07-13.

**Cost if wrong:** If ridge 4,5 is genuinely non-level (a sagged or rebuilt ridge beam) rather than instrument noise, the true tilt is nearer the two-ridge value and every pitch carries up to ~0.2 degrees of extra bias, which is already inside the reported floor.

---

### 2026-07-13: REVERSAL: Z is tilted 1.25 degrees; ridge inclination replaces the symmetry gate as the primary vertical reference

**Decision:** Georeferenced Z is rejected for big_house: measured tilt 1.25 degrees, uphill azimuth 81.3, from the ridge instrument. The cloud is leveled by this vector before all measurement. Ridge-line inclination becomes this project's primary vertical reference; the opposing-facet symmetry residual is demoted to an asymmetry report, and only ridge-validated pairs count as instruments at all.

**Why (the reasoning is the deliverable here, not the number):**

1. The symmetry gate was a flawed instrument, and specifically why: it assumed any two facets facing opposite directions form a gable. Pair 0,2 met at mid-height, not at a ridge; it was never a gable pair, so its 0.10 residual was never evidence about anything, and the earlier 0.85 conclusion was anchored to it. The failure mode is a plausible instrument reading confidently and being wrong, not a noisy number.
2. The ridge method is better because it assumes less. Ridges are level in the real world. Two ridges running roughly orthogonal fully determine which way is up, with no symmetry assumption anywhere. That is why it can be trusted where the gate could not.
3. The cross-validation is what makes it trustworthy: the ridge fit PREDICTED pair 6,7's symmetry residual at 1.24 degrees, and the independent symmetry measurement read 1.17. Two unrelated instruments agreeing is the evidence. Without that, this is just a second story replacing a first one.
4. Facet 7 was innocent. The contamination hypothesis was wrong. The trimmed refit stays (cleaner fits, cleaner membership) but it did not fix anything and is not credited with it.
5. Tilt and building asymmetry are now separated, and that separation is the real result. 1.25 degrees is instrument error and is correctable. The ~1.2 degrees surviving on pair 1,3 after leveling is the house being genuinely asymmetric, which is normal on an old roof and is not an error to chase to zero. It is reported as a measured property of the building.

**Rejected:** Leveling from the facet-normal bisector (it assumes exactly the symmetry that pair 1,3 measurably lacks). Widening the gate (standing instruction).

**Evidence:** Ridge inclinations +1.239 degrees (ridge az 88.6) and -0.157 (az 178.5), ~1,400 contact points each; contact-height fractions 0.95/0.95 for both true ridge pairs versus 0.48/0.55 for pair 0,2; the cross-validation in point 3. Diagnostic runs of 2026-07-13.

**Cost if wrong:** If the ridge extraction is biased (asymmetric contact zones, curved ridge lines), the leveling bakes that bias in. Checked empirically: after leveling, re-measured ridge inclinations must read ~0.

**Reverses:** 2026-07-13 "Z gate first reading: a ~0.85 degree rigid tilt is the pitch uncertainty floor."

---

### 2026-07-13: Z gate first reading: a ~0.85 degree rigid tilt is the pitch uncertainty floor

**Decision:** The big_house cloud's georeferenced Z is accepted as the vertical reference per the gate protocol (worst-pair residual 0.84 degrees, limit 1.0), and 0.85 degrees is recorded as the uncertainty floor on every pitch from this cloud. This is not treated as a pass to be forgotten: it consumes roughly a third of the 2-3 degree pitch error budget and appears in the report footer.

**Why:** Three opposing facet pairs at distinct compass axes read residuals 0.10, 0.72, 0.84. A single rigid tilt predicts residuals proportional to the cosine between each pair's axis and the tilt direction; a tilt of ~0.85-0.9 degrees with maximum sensitivity near azimuth 20 fits all three. The residuals were stable under the robust trimmed refit (0.14/0.70/0.89 before, 0.10/0.72/0.84 after), which rules out facet clutter as their cause: this is genuine cloud lean from GPS-based georeferencing.

**Rejected:** Leveling the cloud now. The bisector instrument's own accuracy is bounded by the same pair asymmetries (~0.1-0.8 degrees), so leveling would trade a measured, reported bias for a partially unknown one. Also rejected: widening the gate (standing instruction).

**Evidence:** Two runs of measure_roof.py on big_house, 2026-07-13, before and after the trimmed refit. Caveats recorded as part of the evidence: (1) run 1's worst pair read 1.31 degrees, but its smaller facet (~3.7% of points, azimuth ~89) was not rediscovered in run 2, so the clutter-contamination hypothesis for that pair is UNTESTED, not proven. (2) Open3D RANSAC exposes no seed, so plane discovery is nondeterministic and facets near the min_points_frac floor flicker between runs; reproducibility fix pending.

**Cost if wrong:** If the tilt estimate is off, every reported pitch is biased by the difference. If the vanished facet returns with a large residual not explained by clutter, the floor rises and this entry gets reversed.

---

### 2026-07-13: Assumption A3 held: one global height cutoff cleared sloped terrain

**Decision:** The staged isolation (crop, height cutoff at z_min 246.5, ExG color filter, planarity filter) is accepted as verified for big_house. `roof.npy` (9,293,239 points) is the input to segmentation. Assumption A3, that a single global z_min removes all ground on a sloped woodland site, held and is no longer an open risk.

**Why:** A3 was the isolation design's open risk: on sloped terrain, a cutoff low enough to keep the eaves could have let uphill ground through. The z_min was deliberately biased toward the eave (1.4 m below the lowest eave pick, 3.6 m above the uphill ground pick) to buy margin against unsampled terrain, and the margin proved sufficient.

**Evidence:** Emmett's stage-by-stage visual verification at the viewer, 2026-07-13. No uphill terrain survived stage 2. Counts: raw 21,325,293, crop 21,308,532, height cutoff 17,303,825, color 16,885,409, planarity 9,293,239. Two counts that look wrong but are correct: the crop removed only 0.08% because ODM reconstructed only the immediate surroundings (no woodland existed to cut), and ExG removed only 2.4% because this canopy is mostly dark and brown, leaving the residue for the planarity filter exactly as the two-filter design intended.

**Cost if wrong:** If the visual check missed surviving ground or foliage, the contamination surfaces in the 7a per-facet areas, which is the integration test's job to expose.

---

### 2026-07-12: RANSAC peeling gets a nearest-plane reassignment pass

**Decision:** `find_roof_planes` reassigns all facet points to their nearest plane after peeling, then refits each plane by least squares (SVD).

**Why:** Greedy peeling is order-dependent: the first-found plane absorbs the neighboring plane's points inside its distance band. At a synthetic gable ridge this stole 424 of 16000 points, inflating one facet's area, deflating the other's, and tilting the first fit by 0.2 degrees. Real roofs have this geometry at every ridge, hip, and valley.

**Rejected:** Tightening the RANSAC band (shrinks the theft strip but throws away legitimate noisy inliers, and turns a geometry problem into threshold tuning). Loosening the test tolerance (hides the bias instead of removing it).

**Evidence:** Stage-by-stage area accounting on the synthetic scene: facet point counts 8300 vs 7592 where 8000/8000 is truth; areas +1.8% and -5.1% against a known 34.641. After the fix: balanced within 3%, pitch within 0.1 degree. Test `test_ridge_points_are_not_stolen_by_the_first_plane` pins it.

**Cost if wrong:** If reassignment is somehow harmful (for example, coplanar facets on separate wings swapping distant points), per-facet membership shifts, though the alpha shape discards isolated distant points so 7a areas are largely protected. The synthetic suite would not catch a regression on non-gable geometries until 7b's dimension checks exist.

---

### 2026-07-12: Site-specific numbers live in a per-dataset config file, not in code

**Decision:** Pipeline scripts are dataset-agnostic and take a dataset directory as an argument. All site-specific values (crop box, height cutoff, tuned filter cutoffs) live in `<dataset>\roofkit.json` next to the data. No dataset name appears in any module, script name, or constant.

**Why:** The pipeline must work for any cloud put into it. Site-specific numbers describe a dataset, not the algorithm, so they belong with the dataset. This is the io.py seam principle applied to configuration: swap the dataset, nothing in the code changes. It also keeps the repo holding only code, per the existing workspace split.

**Rejected:** Scripts named after and hardcoded to one dataset (the plan's first draft did this and was caught in review).

**Cost if wrong:** If a knob that is actually algorithmic gets pushed into per-dataset config, every dataset re-tunes something that should have one defended value. The config template documents which knobs are site-specific versus scale-derived to resist this.

---

### 2026-07-12: Deliverable is a dimension sheet; area ships first as stage 7a

**Decision:** Lengths (eave, ridge, rake, hole dimensions) are the primary reported quantity; areas are derived from them. Measurement is split into 7a (polygon area per facet via alpha shape, built first) and 7b (edge fitting and dimensions, built second). 7a plus per-facet pitch satisfies the done-definition on its own.

**Why:** A tape measure validates lengths directly, so the error report compares like with like. Length errors are linear where area errors are quadratic, so a dimension sheet localizes error to a specific edge instead of hiding it in an aggregate. 7a is built first because edge extraction from a ragged, tree-occluded boundary is likely the hardest stage in the pipeline, and 7a is the afternoon-scale integration test that catches upstream contamination before a week is spent on 7b. Once both exist, 7b-derived areas and 7a polygon areas cross-check each other.

**Rejected:** Area-only definitions (holes-open undercounts by point density rather than geometry; holes-filled is validatable but hides error structure; dormers-as-facets adds small fragile segments). Also rejected: building 7b directly, because the better version must not prevent the finished version.

**Evidence:** Reasoning, not measurement. The claim that 7b is the hardest stage is a judgment call.

**Cost if wrong:** If 7b proves intractable, the project still finishes at 7a. That is the point of the split.

---

### 2026-07-12: Vegetation removed by color then planarity; rests on the roof-is-not-green assumption

**Decision:** Two sequential per-point filters before segmentation: Excess Green (`ExG = 2G - R - B`, unitless) removes the green canopy bulk, then a local planarity score (neighborhood covariance eigenvalues, unitless cutoff, radius derived from median point spacing) removes the gray/brown residue.

**Why:** Trees touch the roof, so position filters cannot separate them; only per-point signals can. Color and local geometry are independent signals with non-overlapping failure modes: color misses shadowed and dead foliage, planarity erodes roof edges and ridges. A foliage point must be both non-green and locally sheet-like to survive both, which is rare in canopy.

**Explicit assumption:** the roof is not green. True for big_house (gray shingle, verified visually) and this is the only reason ExG works. It fails outright on a green-painted, moss-covered, or copper-patina roof; on such a roof stage 3 must be disabled and planarity carries the whole job.

**Rejected:** RANSAC alone (foliage within the inlier band of a real facet gets counted as roof, inflating area and skewing pitch, silently). Normal-direction filtering (foliage normals are random, per the 2026-07-12 adversary entry). Planarity alone (its edge-erosion failure mode would have no backstop).

**Evidence:** Visual inspection: gray shingle roof, green July canopy. Filter effectiveness on this cloud is assumption, not verified; the per-stage visual checks are the verification plan.

**Cost if wrong:** Surviving foliage contaminates facets and inflates area; over-aggressive filtering erodes facet boundaries and shrinks it. Both are caught by the stage 7a integration test if the visual checks miss them.

---

### 2026-07-12: No ground-plane RANSAC; vertical is georeferenced Z behind a symmetry gate

**Decision:** Ground and walls are removed by crop plus height cutoff only. The vertical reference for pitch is the cloud's georeferenced Z axis, and it is gated, not trusted: on a gable, half the pitch difference between opposing facets measures residual Z tilt. Residual at or below 1 degree: accept Z, report the residual as the pitch uncertainty floor. Above 1 degree: reject Z and level using the bisector of the opposing facet normals.

**Why:** Two independent reasons to drop the tyco ground-plane method here. Removal: on fragmented sloped woodland, the largest plane RANSAC finds may be a roof facet, not ground, since the roof is the densest continuous surface. Leveling: ground normal equals up only on flat ground; leveling to this hillside would inject the terrain slope into every pitch. Meanwhile georeferenced Z comes from meter-grade GPS whose accuracy as a gravity reference is unquantified, so it must be measured before any pitch is reported. The building's own symmetry is the instrument. The 1 degree gate is scale-independent (an angle) and sits comfortably below the roughly 3 degree spacing of adjacent standard pitches, so a passing residual cannot cause a pitch-class misread.

**Rejected:** `fit_ground_plane` plus `level_cloud` as used on tyco (both premises broken on this site). CSF cloth-simulation ground filtering (handles slope but adds a dependency this cloud does not need).

**Evidence:** Terrain slope and roof density from visual inspection of the rendered cloud. Georeferenced Z accuracy: assumption, not verified; the gate exists precisely because of that.

**Cost if wrong:** If the gate threshold is too loose, every pitch carries up to 1 degree of hidden bias. If the house turns out to have no symmetric gable pair, the gate has no instrument and a fallback reference must be designed.

---

### 2026-07-12: The adversary is vegetation, not walls

**Decision:** Roof isolation must be designed primarily against overhanging trees, not against walls.

**Why:** The original plan assumed walls would dominate RANSAC, based on the Tyco orbit footage. The `big_house` capture was a nadir grid, so walls reconstruct thin and partial while the roof is dense. Walls are no longer the problem. Trees overhang the roof directly, and foliage normals are random rather than horizontal, so a normal-direction filter (the obvious wall filter) will not remove them.

**Rejected:** Building the wall-removal filter as originally planned. It solves a problem this cloud no longer has.

**Evidence:** Visual inspection of the rendered `big_house` cloud. Roof surface is continuous and dense; walls are fragmentary; trees are clearly intersecting the roof volume.

**Cost if wrong:** Foliage points get counted as roof, inflating total area. Area error scales directly with contaminated points.

---

### 2026-07-12: ODM must run past odm_filterpoints to produce a point cloud

**Decision:** Do not stop ODM at `--end-with odm_filterpoints`.

**Why:** `odm_filterpoints` does not write `odm_georeferenced_model.laz`. A later stage does. Two full runs were completed with the early stop and neither produced a point cloud.

**Rejected:** Stopping early to skip mesh generation. The intent was sound (the mesh is never consumed by this project) but the stop point was attached to the wrong stage, so it skipped the deliverable along with the mesh.

**Evidence:** Two failed runs producing no `.laz`. Corrected stage order confirmed against the ODM run log rather than from assumption.

**Cost if wrong:** One full ODM run wasted per occurrence, roughly one to three hours on a 232-image dataset.

**Note:** This entry exists as much as a warning about method as about ODM. The original wrong instruction was written into both `CLAUDE.md` and the `odm-run` skill as a confident "lesson learned," and was then followed twice. Written-down claims about tool behavior must be checked against tool output.

---

### 2026-07-12: Claude Code writes the analysis code; the gate is explanation, not authorship

**Decision:** Claude Code writes the analysis core (segmentation, geometry, measurement). Emmett no longer hand-types it. The acceptance gate is that no code enters `roofkit/` unless Emmett can explain the approach, justify every threshold, and state whether it is scale-dependent.

**Why:** The original rule required hand-typing the analysis core so it could be defended in an interview. On reflection, typing was a means to understanding, not the source of it, and a slow one. The defensible content of this project is the design: the ODM-versus-own-code seam, the isolation strategy, the facet definition, the error analysis. That survives a change of authorship. The ability to explain does not survive skipping the gate.

**Rejected:** Continuing to hand-type. Rejected on speed. Also rejected: dropping the gate entirely, which would turn a portfolio project into a demo.

**Cost if wrong:** If the gate is not actually enforced, this becomes code that cannot be defended under questioning, and the project loses its entire purpose.

**Reverses:** The original project rule that Emmett writes all analysis code by hand.

---

### 2026-07-12: Scale comes from one tape-measured ground distance

**Decision:** Real-world scale is locked using a single tape-measured distance captured on site, not from GPS.

**Why:** The reconstruction has correct shape and proportion but is off by a single scale multiplier. One true length resolves it. Meter-grade GPS is far too coarse for a single building (20 to 40 m baseline gives roughly 3% linear error, which becomes roughly 6% area error, since area scales as the square of the linear error). Measuring the longest available clean edge dilutes tape error: 2 cm on 10 m is 0.2%.

**Rejected:** GPS-derived scale, on accuracy. Rejected: multiple control points, as unnecessary for a single-multiplier correction.

**Evidence:** Ground distance measured on site during the July 11-12 capture.

**Cost if wrong:** Area error scales as the square of the scale error. This is the single most sensitive input in the pipeline.
