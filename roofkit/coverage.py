# roofkit/coverage.py
# The COMPLETENESS GATE. Replaces the human-supplied expected_facets count
# with a physical invariant: a roof is a closed surface, so in plan view
# (looking straight down) every part of the building footprint must be
# explained by SOME fitted facet. Where it is not, a facet is missing.
#
# Why this exists (decision 2026-07-21): expected_facets was a number a
# human had to know and type, which blocks an automated run and cannot
# catch a facet nobody expected. The invariant needs no prior count. It
# asks "is every building cell explained?" instead of "did we get N?".
#
# THE HARD RULE (do not soften): inside an unexplained region we relax the
# minimum facet SIZE (that is what rejected the big_house dormers), but we
# NEVER relax FIT QUALITY. The plane RMS a small facet must achieve is the
# SAME one the large facets already achieve. Without this, iterating to full
# coverage eventually fits a plane to noise, because a small enough patch of
# anything is planar. Size is negotiable; planarity is not.
#
# KNOWN LIMITS (state them, do not oversell): coverage catches missing
# facets, lost edges, and dormers rejected as too small. It does NOT catch
# one real facet split into two coplanar halves (over-segmentation) nor a
# spurious facet fitted to noise inside an already-covered region; a
# separate adjacent-coplanar-merge check handles the first. Coverage is a
# PLAN-VIEW test, so vertical surfaces (dormer cheeks, gable ends) project
# to near-zero plan area and correctly never register as gaps.
#
# Two rules pull opposite ways on the same cells, by design:
#   coverage  -> SET UNION of explained cells (overlap is harmless).
#   area      -> each plan cell belongs to exactly ONE facet (see the
#                area-ownership logic in the recon, not here).
import numpy as np
from scipy.ndimage import (binary_erosion, binary_fill_holes, label,
                           find_objects)
from scipy.spatial import Delaunay

from roofkit.segment import (find_roof_planes, assign_to_planes,
                             fit_plane_trimmed)
from roofkit.measure import tilt_degrees, project_to_plane, facet_area


def lattice_origin(points, cell):
    """THE DECLARED RASTER ORIGIN (adopted 2026-07-28).

    Every raster in this pipeline anchors here: the global lattice of pitch
    `cell` that passes through the origin of the LEVELED FRAME, snapped down to
    the cell at or below the data.

        xlo = floor(x.min() / cell) * cell

    WHY THIS AND NOT `x.min()`. `x.min()` is a property of the DATA EXTENT: it
    is wherever one extreme point happens to sit. Two runs over the same
    building with slightly different point sets land on different grids, and
    nothing anywhere records that a choice was made. That defect was measured on
    2026-07-28: a sub-cell origin shift swung facet coverage by 5.20 percentage
    points and one facet's connectivity membership by half
    (decisions/2026-07-28-published-coverage-is-a-grid-artifact.md).

    The lattice origin is a pure function of `cell`. Remove a million points and
    the grid does not move; add a facet and it does not move. The floor() only
    guarantees the origin sits at or below the data so nothing falls outside.

    WHAT IT DOES NOT DO, stated so it is not oversold: it does not remove
    discretisation sensitivity. It picks ONE phase and makes it declared,
    reproducible and identical at every site, instead of accidental and
    different every run. The residual sensitivity of the hole-filled and eroded
    footprints (about 1.1 to 1.5 percent) is a property of `min_pts = 2` on a
    sparse cloud and is unchanged by this.

    TRANSFERABILITY, which is the point: bungalow and cove_house raster by the
    same RULE. The lattice itself differs between sites because `cell` is
    2.5 x that site's own median spacing, which is correct; what transfers is
    that the origin is derived from the declared pitch rather than from whichever
    point happens to be furthest south-west."""
    p = np.asarray(points, float)
    return np.array([np.floor(p[:, 0].min() / cell) * cell,
                     np.floor(p[:, 1].min() / cell) * cell])


