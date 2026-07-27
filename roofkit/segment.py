import numpy as np
import open3d as o3d
from roofkit.measure import tilt_degrees
from scipy.spatial.transform import Rotation

def clean_outliers(points, nb_neighbors=20, std_ratio=2.0):
    """Remove sparse floating points (noise) that sit far from their neighbors.
    Returns the cleaned points as a NumPy array."""
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    cleaned, kept_indices = cloud.remove_statistical_outlier(
        nb_neighbors=nb_neighbors, std_ratio=std_ratio)
    return np.asarray(cleaned.points)

def fit_ground_plane(points, distance_threshold=0.2):
    """Find the ground: the single largest flat surface in the cloud.

    Uses one RANSAC pass to grab the biggest plane, which after cropping is the
    lawn. Returns:
      normal        : (3,) unit vector pointing UP out of the ground (true vertical)
      ground_points : the points that lie on the ground plane
      inlier_mask   : (N,) True/False, which input points are ground
    """
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)

    # RANSAC for the single biggest flat plane. Same call find_roof_planes uses,
    # but we run it ONCE and take whatever the largest plane is, no pitch filter,
    # because here we WANT the flat ground, not a roof.
    plane_model, inliers = cloud.segment_plane(
        distance_threshold=distance_threshold, ransac_n=3, num_iterations=1000)

    normal = np.asarray(plane_model[:3], dtype=float)   # (a, b, c)
    normal = normal / np.linalg.norm(normal)            # make it length 1 (a unit vector)

    # Sign fix: RANSAC may return the normal pointing down into the ground instead
    # of up. We want "up". In the cloud's own frame, the roof/house sits on the
    # HIGH side of the ground. We can't trust Z (it's tilted), so we orient the
    # normal to point toward the cloud's average point, which sits above the
    # ground (house + points are mostly above the lawn, not below it).
    cloud_center = points.mean(axis=0)
    ground_center = points[inliers].mean(axis=0)
    up_ish = cloud_center - ground_center      # rough "toward the bulk of the cloud"
    if normal @ up_ish < 0:                     # dot product negative = normal points away from the bulk
        normal = -normal                        # flip it to point up

    # Build a True/False mask of which points are ground (for later use).
    inlier_mask = np.zeros(len(points), dtype=bool)
    inlier_mask[inliers] = True

    ground_points = points[inlier_mask]
    return normal, ground_points, inlier_mask

