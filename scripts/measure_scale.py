# Derive the tape-measured wall span from wall PATCHES, never from clicked
# corners. A corner in this cloud is the noisiest geometry in the scene:
# two fuzzy surfaces meeting, and ODM reconstructs edges worse than
# surfaces. The middle of a wall is the cleanest. So this is the ridge
# instrument's logic again: fit planes to good data, intersect them, and
# measure on the DERIVED geometry, which is more accurate than any single
# point that exists in the cloud. Run:
#
#   python scripts/measure_scale.py C:\odm\datasets\big_house --tape 10.42
#   python scripts/measure_scale.py C:\odm\datasets\big_house --click-spread
#
# Patch mode opens three picking windows in a row:
#   1/3: the TAPED wall face    -- 6-10 shift+clicks spread over the face
#   2/3: return wall at corner A -- 5-8 clicks
#   3/3: return wall at corner B -- 5-8 clicks
# Click the MIDDLE of each face: stay ~0.5 m clear of edges, windows,
# doors, gutters, vegetation. Each click gathers every cloud point within
# patch_radius and a trimmed plane fit does the precision work, so clicks
# only need to land ON the face, nowhere precise.
#
# --click-spread is the control experiment: shift+click the SAME corner
# 5+ times; the printed spread is the old click-the-corner instrument's
# empirical uncertainty per endpoint, for the error budget.
import argparse
import json
import numpy as np
import open3d as o3d
from dataset_config import load_config
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box
from roofkit.stats import median_nn_spacing
from roofkit.segment import fit_plane_trimmed, level_cloud
from roofkit.measure import tilt_degrees, plane_intersection, up_from_tilt

MAX_VIEW_POINTS = 2_000_000  # keep the picking viewer responsive


def pick(points, colors, title):
    """One picking window. Returns the clicked points' XYZ; every pick is
    an exact cloud point, not a screen estimate."""
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    cloud.colors = o3d.utility.Vector3dVector(colors)
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window(window_name=title)
    vis.add_geometry(cloud)
    vis.run()
    vis.destroy_window()
    idx = vis.get_picked_points()
    return points[idx] if idx else np.empty((0, 3))


def gather(full, clicks, radius):
    """The patch: every FULL-cloud point within radius of any click (the
    viewer may show a subsample, but the fit uses all the data)."""
    mask = np.zeros(len(full), bool)
    for c in clicks:
        mask |= ((full - c) ** 2).sum(axis=1) <= radius * radius
    return full[mask]


def wall_plane(full, clicks, radius, trim_mult, label, verbose=True):
    patch = gather(full, clicks, radius)
    normal, keep = fit_plane_trimmed(patch, trim_mult=trim_mult)
    core = patch[keep]
    centroid = core.mean(axis=0)
    scatter = np.median(np.abs((core - centroid) @ normal))
    if verbose:
        print(f"  {label}: {len(clicks)} clicks -> {len(patch):,} patch "
              f"points, kept {100 * keep.mean():.0f}%, scatter "
              f"{scatter:.4f} cu, tilt {tilt_degrees(normal):.1f} deg "
              f"(a wall should read ~90)")
    return normal, centroid


def corner_line(wall, ret, label, verbose=True):
    inter = plane_intersection(wall[0], wall[1], ret[0], ret[1])
    if inter is None:
        raise SystemExit(f"{label}: the two planes are near-parallel and do "
                         f"not define a corner. Re-pick the patches.")
    p0, d = inter
    if abs(d[2]) < 0.5:
        raise SystemExit(f"{label}: the intersection line is far from "
                         f"vertical. These patches are not the two WALLS "
                         f"of a corner (a wall-ground line would do this).")
    if verbose:
        plumb = np.degrees(np.arccos(min(abs(d[2]), 1.0)))
        print(f"  {label}: corner line off plumb by {plumb:.2f} deg")
    return p0, d / d[2]  # rescale so stepping z by 1 walks the line once


def line_at_z(line, z):
    p0, d = line
    return p0 + d * (z - p0[2])


def span_between(la, lb, z):
    return float(np.linalg.norm(line_at_z(la, z) - line_at_z(lb, z)))