def plan_grid(points, cell, origin=None, exact_pitch=True, anchor="lattice"):
    """Bin XY into square cells of side `cell`. Returns the count grid and
    the grid geometry so callers can map cells back to coordinates.
    `cell` is a LENGTH (scale-dependent): callers derive it from spacing.

    `origin` is the raster's bottom-left corner. None (the default) is the
    historical behaviour bit for bit: the corner is `x.min(), y.min()` of the
    points handed in, i.e. wherever the extreme point of this particular cloud
    happens to sit.

    WHY THE ARGUMENT EXISTS AND WHAT IT IS NOT. It is not a tuning knob and no
    production caller passes it. A data-derived origin is a NUISANCE PARAMETER:
    it changes where every cell boundary falls, and nobody chose it. Its
    influence cannot be measured from outside, because translating the points
    translates the default origin with them and the binning comes out
    identical; a first attempt to measure exactly this on the connectivity
    filter reported a spread of precisely zero for that reason
    (decisions/2026-07-28-raster-phase-is-an-unswept-parameter.md). An explicit
    origin is the only way to vary the phase while leaving the code under test
    otherwise untouched. Callers passing an origin must place it at or below
    the data on both axes, or points fall outside the raster."""
    x, y = points[:, 0], points[:, 1]
    xhi, yhi = x.max(), y.max()
    if origin is not None:
        xlo, ylo = float(origin[0]), float(origin[1])
    elif anchor == "lattice":
        xlo, ylo = lattice_origin(points, cell)
    elif anchor == "extent":
        # THE PRE-2026-07-28 BEHAVIOUR, kept runnable so superseded numbers can
        # be RECOMPUTED rather than merely quoted. Never use it for a real run.
        xlo, ylo = x.min(), y.min()
    else:
        raise ValueError(f"anchor must be 'lattice' or 'extent', got {anchor!r}")
    nx = int((xhi - xlo) / cell) + 1
    ny = int((yhi - ylo) / cell) + 1
    # `exact_pitch` is a DIAGNOSTIC COUNTERFACTUAL and defaults to the
    # historical behaviour. False asks histogram2d for nx bins spanning
    # [xlo, xhi], so the actual bin width is span/nx, which is always slightly
    # SMALLER than `cell`. True asks for bins spanning [xlo, xlo + nx*cell], so
    # they are exactly `cell` wide.
    #
    # This matters because the sibling histogram in coverage_masks (Hexp, the
    # explained counts) is already anchored the second way. The two grids that
    # coverage_masks compares cell-for-cell therefore have different pitches
    # and drift apart with distance from the origin, and every area is charged
    # as cell^2, which is the pitch of neither. Measured on big_house: the
    # drift reaches 0.487 x 0.731 cells at the far corner.
    #
    # ADOPTED as the default 2026-07-28 after the counterfactual established
    # causation: it removes 97 percent of the phase sensitivity (5.20 points
    # down to 0.18) and is the only setting under which the three parts of the
    # calculation agree with each other, since Hexp and the cell^2 area charge
    # ALREADY assume bins of width `cell`. `exact_pitch=False` is kept runnable
    # so superseded numbers can be recomputed rather than merely quoted.
    # decisions/2026-07-28-published-coverage-is-a-grid-artifact.md
    rng = ([[xlo, xlo + nx * cell], [ylo, ylo + ny * cell]] if exact_pitch
           else [[xlo, xhi], [ylo, yhi]])
    H, _, _ = np.histogram2d(x, y, bins=[nx, ny], range=rng)
    return H, dict(xlo=xlo, ylo=ylo, cell=cell, nx=nx, ny=ny)


def cell_centers(cells, g):
    """(x, y) centers for an (M, 2) array of (i, j) grid indices."""
    return np.column_stack([g["xlo"] + (cells[:, 0] + 0.5) * g["cell"],
                            g["ylo"] + (cells[:, 1] + 0.5) * g["cell"]])


