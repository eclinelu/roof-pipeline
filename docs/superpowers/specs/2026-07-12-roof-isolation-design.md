# Roof Isolation and Measurement Design: big_house

Date: 2026-07-12
Status: awaiting Emmett's review
Scope: Phase 2 (roof isolation) through Phase 3 (measurement) for the `big_house` cloud.

## Goal

Isolate the roof from `C:\odm\datasets\big_house\odm_georeferencing\odm_georeferenced_model.laz`
(80 MB, 232 Mavic Mini nadir images) so plane segmentation runs on roof facets
alone, then measure per-facet pitch and area, then per-facet dimensions.

**Done-definition (unchanged from CLAUDE.md):** total roof area and per-facet
pitch, validated against a roof of known dimensions, error quantified and
reported honestly. Stage 7a below satisfies this on its own. Stage 7b exceeds it.

## Inputs

- The georeferenced `.laz` above. Because it is georeferenced (Mavic Mini
  geotags every image), the cloud is approximately in meters (UTM coordinates)
  and Z points approximately up. This differs from the no-GPS tyco cloud, which
  was in arbitrary units and arbitrary orientation.
- Per-point RGB, already readable via `roofkit.io.load_xyz_rgb`.
- One tape-measured ground distance for the scale lock (existing decision,
  2026-07-12: scale from tape, not GPS).

## Explicit assumptions

Each assumption is stated with its failure mode and the test that verifies it.
None is treated as solved.

**A1. The roof is not green.** The color filter (stage 3) removes vegetation by
greenness. This works here because the big_house roof is gray shingle, verified
visually. It fails outright on a green-painted roof, a moss-covered roof, or a
copper roof with green patina. If this pipeline is ever pointed at such a roof,
stage 3 must be disabled or replaced, and stage 4 carries the whole vegetation
job alone.

**A2. Georeferenced Z is vertical.** Every pitch number depends on this. The Z
axis comes from meter-grade Mavic Mini GPS, whose accuracy as a gravity
reference is unquantified. This assumption is therefore gated, not trusted: see
the Z-verification gate below. If the gate fails, the cloud gets leveled and
georeferenced Z is abandoned as the reference.

**A3. After cropping, the roof is the highest dense structure.** This is what
makes a plain height cutoff (stage 2) a valid ground-and-wall remover. It fails
if the wooded terrain on the uphill side approaches eave height inside the crop
box. Verified visually when the cutoff is chosen.

## Pipeline

Every stage takes plain NumPy arrays and returns plain NumPy arrays.
`roofkit/io.py` remains the only module that touches file formats. Each stage
ends with a visual check before the next stage is trusted.

**1. Load and crop.** `load_xyz_rgb`, then the existing `crop_box` with a box
chosen visually (same workflow as tyco). Site-specific by nature.

**2. Height cutoff.** Drop all points below approximately eave height, chosen
visually. Removes the sloped fragmented ground and the thin partial walls in one
stroke. There is deliberately no ground-plane RANSAC anywhere in this pipeline:
on fragmented sloped woodland the largest plane in the cloud may well be a roof
facet, so RANSAC "ground" detection could silently return a piece of the roof.

**3. Color filter (vegetation index).** Compute Excess Green per point,
`ExG = 2G - R - B`, and drop points above a cutoff. Foliage in July scores high;
gray shingle scores near zero. Removes the bulk of the canopy for one line of
NumPy. Known residue: shadowed foliage (desaturates toward gray) and dead
branches (brown) survive. Rests on assumption A1.

**4. Local planarity filter.** For each surviving point, examine its neighbors
within a radius and score how sheet-like the neighborhood is. Formally: the
covariance eigenvalues of the neighborhood; the score is the fraction of scatter
that lies off the best-fit local plane (surface variation). In plain language:
does the world around this point look like a sheet or like confetti? Roof points
are sheet-like; the foliage residue from stage 3 is confetti. This attacks the
same property that defeats a normal-direction filter (random foliage normals)
but from the side that works. Known cost: roof edges, ridges, and dormer
junctions also score somewhat rough, so an aggressive cutoff erodes facet
boundaries. The cutoff is tuned visually against that tradeoff.

Stages 3 and 4 are deliberately sequenced: their failure modes do not overlap.
A foliage point must be both non-green and locally sheet-like to survive both,
and that combination is rare in a canopy.

**5. Facet segmentation.** Iterative RANSAC plane peeling with a pitch band,
same shape as the existing `find_roof_planes` (largest plane, keep if pitched
like a roof, remove, repeat). Visual check with per-facet colors.

