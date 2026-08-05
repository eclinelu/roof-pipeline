# Roof isolation filters: strip ground, walls, and vegetation BEFORE plane
# segmentation, so RANSAC only ever sees roof candidates (decisions
# 2026-07-12: vegetation is the adversary; no ground-plane RANSAC).
import numpy as np
import open3d as o3d


def height_cutoff(points, z_min):
    """Keep points at or above z_min. With a georeferenced cloud and a tight
    crop, one cut below eave height removes sloped ground and the thin
    partial walls in a single stroke. z_min is site-specific and chosen
    visually by the caller; it does not belong in this module as a constant."""
    mask = points[:, 2] >= z_min
    return points[mask], mask


def excess_green(colors):
    """ExG = 2G - R - B per point, on 0-1 RGB. Foliage scores high, gray or
    brown shingle scores near zero. Unitless, therefore scale-independent.
    ASSUMPTION (logged 2026-07-12): the roof is not green. Fails on green,
    moss-covered, or copper-patina roofs."""
    return 2.0 * colors[:, 1] - colors[:, 0] - colors[:, 2]


def color_filter(points, colors, exg_max=0.1):
    """Keep points that are NOT green (ExG at or below exg_max)."""
    mask = excess_green(colors) <= exg_max
    return points[mask], mask


def planarity_scores(points, radius, max_nn=30):
    """Surface variation per point: how confetti-like is the neighborhood?

    For each point, Open3D fits a covariance to the neighbors within
    `radius` (capped at max_nn, in C++, so it is fast). The covariance's
    three eigenvalues measure the neighborhood's spread along its three
    principal directions. On a flat sheet the smallest eigenvalue is ~0
    (no spread off the plane); in foliage all three are comparable.
    The score is smallest_eigenvalue / sum, ranging 0 (perfect plane) to
    1/3 (isotropic confetti). The RATIO is unitless and scale-independent;
    the RADIUS is a length and therefore scale-DEPENDENT: callers derive
    it from median_nn_spacing, never hardcode it.
    """
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    cloud.estimate_covariances(
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=max_nn))
    eig = np.linalg.eigvalsh(np.asarray(cloud.covariances))  # ascending
    total = eig.sum(axis=1)
    scores = np.full(len(points), 1.0 / 3.0)  # degenerate = worst case
    ok = total > 1e-12  # points with too few neighbors have ~zero covariance
    scores[ok] = eig[ok, 0] / total[ok]
    return scores


def planarity_scores_blocked(points, radius, max_nn=30, max_block=8_000_000):
    """planarity_scores computed one spatial tile at a time.

    WHY. The score is a LOCAL operator: a point's value depends only on the
    neighbours within `radius` of it. Nothing in it couples one end of the roof
    to the other. But the implementation is not local in MEMORY -- Open3D
    materialises one 3x3 covariance per point, so the ultra cloud's ~71M
    post-colour points need about 5.1 GB for the covariances alone, plus the
    cloud and the KD-tree, against the 6.8 GB of free physical memory actually
    available. The whole-cloud call does not fit, and paging a 5 GB array
    through a KD-tree traversal is not a workaround, it is a way to wait a day.

    HOW IT STAYS EXACT. The points are partitioned into tiles by X. Each tile is
    processed together with a HALO of width `radius` on both sides, so every
    point in the tile CORE sees the identical neighbourhood it would have seen
    in the whole cloud -- a neighbour more than `radius` away cannot influence
    it by definition of the radius search, and every neighbour within `radius`
    is inside the halo by construction. Scores are written back to the core
    points' ORIGINAL positions, so the returned array is in input order.

    The halo is `radius`, not a multiple of it. It is not a tolerance and not a
    tuning knob: it is exactly the support of the operator, so any smaller value
    is wrong and any larger value is wasted work.

    `max_block` sets the target core size and therefore only trades peak memory
    against the number of passes. It cannot change a score, because the halo
    already guarantees each core point's neighbourhood is complete. The
    equivalence is asserted against the whole-cloud path in tests rather than
    argued, because "the tile boundary is handled correctly" is exactly the kind
    of claim that is easy to believe and easy to get wrong.
    """
    n = len(points)
    if n <= max_block:
        return planarity_scores(points, radius, max_nn)

    order = np.argsort(points[:, 0], kind="stable")
    xs = points[order, 0]
    n_tiles = int(np.ceil(n / max_block))
    # Split by COUNT, not by equal X width, so a dense strip of roof cannot
    # produce one tile holding most of the cloud and defeat the whole point.
    bounds = [int(round(k * n / n_tiles)) for k in range(n_tiles + 1)]

    scores = np.full(n, np.nan)
    for k in range(n_tiles):
        lo, hi = bounds[k], bounds[k + 1]
        if lo >= hi:
            continue
        core_idx = order[lo:hi]
        x_lo, x_hi = xs[lo], xs[hi - 1]
        # Halo membership is found on the sorted axis, so it costs a search,
        # not a scan of the whole cloud per tile.
        h_lo = int(np.searchsorted(xs, x_lo - radius, side="left"))
        h_hi = int(np.searchsorted(xs, x_hi + radius, side="right"))
        halo_idx = order[h_lo:h_hi]

        sub = planarity_scores(points[halo_idx], radius, max_nn)
        # Position of each core point inside the halo block.
        core_pos = np.arange(lo - h_lo, hi - h_lo)
        scores[core_idx] = sub[core_pos]

    if np.isnan(scores).any():
        raise AssertionError(
            f"planarity_scores_blocked left {int(np.isnan(scores).sum())} points "
            f"unscored; the tiling did not cover every point"
        )
    return scores


def planarity_filter(points, radius, score_max=0.05, max_nn=30):
    """Keep points whose neighborhood is sheet-like (score at or below
    score_max). Known cost: roof edges and ridges score somewhat rough and
    can be eroded; tune score_max visually against that tradeoff."""
    mask = planarity_scores(points, radius, max_nn) <= score_max
    return points[mask], mask