def coverage_masks(roof, facets, band, cell, min_pts=2, fill_holes=True,
                   origin=None, exact_pitch=True, anchor="lattice",
                   allow_superseded=False):
    """Split the plan grid into footprint / explained / residual masks.

    testable : a cell holding at least min_pts roof points. Only these can be
               tested at all: a cell with one point cannot show whether a
               facet explains it.
    footprint: `testable` with ENCLOSED HOLES FILLED. A cell completely
               surrounded by roof is inside the building whatever its point
               count, because a roof is a closed surface. See below.
    interior : footprint eroded by one cell, so the partially-filled
               perimeter fringe cannot masquerade as unexplained (trap 1).
    explained: a cell at least min_pts of whose points lie within `band`
               of some accepted facet plane (its points belong to a facet).
    residual : interior TESTABLE cells that are NOT explained -> the gaps.

    `building` is kept as an alias of `testable` so older callers still work.

    WHY HOLES ARE FILLED BEFORE ERODING (decision 2026-07-26). The mask is not
    a clean outline. On big_house it contains 111,154 enclosed holes totalling
    370,079 cells, most of them a single cell, because a cell needs 2 points to
    count and 249,745 cells inside the roof hold exactly 1. Eroding that mask
    widens every hole from the inside: 90 to 95 percent of what each erosion
    ring removed was hole boundary, not building outline, and the one-cell
    erosion alone discarded 32.5 percent of the roof. Coverage was therefore
    being reported as a percentage of something that was not the footprint.

    Filling is not a patch, it is the project's own invariant applied to the
    mask instead of to the facets: a roof is a CLOSED SURFACE, so a cell
    entirely enclosed by roof is roof. It introduces no parameter and no
    threshold. It cannot bridge a real courtyard or light well either, because
    binary_fill_holes only fills regions with no path to the outside, and any
    genuine opening is reported in the filled-hole size table so a real one
    surfaces instead of being silently absorbed.

    Returns (masks dict, grid dict, owner, dist). owner/dist come from
    assign_to_planes so the caller can pull a blob's unexplained points."""
    Hall, g = plan_grid(roof, cell, origin=origin, exact_pitch=exact_pitch,
                        anchor=anchor)
    owner, dist = assign_to_planes(roof, facets, max_dist=np.inf)
    # count explained points per cell via histogram WEIGHTS (0/1), so we never
    # materialize the ~150 MB explained-points subset copy.
    w = (dist <= band).astype(np.float64)
    Hexp, _, _ = np.histogram2d(roof[:, 0], roof[:, 1],
                                bins=[g["nx"], g["ny"]],
                                range=[[g["xlo"], g["xlo"] + g["nx"] * cell],
                                       [g["ylo"], g["ylo"] + g["ny"] * cell]],
                                weights=w)
    # --- THE SHARED-LATTICE ASSERTION (adopted 2026-07-30) -----------------
    # Hall and Hexp are compared CELL FOR CELL below, and every area is charged
    # as cell^2. That is only meaningful if the two rasters are the same raster.
    # Before 2026-07-28 they were not: plan_grid asked for nx bins spanning
    # [xlo, xhi], so its bins were 99.978 percent of `cell`, while Hexp's were
    # exactly `cell`. The two drifted apart by 0.487 x 0.731 CELLS at the far
    # corner and the published coverage was substantially an artifact of it.
    #
    # The fix is now the default, so this asserts the fix is actually in force
    # rather than trusting the defaults, which is the whole point of standing
    # rule R4.
    # `allow_superseded` is the ONLY way past the first two checks, and it
    # exists because "supersede, never overwrite" is only a real property if a
    # superseded number can still be RECOMPUTED rather than merely quoted.
    # Four probes legitimately run the old configuration for exactly that, one
    # of them an anti-null that must show the OLD path still reproduces 82.29.
    # Making the guard opt-out rather than absolute keeps those runnable while
    # still making it impossible for a PRODUCTION path to reach the defective
    # grid silently, which is the failure that actually happened.
    if not allow_superseded:
        if not exact_pitch:
            raise AssertionError(
                "coverage_masks: exact_pitch=False. Hall's bins are span/nx "
                "wide and Hexp's are exactly `cell` wide, so the two rasters "
                "this function compares cell-for-cell have different pitches. "
                "This is the 2026-07-28 grid defect. A probe recomputing a "
                "superseded number must say so with allow_superseded=True.")
        if origin is None and anchor != "lattice":
            raise AssertionError(
                f"coverage_masks: anchor={anchor!r}, so the origin is an "
                f"arbitrary sub-cell offset of the data rather than a declared "
                f"lattice point. Adopted 2026-07-28: every raster anchors to "
                f"floor(min/cell)*cell.")
        if origin is None and anchor == "lattice":
            want = lattice_origin(roof, cell)
            if (g["xlo"], g["ylo"]) != (want[0], want[1]):
                raise AssertionError(
                    f"coverage_masks: grid origin ({g['xlo']!r}, "
                    f"{g['ylo']!r}) is not the declared lattice origin "
                    f"({want[0]!r}, {want[1]!r}) derived from the same global "
                    f"min by floor(min/cell)*cell.")
        # THE INDEPENDENT CHECK (R4): the assertions above are read off the
        # ARGUMENTS, so they would all pass if the rasters were misaligned for
        # a reason nobody anticipated. This one is not: it is a property of the
        # DATA that must hold for any pair of aligned rasters and must break
        # for a misaligned pair. Every explained point is also an `all` point,
        # so cell by cell Hexp can never exceed Hall. If the two grids drifted
        # apart, some cell is credited with explained points Hall never counted
        # there. Both are sums of 0/1 doubles, so this is integer-exact.
        #
        # It sits inside the `not allow_superseded` branch, and that placement
        # is the point rather than a convenience. MEASURED 2026-07-30 on
        # big_house: under the superseded configuration it fires on 707,650
        # cells, which is this defect's first direct count rather than an
        # inference from coverage moving. A probe recomputing a superseded
        # number is deliberately reproducing the misalignment, so the invariant
        # SHOULD be violated there, and enforcing it would make the old number
        # unrecomputable, which is the property "supersede, never overwrite"
        # depends on.
        if not (Hexp <= Hall).all():
            bad = int((Hexp > Hall).sum())
            raise AssertionError(
                f"coverage_masks: Hexp exceeds Hall in {bad:,} cells. "
                f"Explained points are a subset of all points, so this is "
                f"impossible on a single shared raster. The grids are not "
                f"aligned.")

    testable = Hall >= min_pts
    # fill_holes=False reproduces the PRE-2026-07-26 base, in which the mask was
    # eroded with its holes still in it. It exists so the coverage change can be
    # attributed step by step to its three causes, and so a superseded number
    # can be recomputed rather than merely quoted. Never use it for a real run:
    # it is the defect, kept runnable on purpose.
    footprint = binary_fill_holes(testable) if fill_holes else testable
    interior = binary_erosion(footprint, iterations=1)
    explained = Hexp >= min_pts
    # Residual counts only cells that CAN be tested. A filled hole holds fewer
    # than 2 points, so no facet could ever explain it; charging it as
    # unexplained would blame the segmentation for a capture shortfall. It is
    # counted instead by the density-testable fraction, which is what that
    # shortfall actually is.
    residual = interior & testable & ~explained
    masks = dict(testable=testable, footprint=footprint,
                 building=testable,          # alias, kept for older callers
                 filled=footprint & ~testable,
                 interior=interior, explained=explained, residual=residual)
    return masks, g, owner, dist