**6. Z-verification gate, then pitch.** Before any pitch number is trusted or
reported, verify assumption A2 using the building's own symmetry: on a gable,
the two opposing facets must show equal and opposite pitch. Half the difference
between the two measured pitches is the residual tilt of the Z axis. The
residual is computed and reported first, as a gate:

- Residual at or below 1 degree: georeferenced Z is accepted as vertical and
  the residual is reported alongside every pitch as its uncertainty floor.
- Residual above 1 degree: georeferenced Z is rejected. True vertical is
  recovered from the roof itself: for a symmetric gable, the bisector of the two
  opposing facet normals points straight up, so the cloud is rotated to align
  that bisector with +Z (reusing the existing `level_cloud` rotation math), and
  the gate is re-run on the leveled cloud.

The 1 degree threshold is an angle, so it is scale-independent. Rationale for
the value: adjacent standard roof pitches (for example 7/12 versus 8/12) differ
by roughly 3 degrees, so a residual at or below 1 degree cannot cause a pitch
class misread, while a larger residual could.

The ground plane is never used as the vertical reference on this site: the
terrain slopes, and leveling to a hillside would inject the hillside's slope
into every pitch. This reverses the tyco leveling method for this cloud, and the
reversal is logged in DECISIONS.md.

**7a. Polygon area per facet (build first).** Project each facet's points onto
its own fitted plane, take an alpha shape (a shrink-wrapped outline that can
follow concave boundaries, unlike a convex hull, controlled by one radius-like
parameter), and compute the polygon area. Cheap to build.

7a exists for two reasons. First, it is the integration test for everything
upstream: if isolation, segmentation, or scale is wrong, the per-facet areas
expose it in an afternoon. Second, together with stage 6 it satisfies the
done-definition on its own (total area, per-facet pitch, validated, error
quantified). 7b is built only after 7a is validated. The better version must not
prevent the finished version.

**7b. Edge fitting and dimensions (the full deliverable, built second).**
Lengths are the primary reported quantity; areas are derived from them. For each
facet: extract the boundary of the projected points, fit straight lines to the
boundary segments, intersect them to get corners, and report edge lengths (eave,
ridge, rakes) as a dimension sheet. Holes (chimney footprints, dormer
footprints) are dimensioned the same way as internal openings. Net area = gross
polygon from fitted edges minus dimensioned holes.

Why lengths first: a tape measure validates lengths directly, so the error
report compares like with like. Length errors are also linear where area errors
are quadratic, so a dimension sheet localizes error to a specific edge instead
of hiding it in one aggregate number.

This is expected to be the hardest stage in the pipeline: the boundary of a
point-cloud facet is ragged, occluded by trees, and soft at the eaves. It is
sequenced last so that its difficulty cannot stall the done-definition.

**Cross-check once both exist:** areas derived from 7b dimensions are compared
against 7a polygon areas per facet. Disagreement beyond the known biases (alpha
shape edge rounding, boundary raggedness) flags an error in one of them.

## Thresholds and scale-dependence

Scale-dependent lengths are never hardcoded constants. They are derived from the
cloud's median nearest-neighbor spacing `s` (computed once per cloud), so they
transfer between clouds and every value has a stated formula.

| Threshold | Stage | Scale-dependent? | How chosen |
|---|---|---|---|
| Crop box corners | 1 | Site-specific | Visually, per cloud |
| Height cutoff | 2 | Site-specific | Visually, per cloud (assumption A3) |
| ExG cutoff | 3 | No (unitless color ratio) | Tuned visually once; transfers |
| Planarity neighborhood radius | 4 | Yes | Multiple of `s` |
| Planarity score cutoff | 4 | No (eigenvalue ratio, unitless) | Tuned visually; transfers |
| RANSAC distance band | 5 | Yes | Multiple of `s` |
| Min points per facet | 5 | Density-dependent | Fraction of cloud size, not a constant |
| Pitch band (10 to 60 degrees) | 5 | No (angle) | Standard roof pitch range |
| Z-gate residual limit (1 degree) | 6 | No (angle) | Pitch-class argument above |
| Alpha (shape parameter) | 7a | Yes | Multiple of `s` |

## Explanation gate

Stages 3 through 7 are analysis core. Per the 2026-07-12 authorship decision:
Claude Code writes them, and no stage enters `roofkit/` until Emmett can explain
the approach, justify every threshold, and state whether it is scale-dependent.
Stages 1 and 2 reuse existing reviewed code plus visually chosen constants.

## Out of scope

- Dormer roof surfaces as their own facets. Their footprints are dimensioned as
  holes in 7b; adding their surfaces back is an optional later refinement.
- The wall-removal normal filter from the original plan (decision 2026-07-12:
  the adversary is vegetation, not walls).
- Anything upstream of the `.laz`: reconstruction stays ODM's job.
