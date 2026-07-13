# Roof isolation filters: strip ground, walls, and vegetation BEFORE plane
# segmentation, so RANSAC only ever sees roof candidates (decisions
# 2026-07-12: vegetation is the adversary; no ground-plane RANSAC).
import numpy as np


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