def footprint_three_ways(masks, cell):
    """The three footprint numbers that make the erosion defect visible to any
    reader, without them having to know it exists (decision 2026-07-26).

    raw      : cells holding at least 2 points.
    filled   : the same mask with enclosed holes filled.
    eroded   : filled, then eroded by one cell. THIS is the base coverage is
               reported against, and before hole filling it was a third
               smaller than the roof.

    Reporting one number invites the reader to assume it is the footprint.
    Reporting all three shows what each step costs."""
    a = cell * cell
    raw = int(masks["testable"].sum())
    fil = int(masks["footprint"].sum())
    ero = int((masks["interior"] & masks["footprint"]).sum())
    return dict(
        raw_cells_at_2_points=raw, raw_cu2=round(raw * a, 3),
        holes_filled_cells=fil - raw, holes_filled_cu2=round((fil - raw) * a, 3),
        filled_cells=fil, filled_cu2=round(fil * a, 3),
        eroded_cells=ero, eroded_cu2=round(ero * a, 3),
        erosion_cost_cells=fil - ero, erosion_cost_cu2=round((fil - ero) * a, 3),
        erosion_cost_pct_of_filled=round(100.0 * (fil - ero) / max(fil, 1), 2))


def filled_hole_report(masks, cell, top_n=10):
    """Size distribution of the enclosed holes that were filled, plus the
    largest few.

    Filling is safe on a roof, but it must not be silent. A genuine courtyard,
    light well or atrium on a future building would also be an enclosed hole,
    and filling it would quietly add area that is not roof. So every filled
    region is measured and the largest are named: a single hole of a few square
    metres is a feature, ten thousand single-cell holes are sparse capture."""
    lab, n = label(masks["filled"])
    a = cell * cell
    if n == 0:
        return dict(n_holes=0, total_cells=0, total_cu2=0.0, size_histogram=[],
                    largest=[], reading="no enclosed holes")
    sizes = np.bincount(lab.ravel())[1:]
    buckets = [(1, 1), (2, 2), (3, 4), (5, 9), (10, 24), (25, 99),
               (100, 999), (1000, 10 ** 9)]
    hist = []
    for lo, hi in buckets:
        m = (sizes >= lo) & (sizes <= hi)
        if m.any():
            hist.append(dict(size_cells=(f"{lo}" if lo == hi else f"{lo}-{hi}"),
                             n_holes=int(m.sum()),
                             total_cells=int(sizes[m].sum()),
                             total_cu2=round(float(sizes[m].sum()) * a, 4)))
    order = np.argsort(sizes)[::-1][:top_n]
    largest = [dict(rank=r + 1, cells=int(sizes[k]),
                    cu2=round(float(sizes[k]) * a, 4))
               for r, k in enumerate(order)]
    biggest = float(sizes.max()) * a
    return dict(
        n_holes=int(n), total_cells=int(sizes.sum()),
        total_cu2=round(float(sizes.sum()) * a, 4),
        median_size_cells=int(np.median(sizes)),
        size_histogram=hist, largest=largest,
        reading=(f"largest single filled region is {biggest:.4f} cu^2. If that "
                 f"is a meaningful fraction of the roof, check it against the "
                 f"imagery before trusting the filled footprint: a real "
                 f"courtyard or light well would look exactly like this."))


def split_coverage(masks, cell):
    """Coverage split into the two questions it was conflating (decision
    2026-07-26).

    One percentage was answering two things at once, so a change in it could
    not be attributed. They are separated:

      density_testable_fraction = testable cells / footprint cells, inside the
        eroded interior. How much of the roof has enough points to test AT ALL.
        This is a CAPTURE-QUALITY metric: it measures the flight, the overlap
        and the reconstruction, and the segmentation cannot move it.

      facet_coverage = explained / testable, inside the eroded interior. Of the
        region that can be tested, how much a facet explains. This is the
        SEGMENTATION metric, and it is the one the coverage gate was built to
        produce.

    Keeping them apart matters because they move for opposite reasons. A sparse
    capture drags the combined number down and looks like a segmentation
    failure; that is exactly what was happening."""
    a = cell * cell
    interior = masks["interior"]
    testable = interior & masks["testable"]
    foot = interior & masks["footprint"]
    expl = testable & masks["explained"]
    n_t, n_f, n_e = int(testable.sum()), int(foot.sum()), int(expl.sum())
    return dict(
        density_testable_fraction=dict(
            question="how much of the footprint has enough points to test at all",
            kind="CAPTURE quality: the flight and the reconstruction, not the "
                 "segmentation",
            testable_cells=n_t, testable_cu2=round(n_t * a, 3),
            footprint_cells=n_f, footprint_cu2=round(n_f * a, 3),
            untestable_cu2=round((n_f - n_t) * a, 3),
            pct=round(100.0 * n_t / max(n_f, 1), 2)),
        facet_coverage=dict(
            question="of the testable region, how much does a facet explain",
            kind="SEGMENTATION: this is what the coverage gate was built to "
                 "measure",
            explained_cells=n_e, explained_cu2=round(n_e * a, 3),
            testable_cells=n_t, testable_cu2=round(n_t * a, 3),
            unexplained_cu2=round((n_t - n_e) * a, 3),
            pct=round(100.0 * n_e / max(n_t, 1), 2)),
        note="these two do not multiply to the old single number, and are not "
             "meant to. The old number mixed a capture shortfall into a "
             "segmentation score against a base that hole-erosion had already "
             "shrunk by a third.")


