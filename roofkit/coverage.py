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
from scipy.ndimage import binary_erosion, label, find_objects
from scipy.spatial import Delaunay

from roofkit.segment import (find_roof_planes, assign_to_planes,
                             fit_plane_trimmed)
from roofkit.measure import tilt_degrees, project_to_plane, facet_area


def plan_grid(points, cell):
    """Bin XY into square cells of side `cell`. Returns the count grid and
    the grid geometry so callers can map cells back to coordinates.
    `cell` is a LENGTH (scale-dependent): callers derive it from spacing."""
    x, y = points[:, 0], points[:, 1]
    xlo, xhi, ylo, yhi = x.min(), x.max(), y.min(), y.max()
    nx = int((xhi - xlo) / cell) + 1
    ny = int((yhi - ylo) / cell) + 1
    H, _, _ = np.histogram2d(x, y, bins=[nx, ny],
                             range=[[xlo, xhi], [ylo, yhi]])
    return H, dict(xlo=xlo, ylo=ylo, cell=cell, nx=nx, ny=ny)


def cell_centers(cells, g):
    """(x, y) centers for an (M, 2) array of (i, j) grid indices."""
    return np.column_stack([g["xlo"] + (cells[:, 0] + 0.5) * g["cell"],
                            g["ylo"] + (cells[:, 1] + 0.5) * g["cell"]])


def coverage_masks(roof, facets, band, cell, min_pts=2):
    """Split the plan grid into building / explained / residual masks.

    building : a cell holding at least min_pts roof points (real surface).
    interior : building eroded by one cell, so the partially-filled
               perimeter fringe cannot masquerade as unexplained (trap 1).
    explained: a cell at least min_pts of whose points lie within `band`
               of some accepted facet plane (its points belong to a facet).
    residual : interior building cells that are NOT explained -> the gaps.

    Returns (masks dict, grid dict, owner, dist). owner/dist come from
    assign_to_planes so the caller can pull a blob's unexplained points."""
    Hall, g = plan_grid(roof, cell)
    owner, dist = assign_to_planes(roof, facets, max_dist=np.inf)
    # count explained points per cell via histogram WEIGHTS (0/1), so we never
    # materialize the ~150 MB explained-points subset copy.
    w = (dist <= band).astype(np.float64)
    Hexp, _, _ = np.histogram2d(roof[:, 0], roof[:, 1],
                                bins=[g["nx"], g["ny"]],
                                range=[[g["xlo"], g["xlo"] + g["nx"] * cell],
                                       [g["ylo"], g["ylo"] + g["ny"] * cell]],
                                weights=w)
    building = Hall >= min_pts
    interior = binary_erosion(building, iterations=1)
    explained = Hexp >= min_pts
    residual = interior & building & ~explained
    masks = dict(building=building, interior=interior,
                 explained=explained, residual=residual)
    return masks, g, owner, dist


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
                   min_pitch=10.0, max_pitch=60.0, size_floor=300,
                   max_planes_per_blob=4, log=None,
                   min_points_hard=None, min_area_hard=None, alpha_mult=4.0,
                   probability=1.0):
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

    Returns a list of new facet dicts {points, normal, pitch, blob, quality}.
    `log`, if given a list, receives one dict per blob describing the pass
    (points tried, planes found, why each was kept or rejected)."""
    new_facets = []
    building_pt_cell = None
    for bi, blob in enumerate(blobs):
        # unexplained points geographically inside this blob's cells
        cx0, cy0 = blob["box"][0]
        cx1, cy1 = blob["box"][1]
        inbox = ((roof[:, 0] >= cx0) & (roof[:, 0] <= cx1) &
                 (roof[:, 1] >= cy0) & (roof[:, 1] <= cy1))
        # cand_idx: where each candidate point sits in `roof`. find_roof_planes
        # returns indices into what IT was given (cand), so composing the two
        # gives indices into roof. Carried for R1; nothing numeric reads it.
        cand_idx = np.flatnonzero(inbox & (dist > band))
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
    xlo = min(float(f["points"][:, 0].min()) for f in facets)
    xhi = max(float(f["points"][:, 0].max()) for f in facets)
    ylo = min(float(f["points"][:, 1].min()) for f in facets)
    yhi = max(float(f["points"][:, 1].max()) for f in facets)
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
