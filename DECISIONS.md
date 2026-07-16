# Decisions and State

## Current state

- **Phase:** Roof-derived scale recon BUILT and run on big_house. Spec `docs/superpowers/specs/2026-07-14-roof-scale-recon-design.md`, plan `docs/superpowers/plans/2026-07-14-roof-scale-recon.md`, executed through `7c932bd`. 46 tests green.
- **Active blocker:** Emmett's reachability judgment, then the deliberate pre-registration freeze. The recon ranked the candidates; the field visit (roof tape for the one scale span, inclinometer audit) waits until the frozen output is committed.
- **Last thing verified working (2026-07-15):** `roof_recon.py` full run on big_house: 8 facets, 18 contact-validated intersection lines (4 true ridges at az 88.6/112.6/125.8/178.5), monotone two-cloud eave brackets (all deltas positive; 4 clean eaves 0.02-0.12 cu, 4 contaminated flagged at 0.44-0.62 cu), 24 ranked scale candidates. Segmentation is bit-identical across fresh processes (verified: per-facet area/pitch/counts and the rank-1 span all match). `preregister.py --dry-run` reproduces the 7a totals (313.19 cu^2). A read-only reachability viewer (`C:\odm\datasets\big_house\big_house_reachability.html`, not committed) draws both spans on the cloud; drawn lengths match the frozen 14.335 / 10.808.
- **Chosen scale span:** PRIMARY `lines:j0,3-j0,5` (perpendicular span across facet 0 between its junctions with facets 3 and 5), 14.335 cu, 0.15% predicted area error, zero edge bias, CONDITIONAL on roof reachability. Documented FALLBACK `length:r6,7` (ridge 6,7), 10.808 cu, 0.79% area, one-sided endpoint bias. Both to be recorded in the freeze.
- **Next action:** (1) Emmett judges reachability from the viewer and on the roof; (2) run `python scripts/preregister.py C:\odm\datasets\big_house --candidate lines:j0,3-j0,5 --fallback length:r6,7` (drop `--dry-run`) and COMMIT the JSON: that commit is the pre-registration; (3) tape the chosen span, put `scale_span_cu` and `scale_true_m` into roofkit.json; (4) the roof tape/inclinometer readings score the frozen file in a NEW comparison file, never editing the pre-registration.
- **Note on the 7a numbers:** totals 313.19 cloud units^2 (matches the earlier 313.00 within area-subsample noise), pitch floor 0.20 deg, pitch classes ~5:12 and ~8:12; leveling values in roofkit.json (1.083 deg, uphill az 75.1); `expected_facets` pinned at 8 as the vanish guard.

---

## Decision log

_Append only. Newest at the top. Past entries are never edited. A reversal is a new entry that references the one it overturns._

### 2026-07-15: The two-cloud eave bracket needs a shared absolute density floor and a guaranteed superset

**Decision:** The loose (upper-bound) eave is read against 0.5 times the tight set's central bin density, not its own, and the loose point set is the distance-gated raw points unioned with the tight core. The loose window extends ~0.62 cu past the tight eave (120 x spacing), and an assertion enforces that the window always stays wider than the 0.4 cu contamination flag.