def residual_blobs(residual_mask, g, min_area):
    """Connected-component the residual cells into candidate missing facets.
    Drops blobs below min_area (a plan area in cu^2). Returns a list of
    dicts: cells (i,j array), area_cu2, box ((x0,y0),(x1,y1)).

    O(N): one labeling, sizes from bincount, and per-blob work confined to
    each component's bounding box via find_objects. The earlier version did
    np.argwhere(lab == i) PER COMPONENT, each a full-grid scan; with tens of
    thousands of residual specks that was O(components x grid) and hung the
    threshold sweep for many minutes (it looked like paging; it was CPU in
    those scans)."""
    lab, n = label(residual_mask)
    cell = g["cell"]
    cell_area = cell * cell
    if n == 0:
        return []
    sizes = np.bincount(lab.ravel())          # sizes[0] = background
    slices = find_objects(lab)                # bbox slice per label 1..n
    blobs = []
    for i in range(1, n + 1):
        if sizes[i] * cell_area < min_area:    # cheap reject, no scan
            continue
        sl = slices[i - 1]
        sub = lab[sl] == i                     # scan only this blob's bbox
        cells = np.argwhere(sub)
        cells[:, 0] += sl[0].start
        cells[:, 1] += sl[1].start
        x0 = g["xlo"] + cells[:, 0].min() * cell
        x1 = g["xlo"] + (cells[:, 0].max() + 1) * cell
        y0 = g["ylo"] + cells[:, 1].min() * cell
        y1 = g["ylo"] + (cells[:, 1].max() + 1) * cell
        blobs.append(dict(cells=cells, area_cu2=sizes[i] * cell_area,
                          box=((x0, y0), (x1, y1))))
    blobs.sort(key=lambda b: -b["area_cu2"])
    return blobs


def blob_areas(residual_mask, cell):
    """Plan areas (cu^2) of EVERY connected residual component, unsorted.
    For the threshold sweep: one labeling + bincount, then the sweep counts
    components above each threshold by pure array comparison, instead of
    re-detecting blobs a dozen times."""
    lab, n = label(residual_mask)
    if n == 0:
        return np.array([])
    return np.bincount(lab.ravel())[1:] * (cell * cell)


def facet_quality(points, normal, spacing):
    """Fit-quality of a facet: trimmed-plane RMS expressed in units of point
    spacing (unitless, so it transfers across clouds). This is the number
    the hard rule holds constant between large and small facets."""
    normal, keep = fit_plane_trimmed(points, trim_mult=3.0)
    d = (points[keep] - points[keep].mean(axis=0)) @ (normal / np.linalg.norm(normal))
    rms = float(np.sqrt(np.mean(d ** 2)))
    return rms / spacing, normal


def calibrate_quality_bar(facets, spacing):
    """The fit-quality bar a recovered facet must clear = the WORST (largest)
    trimmed RMS/spacing among the already-accepted large facets. A dormer
    facet is required to be at least as planar as the roughest main facet;
    it is never held to an easier standard (that would be relaxing quality)."""
    ratios = [facet_quality(f["points"], f["normal"], spacing)[0] for f in facets]
    return float(max(ratios)), ratios