def find_roof_planes(points, distance_threshold=0.2, min_points=300,
                     min_pitch=10, max_pitch=60, max_planes=8,
                     probability=1.0, peel_log=None):
    """Peel flat planes off the cloud one at a time with RANSAC, keeping only
    the ones tilted like a roof. Returns a list of facets, each a dict holding
    that facet's points, its normal, and its pitch in degrees.

    `probability` is Open3D's ADAPTIVE EARLY STOP: RANSAC keeps a running
    estimate of how many iterations it still needs to have reached this
    probability of having found the best plane, and quits as soon as the
    estimate is met, usually long before num_iterations. That estimate depends
    on the best inlier count found SO FAR. Open3D evaluates candidates in
    PARALLEL, so "best so far" depends on the order threads happen to finish,
    which the seed does not control. That is why a fixed seed did NOT give a
    fixed answer (measured 2026-07-25: a 664-point facet returned three
    different planes under an identical seed).

    probability=1.0 disables the early stop and forces all num_iterations, so
    every candidate is always evaluated and the result no longer depends on
    thread timing.

    WHY 1.0 IS THE DEFAULT (decision 2026-07-26). The alternative fixes were
    an env var (OMP_NUM_THREADS=1) or a non-default argument. Both fail the
    same way: they are invisible at the call site and a caller who forgets
    silently gets the irreproducible path. A default cannot be forgotten.
    Verified before adopting: at probability=1.0 the eight main big_house
    facets match the frozen pre-registration to 0.00043 deg worst case, which
    is the SAME worst-case delta the old default produced, so this does not
    restate the frozen result. Cost is wall-clock only (measured in T2,
    2026-07-26).

    Note this makes scripts/measure_roof.py run at 1.0 as well, since it does
    not pass the argument. That is intended: it is the same verified-identical
    fit, now reproducible.

    EVERY returned facet also carries "idx": the positions, in the INPUT
    `points` array, of the points that facet ended up owning, so that
    points[facet["idx"]] reproduces facet["points"] exactly. This exists to
    satisfy standing rule R1 (persist plane coefficients AND inlier indices, so
    a run is replayable from its own output). It is pure bookkeeping: no number
    below is computed from it, so it cannot change any result.

    `peel_log`, if given a list, receives one dict per RANSAC peel BEFORE the
    pitch filter: the plane's pitch, its inlier count, and whether the pitch
    filter kept it. Without this the pitch filter is silent, and a blob that
    produces no facet gives no clue whether RANSAC found nothing or found
    something the wrong shape (measured need, Task 6C, 2026-07-26)."""
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)

    # `live[i]` = where row i of the CURRENT shrunken cloud came from in the
    # original `points`. Peeling removes rows, so this is how a facet's rows are
    # traced back to the input after several peels.
    live = np.arange(len(points))

    facets = []
    for peel in range(max_planes):
        # Stop if too little is left to be a real surface.
        if len(cloud.points) < min_points:
            if peel_log is not None:
                peel_log.append({"peel": peel, "stopped": "remaining points "
                                 f"{len(cloud.points)} < min_points {min_points}"})
            break

        # RANSAC: grab the biggest flat plane in what remains.
        plane_model, inliers = cloud.segment_plane(
            distance_threshold=distance_threshold, ransac_n=3,
            num_iterations=1000, probability=probability)

        # If even the biggest remaining plane is tiny, we're done finding surfaces.
        if len(inliers) < min_points:
            if peel_log is not None:
                peel_log.append({"peel": peel, "stopped": "largest remaining "
                                 f"plane has {len(inliers)} inliers < min_points "
                                 f"{min_points}"})
            break

        normal = plane_model[:3]          # (a, b, c) from (a, b, c, d)
        pitch = tilt_degrees(normal)
        in_pitch = bool(min_pitch <= pitch <= max_pitch)

        if peel_log is not None:
            peel_log.append({"peel": peel, "n_inliers": int(len(inliers)),
                             "pitch_deg": round(float(pitch), 3),
                             "pitch_window": [min_pitch, max_pitch],
                             "kept_by_pitch": in_pitch,
                             "surface": _pitch_verdict(pitch, min_pitch, max_pitch)})

        # Keep it only if it tilts like a roof (not flat ground, not a wall).
        if in_pitch:
            sel = np.asarray(inliers, dtype=np.int64)
            plane_points = np.asarray(cloud.select_by_index(inliers).points)
            facets.append({"points": plane_points, "normal": np.asarray(normal),
                           "pitch": pitch, "idx": live[sel]})

        # Remove this plane's points (kept or not) so the next loop finds the next
        # surface. `live` is trimmed the same way, staying row-aligned with the cloud.
        drop = np.zeros(len(live), dtype=bool)
        drop[np.asarray(inliers, dtype=np.int64)] = True
        live = live[~drop]
        cloud = cloud.select_by_index(inliers, invert=True)

    # Greedy peeling steals shared-edge points: at a ridge the two roof
    # planes lie within the RANSAC band of EACH OTHER, so whichever plane is
    # found first absorbs a strip of its neighbor's points, inflating its
    # area and tilting its fit (order-dependent, so also not reproducible).
    # One reassignment pass removes the order dependence: pool every point
    # that belongs to any facet, hand each point to its NEAREST plane, then
    # refit each plane to its final members. RANSAC proposes, the final
    # consensus refits.
    if len(facets) > 1:
        pool = np.vstack([f["points"] for f in facets])
        pool_idx = np.concatenate([f["idx"] for f in facets])   # same row order as pool
        dists = np.column_stack([_point_plane_dist(pool, f) for f in facets])
        owner = dists.argmin(axis=1)          # index of the closest plane, per point
        for k, f in enumerate(facets):
            mine = pool[owner == k]
            if len(mine) < 3:                 # a plane needs 3 points; keep RANSAC's answer
                continue
            f["points"] = mine
            f["idx"] = pool_idx[owner == k]   # reassign the labels alongside the points
            f["normal"] = fit_plane_svd(mine)
            f["pitch"] = tilt_degrees(f["normal"])

    return facets


def _pitch_verdict(pitch, min_pitch, max_pitch):
    """Plain-language reason a peeled plane failed the pitch window, for the
    peel log. Below the window a surface is effectively flat (ground, a flat
    roof deck, a road); above it, effectively vertical (a wall, a dormer cheek,
    a gable end). Neither is a pitched roof facet."""
    if pitch < min_pitch:
        return f"near-flat ({pitch:.1f} deg < {min_pitch} deg)"
    if pitch > max_pitch:
        return f"near-vertical ({pitch:.1f} deg > {max_pitch} deg)"
    return "roof-pitched"


