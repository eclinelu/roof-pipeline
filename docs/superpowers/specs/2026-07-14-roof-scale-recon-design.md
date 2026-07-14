# Roof-derived scale reconnaissance: design

Date: 2026-07-14
Status: approved in planning session; implementation plan to follow
Dataset: big_house (applies to any dataset via roofkit.json, per the 2026-07-12
config decision, but the roof-as-scale-source usage is a big_house exception)

## Context and goal

The wall scale instrument is retired for big_house: most wall faces have no
coverage (nadir grid capture, trees prevented low flight), so the wall finder
had nothing to find. The roof is the densest, cleanest geometry in this cloud
(8 planes, sub-centimeter scatter). For THIS dataset only, the scale reference
is derived from roof geometry and taped on the roof, which is climbable.

Goal: a reconnaissance script that derives every candidate scale span from
fitted roof geometry, quantifies each one's noise AND bias honestly, reports
where each sits physically, and ranks them, BEFORE the tape comes out. Same
recon-before-tape principle as wall_recon.py (decision 2026-07-14): the cloud
is the fixed thing, the tape is the flexible thing.

Nothing is ever clicked. All spans come from plane fits and constructs derived
from them (decision 2026-07-14: cloud-side scale endpoints are never clicked).

## Standing constraints (from the 2026-07-14 planning session)

1. **Ground truth is audit-only, never a pipeline input.** Permitted pipeline
   inputs: the point cloud, thresholds derived from the cloud, one
   tape-measured scale distance. big_house exception: that one scale tape may
   be taken ON the roof. Every other roof measurement (inclinometer pitches,
   extra tape checks) exists only to score outputs after they are frozen.
2. **Pre-registration protocol.** Outputs (per-facet area and pitch in cloud
   units, eave brackets, the chosen scale span identity and its cloud-unit
   value) are written to an output file and committed BEFORE the field visit.
   That commit hash is the pre-registration. The tape number converts the
   frozen outputs; the audit readings score them in a NEW file. The
   pre-registered file is never edited. Retuning after seeing roof data is a
   second pre-registered run with its own commit; both get reported.
3. **No refly, no ground control markers.** The capture is what it is.
4. **Future properties get scale from the ground** (longest building face at
   grade, footprint diagonal, fixed ground feature pair, in that order). The
   roof route is an exception, logged as such, not a precedent.

## The candidate instruments

Three classes, in order of cleanliness. All are derived; none depend on where
a point cloud edge raggedly stops, except class 3, which is kept only because
its dependence is measured and reported.

### Class 1: parallel facet-plane separation (interior fits only)

The wall trick applied to roof planes: if two facet planes are parallel
(strike AND pitch within tolerance) but offset, their perpendicular separation
is derivable entirely from interior surface points. No edges anywhere.
Checked first because nothing beats it if a pair exists; expected to be a
long shot on this building.

Mechanics follow wall_recon's `sep_at`: fit one plane (trimmed), read the
other facet's signed perpendicular distances as a linear function of position,
evaluate at a chosen spot, swap roles, average. Position sensitivity across
the overlap is reported, because the tape goes to one physical spot.

### Class 2: perpendicular span between parallel derived lines

A perpendicular distance between two well-fit parallel lines does not depend
on where either line ends. Two line families feed this:

- **Intersection lines** (ridges, valleys, hips): plane-plane intersections
  validated by contact points, exactly as `ridge_line` does today. Direction
  quality: essentially exact.
- **Eave lines**: a non-horizontal plane contains exactly one level direction,
  so the eave is EXACTLY parallel to its own ridge, by geometry, not by
  construction. The eave's direction therefore comes free from the plane fit
  (u = normalize(cross(n, z_hat))). Only ONE unknown is estimated from
  boundary points: the eave's position down the slope, averaged along the
  full edge length.

Every pair of parallel lines (within a 2 deg angular tolerance, an angle and
therefore scale-free; divergence is reported per pair) yields a candidate span, evaluated perpendicular to the lines at a stated
position, with position sensitivity reported when the lines are not exactly
parallel. This includes:

- ridge to eave within one facet = **slope length** (bias enters once)
- eave to eave across a gable pair = **horizontal building span** (bias
  enters twice, one eroded edge per side)
- ridge to ridge / any parallel intersection-line pair (no eave bias at all;
  known ridge azimuths 88.6 / 112.6 / 178.5 make this unlikely, but the recon
  enumerates all validated intersection lines, not just the three logged
  ridges)

### Class 3: intersection-line length (ridge length and kin)

Both endpoints of a ridge sit where facets stop overlapping: the eroded,
badly reconstructed edge zone. This is the corner-clicking disease in milder
form, and the erosion is a ONE-SIDED systematic (always shortens) that
split-half repeatability cannot see. Kept as a fallback class with its
endpoint uncertainty measured, not assumed:

- extent estimated by the along-line contact-density edge (see the
  half-density edge estimator below), per end
- sensitivity of each end to the contact radius (re-derived at 0.5x and 2x
  contact_dist), reported per end as a bias bound

## The eave position estimator and the two-cloud bracket

### Position estimator (one parameter)

Project the facet's points onto the in-plane downslope direction
(w = cross(n, u), oriented downhill). The eave position is where the
along-slope point density falls to half its interior median: a half-density
edge. This is robust to stragglers, uses hundreds of points along the edge,
and is the SAME estimator reused for class-3 line extents, so it is validated
once. The exact implementation is pinned by the synthetic test below, where
truth is known.

### Two-cloud bracket (decision: bracket, never a correction)

Erosion has a known sign and an unknown magnitude, and the only magnitude
measurement is the real roof, which constraint 1 forbids as an input. So each
eave position is derived twice from the SAME fitted plane:

- **Tight set** (filtered roof points, the ones segmentation uses): LOWER
  bound on eave extent. Filtering only ever removes boundary points.
- **Loose set** (pre-filter cropped cloud, leveled, gated by (a) perpendicular
  distance to the fitted plane within the segmentation band and (b) an
  in-plane region gate: the tight facet's in-plane footprint dilated by a
  bounded margin along and beyond the eave): UPPER bound. Readmits true eave
  points plus gutter, fascia, and vegetation near the plane.

The in-plane region gate exists because an extended facet plane will
eventually slice terrain or trees far from the facet; without it the loose
set is unbounded contamination.

The plane itself is ALWAYS fit from the tight set. Output per eave: lower,
upper, delta. Never averaged, never half-delta corrected.

**Contamination flag:** an anomalously wide bracket (delta far beyond the
tight set's split-half repeatability and beyond typical shingle-overhang
scale) is reported as a loose-set contamination flag and DISQUALIFIES that
eave as a scale candidate. It is not read as an erosion measurement, and it
is never silently swallowed.

**Three-edges caveat, printed with every bracket:** tight cloud, loose cloud,
and a physical tape may measure three different physical edges (shingle
overhang, fascia, wall line). Disagreement may be geometry, not erosion. The
field notes record which edge the tape actually hooked.

## Error model: bias and noise are never folded together

Per candidate:

- **noise**: split-half repeatability (even/odd point split, full derivation
  re-run per half) combined in quadrature with the tape's centimeter
- **bias bound**: stated SEPARATELY. Eave bracket delta for eave-involved
  spans (once for slope length, twice for eave-to-eave), summed endpoint
  bounds for class-3 lengths, zero for class 1 and pure intersection-line
  pairs
- predicted linear error % = 100 * (sqrt(rep^2 + tape^2) + bias) / span,
  with the noise and bias contributions each printed; area error % = 2x
  linear (area scales as the square of scale)

Ranking is by predicted linear error, but the noise/bias split is visible in
the table, because a candidate with tiny noise and a fat bias bracket is not
better than the reverse. Physical plausibility is judged by Emmett from the
location report, not by the script.

## Output

A ranked table in the wall_recon style: kind, span (cu), split-half rep,
bias bound, noise %, bias %, total linear %, area %, support (point counts),
position sensitivity, and WHERE IT SITS: dx/dy relative to the cloud origin,
height above ground level, which roof section, and the tape plan (what the
tape hooks, where the person stands: ridge walk, ladder at eave, ground with
plumb drops).