def recover_facets(roof, blobs, owner, dist, band, spacing, quality_bar,
                   min_pitch=5.0, max_pitch=60.0, size_floor=300,
                   max_planes_per_blob=4, log=None,
                   min_points_hard=None, min_area_hard=None, alpha_mult=4.0,
                   probability=1.0, selection="cells", *, grid):
    """Recover the missing facets inside residual blobs.

    For each blob we take its UNEXPLAINED points (dist > band: the surfaces
    no main facet owns, i.e. the dormer roof faces) and peel roof-pitched
    planes with a RELAXED size floor. Each candidate must clear the SAME
    fit-quality bar as the main facets; size is the only thing relaxed.

    size_floor is a STABILITY floor (a plane fit needs enough points to be
    meaningful), NOT a size threshold: it is a small absolute constant, not
    a fraction of the roof, so it does not encode "big enough to matter."

    THE HARD FLOOR (added 2026-07-25, in response to measured nondeterminism).
    min_points_hard and min_area_hard reject a candidate plane outright,
    inside residual blobs as everywhere else. This is NOT a softening of the
    quality rule and NOT a quality threshold: both floors are about SIZE, and
    a plane that clears them is still held to the same fit-quality bar.

    Why a size floor is the right response to nondeterminism rather than a
    workaround: Open3D's RANSAC was measured returning different planes for an
    identical seed on identical points. The effect is invisible when the fit is
    over-determined (a facet with 1.5M points reproduced to 0.0004 deg) and
    decisive when it is not (a 664-point facet gave three different answers,
    and one facet vanished between runs entirely). A plane fitted to too few
    points is therefore not merely small, it is NOT REPRODUCIBLE, and an
    irreproducible facet cannot be part of a result anyone freezes. The floor
    removes facets the instrument cannot measure twice.

    min_area_hard is checked against the candidate's ALPHA GROSS area, which is
    what can be computed at recovery time. Gross is always >= net (occlusion
    only subtracts), so this gate is PERMISSIVE: anything it rejects would also
    fail the same floor on net. A final net-area check belongs after area
    accounting, where net actually exists.

    CANDIDATE SELECTION IS BY CELL, NOT BY BOUNDING BOX (decision 2026-07-26).
    `grid` is the plan grid from coverage_masks and is REQUIRED, because
    selecting by box was a real defect, not a theoretical one: two recovered
    facets on big_house ended up owning 9,739 of the same points. Connected
    components guarantee that two blobs share no CELL, but they say nothing
    about their bounding BOXES, which can overlap or even nest; blob 7's and
    blob 10's overlapped by 73 percent of the smaller. A point inside both boxes
    was offered to both blobs and fitted twice.

    Selecting by the blob's own cells makes that impossible BY CONSTRUCTION
    rather than unlikely: blobs share no cell, and every point falls in exactly
    one cell, so no point can be offered to two blobs. That is a structural
    guarantee, which is worth more than a fix that removes the observed case.
    `assert_single_ownership` then checks the guarantee on every run.

    Returns a list of new facet dicts {points, normal, pitch, blob, quality}.
    `log`, if given a list, receives one dict per blob describing the pass
    (points tried, planes found, why each was kept or rejected)."""
    # Every roof point's plan cell, computed once. Cell membership is what makes
    # the blobs disjoint, so it is what selection must use.
    g = grid
    ny1 = np.int64(g["ny"] + 1)
    pi = np.clip(((roof[:, 0] - g["xlo"]) / g["cell"]).astype(np.int64),
                 0, g["nx"] - 1)
    pj = np.clip(((roof[:, 1] - g["ylo"]) / g["cell"]).astype(np.int64),
                 0, g["ny"] - 1)
    point_cell = pi * ny1 + pj
    unexplained = dist > band

    if selection not in ("cells", "box"):
        raise ValueError(f"selection must be 'cells' or 'box', got {selection!r}")

    new_facets = []
    for bi, blob in enumerate(blobs):
        # cand_idx: where each candidate point sits in `roof`. find_roof_planes
        # returns indices into what IT was given (cand), so composing the two
        # gives indices into roof. Carried for R1; nothing numeric reads it.
        if selection == "cells":
            # The blob's OWN cells, as the same single-integer ids. Two blobs
            # never share a cell, and a point sits in exactly one cell, so no
            # point can be offered to two blobs.
            blob_cells = (blob["cells"][:, 0].astype(np.int64) * ny1 +
                          blob["cells"][:, 1].astype(np.int64))
            cand_idx = np.flatnonzero(unexplained &
                                      np.isin(point_cell, blob_cells))
        else:
            # THE DEFECT, kept runnable so superseded states can be reproduced
            # and the coverage change attributed. Blob bounding boxes overlap
            # even though blob cells do not, so this hands the same points to
            # two blobs and fits them twice. Never use it for a real run.
            (cx0, cy0), (cx1, cy1) = blob["box"]
            inbox = ((roof[:, 0] >= cx0) & (roof[:, 0] <= cx1) &
                     (roof[:, 1] >= cy0) & (roof[:, 1] <= cy1))
            cand_idx = np.flatnonzero(inbox & unexplained)
        cand = roof[cand_idx]
        entry = dict(blob=bi, area_cu2=blob["area_cu2"], n_candidate=len(cand),
                     planes=[])
        if len(cand) < size_floor:
            entry["skipped"] = f"only {len(cand)} unexplained pts < stability floor {size_floor}"
            if log is not None:
                log.append(entry)
            continue
        # The hard point floor is pushed INTO the peeling loop as its
        # min_points, so RANSAC never even proposes a sub-floor plane and the
        # loop terminates as soon as too little is left. Enforcing it here
        # rather than filtering afterwards matters: a rejected-after-the-fact
        # plane has already had its points removed from the cloud, which
        # changes what the NEXT peel sees.
        floor = max(size_floor, min_points_hard or 0)
        # peel_log records EVERY plane RANSAC peeled inside this blob, including
        # the ones the pitch window discards. Without it, a blob that yields no
        # facet is indistinguishable from a blob where RANSAC found nothing at
        # all, and those are different diagnoses (Task 6C, 2026-07-26).
        peels = []
        planes = find_roof_planes(cand, distance_threshold=band,
                                  min_points=floor,
                                  min_pitch=min_pitch, max_pitch=max_pitch,
                                  max_planes=max_planes_per_blob,
                                  probability=probability, peel_log=peels)
        entry["peels"] = peels
        for p in planes:
            q, normal = facet_quality(p["points"], p["normal"], spacing)
            pitch = tilt_degrees(normal)
            rec = dict(n=len(p["points"]), pitch=round(pitch, 2),
                       quality=round(q, 3), bar=round(quality_bar, 3),
                       # Full-precision normal, as exact hex float strings.
                       # The rounded fields above are for humans reading the
                       # log; these are for bit-for-bit comparison between
                       # runs (added 2026-07-26 for the T1 threading test).
                       # Recorded for EVERY candidate, kept or rejected, so a
                       # run-to-run diff sees the whole candidate set and not
                       # just the accepted subset.
                       normal_hex=[float(x).hex() for x in np.asarray(normal, float)])

            # SIZE gates first (cheap, and they are the reproducibility gates),
            # then the QUALITY bar, which is never relaxed.
            ok = True
            if min_points_hard is not None and len(p["points"]) < min_points_hard:
                ok = False
                rec["rejected_by"] = f"point floor {len(p['points'])} < {min_points_hard}"
            if ok and min_area_hard is not None:
                s_f = float(np.median(_nn(p["points"])))
                gross = facet_area(p["points"], normal, alpha_mult * s_f)
                rec["gross_cu2"] = round(float(gross), 4)
                if gross < min_area_hard:
                    ok = False
                    rec["rejected_by"] = f"area floor {gross:.4f} < {min_area_hard}"
            if ok and q > quality_bar:
                ok = False
                rec["rejected_by"] = f"quality {q:.3f} > bar {quality_bar:.3f}"

            rec["kept"] = bool(ok)
            entry["planes"].append(rec)
            if ok:
                new_facets.append(dict(points=p["points"], normal=normal,
                                       pitch=pitch, blob=bi, quality=q,
                                       idx=cand_idx[p["idx"]]))
        if log is not None:
            log.append(entry)
    return new_facets