def fit_plane_svd(points):
    """Least-squares plane normal for a point set: the direction the set
    spreads LEAST along. SVD of the centered points gives the three spread
    directions sorted largest to smallest; row 2 is the smallest, i.e. the
    normal. (Same eigen-idea as the planarity filter.)"""
    centered = points - points.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    return vt[2]


def fit_plane_trimmed(points, trim_mult=3.0, max_iterations=10):
    """Robust plane fit: least-squares SVD that ignores the clutter tail.

    Plain least squares SQUARES its errors, so points far off the plane
    (dormer surfaces or chimney sides riding inside the assignment band)
    pull the normal disproportionately. Iterate: fit, measure every point's
    distance to the fit, keep only points within trim_mult x the median
    distance, refit; stop when membership stabilizes. For Gaussian noise
    the median distance is ~0.67 sigma, so trim_mult=3 keeps roughly the
    2-sigma core of the true sheet (~95% single pass, a little under that
    at the iterated fixed point, since each trim shrinks the next median)
    while rejecting a tail an order of magnitude farther out. The trim is
    symmetric, so the fitted normal stays unbiased. The trim DISTANCE is derived from the facet's
    own scatter (adapts to any cloud); trim_mult itself is a unitless
    ratio, therefore scale-independent.

    Returns (normal, kept_mask) so callers can report how much was trimmed.
    """
    keep = np.ones(len(points), dtype=bool)
    for _ in range(max_iterations):
        normal = fit_plane_svd(points[keep])
        d = np.abs((points - points[keep].mean(axis=0)) @ normal)
        trim = max(trim_mult * np.median(d[keep]), 1e-12)
        new_keep = d <= trim
        if (new_keep == keep).all():
            break
        keep = new_keep
    return fit_plane_svd(points[keep]), keep


def assign_to_planes(points, facets, max_dist):
    """Give every point to its NEAREST facet plane (the plane through each
    facet's centroid with its normal). Returns (owner, dist): owner is the
    facet index per point, -1 where the nearest plane is farther than
    max_dist; dist is the distance to that nearest plane.

    Loops over facets (few) rather than building an N x n_facets distance
    matrix, so memory stays flat on multi-million-point clouds. This is how
    a plane fit discovered on a SUBSAMPLE gets its full-resolution
    membership: fit small, assign big."""
    best = np.full(len(points), np.inf)
    owner = np.full(len(points), -1, dtype=np.int64)
    for k, f in enumerate(facets):
        d = _point_plane_dist(points, f)
        better = d < best
        best[better] = d[better]
        owner[better] = k
    owner[best > max_dist] = -1
    return owner, best


def _point_plane_dist(points, facet):
    """Perpendicular distance from each point to a facet's plane (the plane
    through the facet's centroid with the facet's normal)."""
    n = np.asarray(facet["normal"], float)
    n = n / np.linalg.norm(n)
    return np.abs((points - facet["points"].mean(axis=0)) @ n)

def level_cloud(points, up_normal):
    """Rotate the whole cloud so `up_normal` points along +Z (true vertical).

    points    : (N, 3) array to rotate.
    up_normal : (3,) the ground's 'up' direction, from fit_ground_plane.

    Returns the rotated points, same shape. After this, the ground is horizontal
    and the Z axis is真 vertical, so tilt_degrees and friends work correctly.
    """
    up_normal = np.asarray(up_normal, dtype=float)
    up_normal = up_normal / np.linalg.norm(up_normal)   # ensure length 1

    target = np.array([0.0, 0.0, 1.0])                  # where we want 'up' to point: +Z

    # Axis to rotate around = cross product of current-up and target-up.
    # This vector is perpendicular to both; it's the hinge we pivot on.
    axis = np.cross(up_normal, target)
    axis_length = np.linalg.norm(axis)

    # Degenerate case: if up_normal already ~equals target, the cross product is
    # ~zero and there's no meaningful axis. That just means "already level" --
    # return the points unchanged rather than dividing by zero.
    if axis_length < 1e-8:
        return points.copy()

    axis = axis / axis_length                           # make the axis a unit vector

    # Angle between current-up and target = arccos of their dot product.
    # Both are unit vectors, so the dot product IS the cosine of the angle.
    angle = np.arccos(np.clip(up_normal @ target, -1.0, 1.0))

    # Build the rotation from axis + angle. SciPy wants a "rotation vector":
    # the axis scaled by the angle (in radians). Then apply it to every point.
    rotation = Rotation.from_rotvec(axis * angle)
    return rotation.apply(points)