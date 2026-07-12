# roofkit/crop.py
# Phase 2, step 4 (part 1): isolate a region of a point cloud with an
# axis-aligned bounding box. This module is engine-agnostic and dataset-agnostic:
# it knows how to apply ANY box, and knows NOTHING about tyco_house specifically.
# The actual box numbers for a given cloud are chosen by the caller and passed in.

import numpy as np


def crop_box(points, min_corner, max_corner):
    """Keep only the points inside an axis-aligned bounding box.

    points     : (N, 3) array of XYZ, in the cloud's native units.
    min_corner : (x_min, y_min, z_min) -- the low corner of the box.
    max_corner : (x_max, y_max, z_max) -- the high corner of the box.

    Returns a (M, 3) array containing only the M points that fall inside
    the box on all three axes. The original array is not modified.
    """
    # Turn the corners into NumPy arrays so we can compare all 3 axes at once.
    min_corner = np.asarray(min_corner)
    max_corner = np.asarray(max_corner)

    # --- the boolean mask, the conceptual core ---
    # points >= min_corner compares EVERY point against the low corner on all
    # 3 axes at once. The result is an (N, 3) array of True/False: for each
    # point, is its x >= x_min? its y >= y_min? its z >= z_min?
    above_min = points >= min_corner          # (N, 3) of True/False
    below_max = points <= max_corner          # (N, 3) of True/False

    # A point is inside the box only if it passes on ALL THREE axes, for BOTH
    # the min and max test. .all(axis=1) collapses each row of 3 True/False
    # values into a single True (all three were True) or False (at least one
    # failed). The & combines the two conditions element-wise.
    inside = (above_min & below_max).all(axis=1)   # (N,) of True/False, one per point

    # Return BOTH the cropped points AND the mask that produced them.
    # The mask lets the caller filter colors (or any per-point array) with the
    # exact same membership test, so they stay aligned to the surviving points.
    return points[inside], inside