# --------------------------------------------------------------------------
# Area accounting. Coverage uses a SET UNION of cells (overlap harmless);
# area needs the opposite: each plan cell belongs to exactly ONE facet.
# Ownership rule: HIGHEST SURFACE WINS. A dormer roof is physically above
# the main slope and the main slope does not exist beneath it.
#
# Adjusted rule (decision 2026-07-21, from the double-count gate): the
# parent's alpha shape ALREADY leaves the dormer hole open (verified: ~91%
# of dormer plan area is not inside any main facet's counted surface). So we
# do NOT subtract the full child footprint from the parent (that would
# over-correct). We subtract only the plan cells the parent's alpha surface
# ACTUALLY counted AND a higher facet also covers. gross = alpha area;
# occluded = that counted overlap converted to slope at the parent's pitch;
# net = gross - occluded.
# --------------------------------------------------------------------------
def _plane_basis(normal, centroid):
    """The same in-plane (u, v) basis roofkit.measure.project_to_plane uses,
    so a query point projects into the identical frame as the facet points."""
    n = np.asarray(normal, float); n = n / np.linalg.norm(n)
    helper = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(n, helper); u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    return n, u, v, np.asarray(centroid, float)


def facet_kept_alpha(points, normal, alpha):
    """Replicate facet_area's KEPT alpha triangles: the exact surface whose
    area is summed. Returns (Delaunay in u,v, kept-triangle mask, basis)."""
    centroid = points.mean(axis=0)
    n, u, v, c = _plane_basis(normal, centroid)
    uv = np.column_stack([(points - c) @ u, (points - c) @ v])
    tri = Delaunay(uv)
    s = tri.simplices
    a, b, cc = uv[s[:, 0]], uv[s[:, 1]], uv[s[:, 2]]
    ab, ac, bc = b - a, cc - a, cc - b
    area = np.abs(ab[:, 0] * ac[:, 1] - ab[:, 1] * ac[:, 0]) / 2.0
    la, lb, lc = (np.linalg.norm(bc, axis=1), np.linalg.norm(ac, axis=1),
                  np.linalg.norm(ab, axis=1))
    with np.errstate(divide="ignore", invalid="ignore"):
        R = np.where(area > 1e-15, la * lb * lc / (4.0 * area), np.inf)
    return tri, (R <= alpha), (n, u, v, c)


def _covered_and_z(qxy, tri, kept, basis):
    """(covered, z): does each query XY land on a KEPT alpha triangle of this
    facet, and what is the facet-plane height there (for the highest-wins
    test)? z is NaN where the facet does not cover the point."""
    n, u, v, c = basis
    x, y = qxy[:, 0], qxy[:, 1]
    z = c[2] - (n[0] * (x - c[0]) + n[1] * (y - c[1])) / n[2]
    P = np.column_stack([x, y, z]) - c
    uv = np.column_stack([P @ u, P @ v])
    simp = tri.find_simplex(uv)
    covered = np.zeros(len(qxy), bool)
    inside = simp >= 0
    covered[inside] = kept[simp[inside]]
    zc = np.where(covered, z, np.nan)
    return covered, zc