**Why:** An edge estimator that is correct for measuring one cloud's extent is not valid for comparing two clouds of different density. `_density_edge` finds the eave where point density drops to half of that cloud's own central density. The raw (loose) cloud is 2-10x denser than the filtered (tight) cloud, so half of its own central density is a much higher absolute count. It hits that count while still well inside the roof and reports its edge inboard of the tight edge, even though it physically holds strictly more points reaching further out. That is how the upper bound fell below the lower bound on 4 of 8 facets. Two fixes make the bracket honest: anchor both sets to one absolute floor (half the tight set's central density) so the comparison is density-independent, and union the tight core into the loose set so "loose is a superset of tight" is true by construction rather than assumed, guaranteeing delta >= 0. A bracket whose upper bound can dip below its lower bound is not a bound; making it provably monotone is what lets it be trusted as a real enclosure of the true eave, which is the whole premise of the erosion instrument.

**Rejected:** Clamping negative deltas to zero and reporting "erosion within noise": that prints a physical claim the data does not support, over a still-broken estimator, which is the odm_filterpoints failure shape (confident, unverified). Duplicating the density-edge logic into the script to keep roofkit frozen: freezing protects committed outputs, not uncommitted code, so there was nothing to protect and no reason to pay the duplication cost.

**Evidence:** big_house run of 2026-07-15. Under the old relative floor, deltas on facets 0/2/3/5 were negative (-0.02 to -0.27). The isolation experiment (widen window first, relative floor unchanged) showed facet 6 grow 0.146 to 0.395, proving the deltas were also window-clipped. After the shared floor plus union superset plus widened window: all eight deltas positive; clean eaves 0.02 to 0.12 cu, contaminated eaves 0.44 to 0.62 cu, a 0.31 cu separation; 46 tests green.

**Cost if wrong:** If the tight central density is itself unreliable on a sparse facet, its floor (half of a small number) is low, and a dense loose set clears it far out, so a sparse-tight eave reads contaminated on faint clutter. That is the safe direction (it flags and excludes rather than admitting a bad eave), but it can retire an eave that a better instrument would have kept. Second cost: if the window is ever narrowed below the flag threshold, contaminated eaves get clipped under the flag and misread as clean, silently admitting a bad scale candidate; the window_margin > flag_threshold assertion guards this.

---

### 2026-07-14: Roof-derived scale is a big_house exception; the wall instrument is retired for this dataset

**Decision:** For big_house, the scale span is derived from roof geometry and taped on the roof. This is an exception, logged so it cannot quietly become the pattern: future properties get scale from the ground (longest building face at grade, footprint corner-to-corner diagonal, fixed ground feature pair, in that priority order), because future roofs will not be climbable and roof measurements there are audit-only.

**Why:** The wall finder failed because most walls have no coverage at all (nadir grid capture, trees prevented low flight), not because of thresholds; no code fixes absent data, and there is no refly. The roof is this cloud's best-reconstructed geometry by a wide margin (8 planes, sub-centimeter scatter), and the fit-from-good-data principle points the scale instrument at it. The 2026-07-14 candidate span (face 7 to the 0/2/4 facade plane) is retired along with the corner instrument.

**Rejected:** Recapturing with wall-oriented flight (no refly available). Ground control markers (same). Deriving scale from ground features on this dataset before exhausting the roof, which is strictly better-reconstructed geometry.

**Evidence:** wall_recon.py runs of 2026-07-14 (8 faces, all ~E/W, zero corner contact) plus Emmett's field knowledge of which walls the capture could see. Roof quality numbers from the 7a runs.

**Cost if wrong:** If the roof-derived span carries hidden edge bias into the scale multiplier, every area is wrong by its square. The recon's bias accounting (see the bracket entry) exists to surface that before the tape is chosen.

---

### 2026-07-14: Eave erosion is handled by a two-cloud bracket, never a correction

**Decision:** An eave line's direction is never fitted from boundary points: a non-horizontal plane contains exactly one level direction, so the eave is exactly parallel to its own ridge and its direction comes free from the plane fit. Only the eave's downslope position is estimated, twice, from the same tight-set plane fit: from the filtered roof points (tight set, LOWER bound, because filtering only removes boundary points) and from the pre-filter cropped cloud gated only by perpendicular distance to the facet plane plus an in-plane region gate (loose set, UPPER bound, because it readmits true eave points along with gutter, fascia, and vegetation). Output per eave is lower, upper, delta. No averaging, no half-delta correction. An anomalously wide bracket is flagged as loose-set contamination and disqualifies that eave as a scale candidate; it is not read as an erosion measurement. Tight, loose, and a physical tape may be measuring three different physical edges (shingle overhang, fascia, wall line); disagreement is noted as possible geometry, not attributed to erosion.

**Why:** Erosion has a known sign and an unknown magnitude, and the only way to measure the magnitude is the real roof, which the audit-only entry forbids as a pipeline input. A bracket is derivable from the cloud alone, so it generalizes to properties with no roof access. Split-half repeatability cannot see erosion because it is a bias, not noise: both halves are eroded identically, so repeatability flatters every edge-derived quantity.

**Rejected:** Reporting erosion as an unquantified caveat: this log already records the cost of a confidently written unverified claim (the odm_filterpoints entry). Dropping eave instruments entirely: it deletes the only ground-tapeable long baseline and does not escape the failure mode anyway, since ridge endpoints erode for the same reason eave corners do. Calibrating an erosion correction from roof measurements: the exact leak the audit-only entry exists to stop.

**Evidence:** Reasoning plus the geometry fact (unique level direction of a non-horizontal plane). The bracket's validity is to be pinned by synthetic eroded-gable tests where truth is known, before it touches real data; until those pass, this entry rests on design, not measurement.

**Cost if wrong:** If the loose gate is too tight, the bracket understates erosion and every reported dimension carries uncertainty that looks smaller than it is. The bracket is only as honest as its contamination flag.

---

### 2026-07-14: Ground truth is audit-only, never a pipeline input; outputs are pre-registered by commit

**Decision:** The pipeline's permitted inputs are exactly three: the point cloud, thresholds derived from the cloud, and one tape-measured scale distance (on big_house, and only there, that tape may be taken on the roof; see the exception entry). All other field measurements (inclinometer pitches, extra tape checks) exist only to score outputs after they are frozen. Enforcement is procedural: (1) run with frozen thresholds, (2) write per-facet area and pitch in cloud units, the eave brackets, and the chosen scale span's identity and cloud-unit value to an output file, (3) commit, and that hash is the pre-registration, (4) only then measure the real roof, (5) the comparison goes in a NEW file and the pre-registered output is never edited. Retuning after seeing roof data is legitimate but becomes a second pre-registered run with its own commit, and both runs are reported.

**Why:** big_house is climbable; future properties are not. Roof access is therefore an audit channel, and any roof-derived number that leaks into a parameter makes the validation circular and the pipeline non-portable. Because roof numbers are physically obtainable here, the discipline cannot rest on intent; the commit hash makes it checkable by a third party.

**Rejected:** Using roof measurements to calibrate an erosion correction, the most tempting use of them and the exact leak this rule exists to stop. Trusting intent without the commit protocol.

**Evidence:** Protocol decision from the 2026-07-14 planning session; nothing to measure yet. The first pre-registration commit will be the first evidence it is being followed.

**Cost if wrong:** If the procedure is bypassed even once, silently, the validation becomes uninterpretable, and the validation is the deliverable.

---

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
