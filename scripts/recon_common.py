# Facet discovery shared by the recon scripts: the same seed-pinned
# subsample-fit / full-assign / trimmed-refit sequence measure_roof.py
# runs, extracted so roof_recon.py and preregister.py segment the cloud
# IDENTICALLY to the 7a instrument. measure_roof.py itself is left
# untouched: it is the frozen pipeline the pre-registration commits.
import numpy as np
import open3d as o3d
from roofkit.stats import median_nn_spacing
from roofkit.segment import (find_roof_planes, assign_to_planes,
                             fit_plane_trimmed)
from roofkit.measure import tilt_degrees


def discover_facets(points, cfg, seed=0):
    """Segment roof facets exactly as measure_roof.py does.
    Returns (facets, band, spacing_full): facets is a list of dicts
    with the trimmed core points, the robust normal, and the pitch;
    band is the RANSAC/assignment band in cu; spacing_full is the full
    cloud's median point spacing in cu."""
    o3d.utility.random.seed(seed)  # RANSAC reproducibility (2026-07-13)
    rng = np.random.default_rng(seed)
    s_full = median_nn_spacing(points)
    n_fit = min(cfg["fit_sample"], len(points))
    sub = points[rng.choice(len(points), n_fit, replace=False)]
    s_sub = median_nn_spacing(sub)
    band = cfg["band_mult"] * s_sub  # a LENGTH: scale-dependent by design
    planes = find_roof_planes(sub, distance_threshold=band,
                              min_points=int(cfg["min_points_frac"] * n_fit),
                              max_planes=cfg["max_planes"])
    owner, dist = assign_to_planes(points, planes, max_dist=np.inf)
    facets = []
    for k in range(len(planes)):
        member = (owner == k) & (dist <= band)
        if member.sum() < 3:
            continue
        mine = points[member]
        normal, keep = fit_plane_trimmed(mine, trim_mult=cfg["trim_mult"])
        facets.append({"points": mine[keep], "normal": normal,
                       "pitch": tilt_degrees(normal)})
    return facets, band, s_full