def area_accounting(facets, spacing, alpha_mult, cell, area_max_points=400_000,
                    seed=0):
    """Per-facet gross / occluded / net slope area under highest-surface-wins.

    Rasterizes every facet's kept alpha surface onto a shared plan grid,
    resolves each contested cell to the highest facet, and charges the
    losers an occlusion (their gross alpha area minus the slope-equivalent
    of the cells they lost). Returns (rows, totals):
      rows[k] = dict(gross, occluded, net, pitch)
      totals  = dict(gross, occluded, net, decomposition string)."""
    import gc
    rng = np.random.default_rng(seed)
    # Grid bounds WITHOUT stacking all facet points (that vstack was a ~9M-pt,
    # 200 MB temporary). Only OCCUPIED cells (holding at least one facet point)
    # can be covered, so we accumulate the occupancy grid facet by facet.
    xhi = max(float(f["points"][:, 0].max()) for f in facets)
    yhi = max(float(f["points"][:, 1].max()) for f in facets)
    # THE DECLARED LATTICE ORIGIN (adopted 2026-07-28), same rule coverage_masks
    # uses. This raster previously took min() over the FACET points, a second
    # data-derived origin unrelated to the coverage grid's. Both are now
    # multiples of `cell`, so the two rasters sit on ONE global lattice and are
    # mutually aligned, which they were not before. See lattice_origin().
    #
    # This grid's BINS were already exactly `cell` wide (see rng2 below), so the
    # plan_grid pitch defect never reached area accounting. Only the origin
    # changes here.
    xlo = float(np.floor(min(float(f["points"][:, 0].min())
                             for f in facets) / cell) * cell)
    ylo = float(np.floor(min(float(f["points"][:, 1].min())
                             for f in facets) / cell) * cell)
    nx = int((xhi - xlo) / cell) + 1
    ny = int((yhi - ylo) / cell) + 1
    rng2 = [[xlo, xlo + nx * cell], [ylo, ylo + ny * cell]]
    Hall = np.zeros((nx, ny))
    for f in facets:
        h, _, _ = np.histogram2d(f["points"][:, 0], f["points"][:, 1],
                                 bins=[nx, ny], range=rng2)
        Hall += h
    occ = np.argwhere(Hall >= 1)
    centers = np.column_stack([xlo + (occ[:, 0] + 0.5) * cell,
                               ylo + (occ[:, 1] + 0.5) * cell])
    del Hall, occ
    gc.collect()

    ncells = len(centers)
    # STREAM the highest-surface-wins resolution: keep only a running best-z
    # and owner (two ncells arrays), plus one CHEAP bool coverage mask per
    # facet (needed later to charge occlusion). Never build the F x ncells
    # float stack (that ~300 MB array plus its np.where copy was what paged).
    best_z = np.full(ncells, -np.inf)
    owner = np.full(ncells, -1)
    cov_masks, gross, pitch = [], [], []
    for k, f in enumerate(facets):
        pts = f["points"]
        if len(pts) > area_max_points:
            pts = pts[rng.choice(len(pts), area_max_points, replace=False)]
        s_f = np.median(_nn(pts))  # facet's own spacing, like the instrument
        alpha = alpha_mult * s_f
        gross.append(facet_area(pts, f["normal"], alpha))
        tri, kept, basis = facet_kept_alpha(pts, f["normal"], alpha)
        covered, z = _covered_and_z(centers, tri, kept, basis)
        upd = covered & (z > best_z)   # NaN where uncovered -> comparison False
        best_z[upd] = z[upd]
        owner[upd] = k
        cov_masks.append(covered)      # bool, ~ncells/8 bytes: cheap to keep
        pitch.append(tilt_degrees(f["normal"]))
        del tri, kept, z, upd, pts
        gc.collect()

    rows, cell_area = [], cell * cell
    tot_gross = tot_occ = tot_net = 0.0
    for k in range(len(facets)):
        lost = cov_masks[k] & (owner != k)      # cells this facet covers but loses
        occ_plan = int(lost.sum()) * cell_area
        occ_slope = occ_plan / max(np.cos(np.radians(pitch[k])), 1e-6)
        net = gross[k] - occ_slope
        rows.append(dict(gross=gross[k], occluded=occ_slope, net=net,
                         pitch=pitch[k]))
        tot_gross += gross[k]; tot_occ += occ_slope; tot_net += net
    totals = dict(gross=tot_gross, occluded=tot_occ, net=tot_net)
    return rows, totals


def _nn(pts, sample=20000, seed=0):
    from scipy.spatial import cKDTree
    p = np.asarray(pts)
    if len(p) > sample:
        rng = np.random.default_rng(seed)
        p2 = p[rng.choice(len(p), sample, replace=False)]
    else:
        p2 = p
    d, _ = cKDTree(p).query(p2, k=2)
    return d[:, 1]


def pairwise_matrix(facets):
    """Raw pairwise geometry for over-segmentation diagnosis. For every pair:
    normal angle difference (deg) and plane offset separation (perpendicular
    distance between the two planes, evaluated at the midpoint of their
    centroids). NO merge, NO tolerance applied: the matrix is reported so a
    human reads whether two facets are the same plane split in two."""
    F = len(facets)
    ang = np.zeros((F, F)); off = np.zeros((F, F))
    ns = [np.asarray(f["normal"], float) / np.linalg.norm(f["normal"]) for f in facets]
    cs = [f["points"].mean(axis=0) for f in facets]
    for i in range(F):
        for j in range(F):
            if i == j:
                continue
            ang[i, j] = np.degrees(np.arccos(np.clip(abs(ns[i] @ ns[j]), -1, 1)))
            mid = (cs[i] + cs[j]) / 2.0
            # perpendicular distance from mid to each plane, averaged
            di = abs((mid - cs[i]) @ ns[i]); dj = abs((mid - cs[j]) @ ns[j])
            off[i, j] = (di + dj) / 2.0
    return ang, off


def coverage_fraction(masks):
    """Explained fraction of the interior building footprint (set-union
    view): 1 - residual_cells / interior_building_cells. Reported as the
    completeness number; near 1.0 with residual concentrated at the
    perimeter ring is the pass condition."""
    interior_building = masks["interior"] & masks["building"]
    if interior_building.sum() == 0:
        return 1.0
    return 1.0 - masks["residual"].sum() / interior_building.sum()