Plus a per-eave bracket table: facet, eave azimuth, lower, upper, delta,
contamination flag.

Viewer (skippable with --no-view): facets painted, derived lines drawn
(intersection lines red, tight eaves green, loose eaves yellow), so a weak
derivation is visible as geometry, not just as a number.

## Code architecture

- **`roofkit/measure.py` gains three primitives**, each with synthetic tests:
  - `eave_line(points, normal, ...)`: level in-plane direction plus
    half-density edge position; returns line (point, direction) and
    diagnostics (edge support count, density profile summary)
  - `line_pair_span(...)`: perpendicular separation between two near-parallel
    lines at a stated evaluation position, with angular divergence and
    position sensitivity
  - `line_extent(...)`: along-line half-density edge per end, with per-end
    contact-radius sensitivity (serves class 3)
- **`scripts/roof_recon.py`** orchestrates: load config, crop, level (from
  roofkit.json), reuse the seed-pinned segmentation path measure_roof uses on
  roof.npy, derive everything, bracket eaves against the cropped raw cloud,
  rank, print, view. Thresholds live at the top with scale-dependence stated
  for each (house rule), site-specific values in roofkit.json.
- Nothing new touches file formats: io.py remains the only format seam.

## Synthetic test requirements (the bracket must be proven before real data)

A synthetic gable with known dimensions, deliberately eroded edges (strip the
outermost points to a known depth), plus optional off-plane clutter near the
eave:

1. `eave_line` on the eroded set reads SHORT of truth (lower bound holds);
   on the full set reads within tolerance of truth (upper bound holds); the
   bracket contains truth.
2. Clutter near the eave widens the bracket and trips the contamination
   flag; the flag never fires on the clean case.
3. `line_pair_span` recovers a known ridge-to-eave slope length and is
   INSENSITIVE to removing the ends of either line (the endpoint-free claim,
   tested directly).
4. `line_extent` shortens under erosion and its per-end bias bound covers
   the known erosion depth.
5. Split-half repeatability on the synthetic is small compared to the
   imposed erosion, demonstrating exactly why repeatability alone flatters
   eave candidates (the honesty claim, pinned as a test).

## Decision log entries (recorded alongside this spec)

1. Ground truth is audit-only, never a pipeline input; outputs pre-registered
   by commit before the field visit; big_house roof-tape exception scoped to
   the one scale span.
2. Eave erosion handled by a two-cloud bracket, never a correction; rejected
   the unquantified caveat and rejected dropping eave instruments.
3. Roof-derived scale is a big_house exception; wall instrument retired for
   this dataset (no coverage); ground-based scale remains the rule for
   future properties.

## Out of scope

- Pitch validation fieldwork (inclinometer protocol): nothing to build; the
  pipeline stays ignorant of it. The within-facet inclinometer spread sets
  the comparison floor, composing with the logged 0.20 deg leveling floor.
- Ground-feature scale instruments for future properties: designed when a
  property without roof access arrives.
- 7b edge/dimension extraction generally: this recon derives specific line
  constructs for scale, not the full dimension sheet.
- Any change to isolation: A3 is recorded as held (2026-07-13) and 7a runs
  clean; no isolation work unless contamination is actually observed.

## Open risks

- No class-1 pair and no parallel intersection-line pair may exist; then
  every candidate carries eave bias and the bracket delta decides whether
  the best roof span beats the ~2-6% clicked-corner floor this project
  already refused. If even bracketed candidates predict worse than the 5%
  area budget, that result is reported honestly rather than papered over.
- The half-density edge estimator has one tunable (the density threshold
  fraction); it is fixed at 0.5 by the synthetic tests and documented as
  scale-free. If real eaves have gradual density tails (partial occlusion),
  the bracket widens and says so.
- Vegetation touching eaves is the known adversary; the contamination flag
  is the designed response, and a flagged eave simply exits the ranking.
