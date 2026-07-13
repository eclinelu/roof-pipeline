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


def planarity_filter(points, radius, score_max=0.05, max_nn=30):
    """Keep points whose neighborhood is sheet-like (score at or below
    score_max). Known cost: roof edges and ridges score somewhat rough and
    can be eroded; tune score_max visually against that tradeoff."""
    mask = planarity_scores(points, radius, max_nn) <= score_max
    return points[mask], mask
