# Facet discovery shared by the recon scripts: the same seed-pinned
# subsample-fit / full-assign / trimmed-refit sequence measure_roof.py
# runs, extracted so roof_recon.py and preregister.py segment the cloud
# IDENTICALLY to the 7a instrument. measure_roof.py itself is left
# untouched: it is the frozen pipeline the pre-registration commits.
import numpy as np
import open3d as o3d
from roofkit.stats import median_nn_spacing
from roofkit.segment import (find_roof_planes, assign_to_planes,
                             fit_plane_trimmed, connected_core)
from roofkit.measure import tilt_degrees


def discover_facets(points, cfg, seed=0, probability=1.0, spacing=None,
                    min_pitch=10.0, max_pitch=60.0,
                    connect_mult=None, min_component_frac=1.0,
                    plane_out=None):
    """Segment roof facets exactly as measure_roof.py does.
    Returns (facets, band, spacing_full): facets is a list of dicts
    with the trimmed core points, the robust normal, and the pitch;
    band is the RANSAC/assignment band in cu; spacing_full is the full
    cloud's median point spacing in cu.

    `probability` is Open3D's adaptive early-stop for RANSAC (see
    find_roof_planes for the full explanation). The default is 1.0, which
    DISABLES the early stop and forces the full iteration count; that is what
    makes the fit reproducible under threading (measured 2026-07-25, adopted
    as the default 2026-07-26). Verified before adopting: at 1.0 the eight
    main facets still match the frozen pre-registration to 0.00043 deg worst
    case, the same delta the old default gave, so the frozen result is not
    restated. Pass 0.99999999 to reproduce the old adaptive behaviour.

    `spacing` lets a caller pass an already-computed median spacing. This is a
    pure speed shortcut for repeated probes over the SAME cloud: the value is
    a deterministic property of the points, so supplying it cannot change any
    result. Leave it None in normal use.

    `connect_mult` is the M1a CONNECTIVITY FILTER and is OPT IN. None (the
    default) is the historical behaviour bit for bit: no filter runs and this
    function is exactly what it was, so every existing artifact stays
    reproducible. Set it to a multiple of median point spacing to require that
    a facet's points be plan-connected to its main body before the plane is
    refitted (pre-registered 2026-07-27, amended 2026-07-28). The filter runs
    HERE, on the 8 main facets, and NOT inside recover_facets: one mechanism
    per pass, and M1b is explicitly out of scope.

    Note WHERE the filter sits, because it is what makes facet identity
    comparable across a sweep: `find_roof_planes` has already run on the seeded
    subsample by this point and the filter cannot touch it. The discovered
    plane list is therefore IDENTICAL for every value of connect_mult, so facet
    k means the same surface in every run and a facet-by-facet diff is exact
    rather than a matching problem. `plane_out`, if given a list, receives the
    raw discovery normals so a caller can assert that.

    `min_component_frac` is how large a component must be to be kept, as a
    fraction of the largest component's point count. 1.0 keeps only the main
    body."""
    o3d.utility.random.seed(seed)  # RANSAC reproducibility (2026-07-13)
    rng = np.random.default_rng(seed)
    s_full = median_nn_spacing(points) if spacing is None else float(spacing)
    n_fit = min(cfg["fit_sample"], len(points))
    sub = points[rng.choice(len(points), n_fit, replace=False)]
    s_sub = median_nn_spacing(sub)
    band = cfg["band_mult"] * s_sub  # a LENGTH: scale-dependent by design
    # min_pitch/max_pitch are exposed only so a PROBE can ask what happens at
    # other values (Task 7A2). The defaults are the pipeline's real values and
    # no caller in the pipeline passes anything else, so this is inert.
    planes = find_roof_planes(sub, distance_threshold=band,
                              min_points=int(cfg["min_points_frac"] * n_fit),
                              min_pitch=min_pitch, max_pitch=max_pitch,
                              max_planes=cfg["max_planes"],
                              probability=probability)
    if plane_out is not None:
        plane_out.extend(np.asarray(p["normal"], float).copy() for p in planes)
    owner, dist = assign_to_planes(points, planes, max_dist=np.inf)
    facets = []
    for k in range(len(planes)):
        member = (owner == k) & (dist <= band)
        if member.sum() < 3:
            continue
        # flatnonzero turns the True/False mask into the row NUMBERS it selects,
        # in the same order the mask selects them; the trim then keeps a subset
        # of those rows. So idx tracks points[] exactly through both steps.
        # Carried for standing rule R1; nothing numeric reads it.
        member_idx = np.flatnonzero(member)
        mine = points[member]

        # --- M1a CONNECTIVITY FILTER, between membership and the refit -------
        # Pre-registered position: "after membership is selected and before the
        # plane is refitted". It matters that it is before: the whole claim is
        # that strays contaminate the FIT, so removing them after fitting would
        # tidy the point set and leave the defect in the normal.
        fdiag = None
        if connect_mult is not None:
            keep_conn, fdiag = connected_core(mine[:, :2],
                                              cell=connect_mult * s_full,
                                              min_frac=min_component_frac)
            # Indices of what the filter DELETED, kept so the sweep's
            # independent assertions can measure the removed set directly
            # rather than trusting the filter's own bookkeeping.
            fdiag["removed_idx"] = member_idx[~keep_conn]
            fdiag["kept_idx_premtrim"] = member_idx[keep_conn]
            mine = mine[keep_conn]
            member_idx = member_idx[keep_conn]
            if len(mine) < 3:
                continue
        normal, keep = fit_plane_trimmed(mine, trim_mult=cfg["trim_mult"])
        facets.append({"points": mine[keep], "normal": normal,
                       "pitch": tilt_degrees(normal),
                       "idx": member_idx[keep],
                       "filter": fdiag})
    return facets, band, s_full
