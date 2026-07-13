# Synthetic point clouds with KNOWN geometry, used as ground truth in tests.
# A gable roof at a chosen pitch, a random blob standing in for foliage,
# and solid color arrays. If a pipeline stage cannot recover the known
# numbers from these, it has no business touching the real cloud.
import numpy as np


def gable_roof(pitch_deg=30.0, width=10.0, depth=6.0, n_per_side=5000,
               seed=0, noise=0.0):
    """Two rectangular planes meeting at a ridge along the Y axis.

    Footprint spans x in [-width/2, width/2], y in [0, depth]. Height is
    z = (width/2 - |x|) * tan(pitch), so the eaves sit at z=0 and the ridge
    at z = (width/2) * tan(pitch). True per-side area (slope-corrected):
    depth * (width/2) / cos(pitch).
    """
    rng = np.random.default_rng(seed)
    slope = np.tan(np.radians(pitch_deg))
    sides = []
    for sign in (-1.0, 1.0):
        x = sign * rng.uniform(0.0, width / 2.0, n_per_side)
        y = rng.uniform(0.0, depth, n_per_side)
        z = (width / 2.0 - np.abs(x)) * slope
        sides.append(np.column_stack([x, y, z]))
    points = np.vstack(sides)
    if noise > 0.0:
        points = points + rng.normal(0.0, noise, points.shape)
    return points


def gable_side_area(pitch_deg=30.0, width=10.0, depth=6.0):
    """The true slope-corrected area of ONE side of gable_roof."""
    return depth * (width / 2.0) / np.cos(np.radians(pitch_deg))


def foliage_blob(center, size, n=3000, seed=1):
    """Uniform random points in a cube: geometry with no planar structure,
    the synthetic stand-in for foliage."""
    rng = np.random.default_rng(seed)
    return rng.uniform(-0.5, 0.5, (n, 3)) * size + np.asarray(center, float)


def solid_color(n, rgb):
    """(n, 3) array of one repeated 0-1 RGB color."""
    return np.tile(np.asarray(rgb, float), (n, 1))
