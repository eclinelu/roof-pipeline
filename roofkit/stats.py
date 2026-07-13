# The scale yardstick. Scale-dependent thresholds (RANSAC band, planarity
# radius, alpha) are expressed as multiples of this number so they transfer
# between clouds of different scale and density (decision 2026-07-12).
import numpy as np
from scipy.spatial import cKDTree


def median_nn_spacing(points, sample_size=20000, seed=0):
    """Median distance from a point to its single nearest neighbor.

    Queries a random sample (not every point) against the full cloud, which
    is statistically identical for a median and far cheaper on millions of
    points. k=2 because a point's nearest neighbor at k=1 is itself.
    """
    points = np.asarray(points)
    if len(points) > sample_size:
        rng = np.random.default_rng(seed)
        sample = points[rng.choice(len(points), sample_size, replace=False)]
    else:
        sample = points
    tree = cKDTree(points)
    dists, _ = tree.query(sample, k=2)
    return float(np.median(dists[:, 1]))