def derive_span(full, cm, ca, cb, radius, trim_mult, z_eval, verbose=True):
    w = wall_plane(full, cm, radius, trim_mult, "taped wall", verbose)
    a = wall_plane(full, ca, radius, trim_mult, "return wall A", verbose)
    b = wall_plane(full, cb, radius, trim_mult, "return wall B", verbose)
    la = corner_line(w, a, "corner A", verbose)
    lb = corner_line(w, b, "corner B", verbose)
    return span_between(la, lb, z_eval), la, lb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="dataset directory (holds roofkit.json)")
    ap.add_argument("--tape", type=float, default=None,
                    help="tape-measured length of the wall span, in meters")
    ap.add_argument("--click-spread", action="store_true",
                    help="control experiment: click ONE corner 5+ times and "
                         "report the spread (the old instrument's error)")
    args = ap.parse_args()
    cfg = load_config(args.dataset)

    points, colors = load_xyz_rgb(cfg["cloud_path"])
    if cfg["crop_min"] is None or cfg["crop_max"] is None:
        raise SystemExit("set crop_min/crop_max in roofkit.json first")
    points, mask = crop_box(points, cfg["crop_min"], cfg["crop_max"])
    colors = colors[mask]

    # Distances are rotation-invariant, but 'horizontal' (the tape line,
    # the span evaluation height) is defined by the LEVELED Z, so work in
    # the same frame measure_roof measures in.
    if cfg["level_tilt_deg"] is not None:
        points = level_cloud(points, up_from_tilt(cfg["level_tilt_deg"],
                                                  cfg["level_uphill_az_deg"]))
        print(f"leveled by {cfg['level_tilt_deg']} deg, uphill azimuth "
              f"{cfg['level_uphill_az_deg']} (from roofkit.json)")

    view_pts, view_cols = points, colors
    if len(points) > MAX_VIEW_POINTS:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(points), MAX_VIEW_POINTS, replace=False)
        view_pts, view_cols = points[idx], colors[idx]
        print(f"viewer shows a {MAX_VIEW_POINTS:,}-point subsample; fits "
              f"use the full cropped cloud")

    if args.click_spread:
        clicks = pick(view_pts, view_cols,
                      "click the SAME corner 5+ times, then Q")
        if len(clicks) < 3:
            raise SystemExit("need at least 3 clicks for a spread")
        centroid = clicks.mean(axis=0)
        r = np.linalg.norm(clicks - centroid, axis=1)
        pairwise = max(np.linalg.norm(a - b)
                       for i, a in enumerate(clicks) for b in clicks[i + 1:])
        print(f"\n{len(clicks)} clicks on one corner:")
        print(f"  per-axis std (cu): x {clicks[:, 0].std():.4f}  "
              f"y {clicks[:, 1].std():.4f}  z {clicks[:, 2].std():.4f}")
        print(f"  RMS distance from centroid: {np.sqrt((r ** 2).mean()):.4f} cu")
        print(f"  worst pair: {pairwise:.4f} cu")
        print("this is the click-the-corner instrument's empirical "
              "uncertainty PER ENDPOINT; it belongs in the error budget.")
        return

    s = median_nn_spacing(points)
    radius = cfg["patch_radius_mult"] * s
    print(f"cropped cloud {len(points):,} points, spacing {s:.4f} cu, patch "
          f"radius {radius:.4f} cu ({cfg['patch_radius_mult']} x spacing)")

    cm = pick(view_pts, view_cols,
              "1/3 TAPED WALL: 6-10 clicks spread over the face, then Q")
    ca = pick(view_pts, view_cols,
              "2/3 RETURN WALL at corner A: 5-8 clicks, then Q")
    cb = pick(view_pts, view_cols,
              "3/3 RETURN WALL at corner B: 5-8 clicks, then Q")
    if min(len(cm), len(ca), len(cb)) < 2:
        raise SystemExit("each window needs at least 2 clicks")

    z_eval = float(np.median(cm[:, 2]))
    print(f"\nplane fits (trim_mult {cfg['trim_mult']}):")
    span, la, lb = derive_span(points, cm, ca, cb, radius,
                               cfg["trim_mult"], z_eval)

    # If the corner edges are truly plumb, the span does not depend on
    # where the tape was held. Print that dependence instead of assuming it.
    print(f"\nderived span at z = {z_eval:.2f} (taped-wall patch height): "
          f"{span:.4f} cu")
    for dz in (-1.0, 1.0):
        print(f"  at z {dz:+.0f} cu: "
              f"{span_between(la, lb, z_eval + dz):.4f} cu")

    # Split-half repeatability: the same derivation twice from disjoint
    # half-patches. The difference is the instrument's empirical noise.
    if min(len(cm), len(ca), len(cb)) >= 4:
        halves = [derive_span(points, cm[off::2], ca[off::2], cb[off::2],
                              radius, cfg["trim_mult"], z_eval,
                              verbose=False)[0]
                  for off in (0, 1)]
        print(f"split-half repeatability: |{halves[0]:.4f} - "
              f"{halves[1]:.4f}| = {abs(halves[0] - halves[1]):.4f} cu")
    else:
        print("(4+ clicks per window enables the split-half check)")

    if args.tape is not None:
        factor = args.tape / span
        print(f"\ntape {args.tape} m over derived span {span:.4f} cu")
        print(f"scale factor: {factor:.4f} m per cloud unit")
        print(f"measured GPS scale error: {100 * (factor - 1):+.2f}% linear, "
              f"{100 * (factor ** 2 - 1):+.2f}% on area")
        print("\npaste into roofkit.json:")
        print(json.dumps({"scale_span_cu": round(span, 4),
                          "scale_true_m": args.tape}, indent=2))
    else:
        print("\n(no --tape given: re-run with --tape LENGTH_M to get the "
              "scale factor and the roofkit.json snippet)")


if __name__ == "__main__":
    main()
