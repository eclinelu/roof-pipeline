# Stages 5-7a on any isolated roof: segment facets, run the Z gate, report
# per-facet pitch and slope area. Run:
#   python scripts/measure_roof.py C:\odm\datasets\big_house [--no-view]
#
# Plane DISCOVERY runs on a random subsample (cfg fit_sample); membership,
# refit, pitch, azimuth, and area use the full cloud. Band diagnostics
# print in physical units BEFORE any render. The Z gate residual prints as
# a number BEFORE any trusted output; above gate_limit_deg the script
# STOPS: leveling is a human decision (2026-07-13), never automatic.
# Areas are in cloud units squared until the tape scale factor is applied.
import argparse
import numpy as np
import open3d as o3d
from dataset_config import load_config
from roofkit.stats import median_nn_spacing
from roofkit.segment import (find_roof_planes, assign_to_planes,
                             fit_plane_trimmed)
from roofkit.measure import (tilt_degrees, azimuth_degrees, z_tilt_residual,
                             facet_area)

# Cap on points fed to one facet's Delaunay triangulation. The alpha shape
# only needs the boundary well sampled; alpha is derived from the spacing
# of the points ACTUALLY used, so the area estimate is consistent at any
# cap. Uncapped, a 2M-point facet costs minutes and gigabytes in Qhull.
AREA_MAX_POINTS = 400_000


def show_facets(facets):
    rng = np.random.default_rng(0)
    clouds = []
    for f in facets:
        c = o3d.geometry.PointCloud()
        c.points = o3d.utility.Vector3dVector(f["points"])
        c.paint_uniform_color(rng.uniform(0.1, 0.9, 3))
        clouds.append(c)
    o3d.visualization.draw_geometries(clouds, window_name="facets")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="dataset directory (holds roofkit.json)")
    ap.add_argument("--no-view", action="store_true",
                    help="skip the per-facet color viewer")
    ap.add_argument("--clutter", default="",
                    help="comma-separated facet ids to show colored by core "
                         "(gray, within band) vs tail (red, band..5x band)")
    args = ap.parse_args()
    cfg = load_config(args.dataset)

    # Pin Open3D's internal RNG (Open3D 0.19 exposes it): without this,
    # RANSAC discovery is nondeterministic and facets near the
    # min_points_frac floor flicker between runs (observed 2026-07-13).
    o3d.utility.random.seed(0)

    points = np.load(cfg["roof_path"])
    s_full = median_nn_spacing(points)
    rng = np.random.default_rng(0)
    n_fit = min(cfg["fit_sample"], len(points))
    sub = points[rng.choice(len(points), n_fit, replace=False)]
    s_sub = median_nn_spacing(sub)
    band = cfg["band_mult"] * s_sub
    print(f"{len(points):,} roof points")
    print(f"median spacing: full cloud {s_full * 100:.2f} cm, "
          f"fit subsample ({n_fit:,} pts) {s_sub * 100:.2f} cm")
    print(f"RANSAC/assignment band = {cfg['band_mult']} x subsample spacing "
          f"= {band * 100:.2f} cm")

    facets = find_roof_planes(sub, distance_threshold=band,
                              min_points=int(cfg["min_points_frac"] * n_fit),
                              max_planes=cfg["max_planes"])
    print(f"\n{len(facets)} planes discovered on the subsample")

    # Full-cloud membership, with the band-vs-sheet diagnostic per facet:
    # scatter is measured in a generous 5x band window so a sheet thicker
    # than the band shows up as a number, not as a moth-eaten render.
    owner, dist = assign_to_planes(points, facets, max_dist=np.inf)
    print(f"\nband vs sheet thickness (cm) [p90 = 90% of a facet's points "
          f"sit closer than this]:")
    print(f"{'facet':>5} {'members':>11} {'median|d|':>10} {'p90|d|':>8} "
          f"{'band':>7}  verdict")
    clutter_ids = {int(x) for x in args.clutter.split(",") if x.strip()}
    clutter_views = []
    kept = []
    for k in range(len(facets)):
        near = (owner == k) & (dist <= 5.0 * band)
        member = (owner == k) & (dist <= band)
        if member.sum() < 3:
            continue
        d = dist[near]
        med, p90 = np.median(d), np.percentile(d, 90)
        verdict = "ok" if p90 <= band else "FAT TAIL (clutter near plane)"
        print(f"{k:>5} {member.sum():>11,} {med * 100:>9.2f} {p90 * 100:>7.2f} "
              f"{band * 100:>6.2f}  {verdict}")
        if k in clutter_ids:
            clutter_views.append((k, points[near], dist[near]))
        mine = points[member]
        # Robust refit: least squares squares its errors, so clutter riding
        # inside the band (dormer surfaces) pulls a plain fit. Trim to each
        # facet's own median scatter and refit (decision 2026-07-13).
        normal, keep = fit_plane_trimmed(mine, trim_mult=cfg["trim_mult"])
        trim_cm = 100 * cfg["trim_mult"] * np.median(
            np.abs((mine[keep] - mine[keep].mean(axis=0)) @ normal))
        kept.append({"points": mine[keep], "normal": normal,
                     "pitch": tilt_degrees(normal),
                     "kept_frac": keep.mean(), "trim_cm": trim_cm})
    facets = kept

    print(f"\ntrimmed refit (trim_mult {cfg['trim_mult']} x per-facet median "
          f"scatter):")
    print(f"{'facet':>5} {'kept %':>7} {'trim cm':>8} {'pitch deg':>10}")
    for k, f in enumerate(facets):
        print(f"{k:>5} {100 * f['kept_frac']:>6.1f} {f['trim_cm']:>8.2f} "
              f"{f['pitch']:>10.2f}")

    if clutter_views:
        for k, pts_v, d_v in clutter_views:
            c = o3d.geometry.PointCloud()
            c.points = o3d.utility.Vector3dVector(pts_v)
            colors = np.full((len(pts_v), 3), 0.75)
            colors[d_v > band] = (1.0, 0.15, 0.15)
            c.colors = o3d.utility.Vector3dVector(colors)
            o3d.visualization.draw_geometries(
                [c], window_name=f"facet {k}: red = beyond band (clutter)")
    off_facet = (dist > band).sum()
    print(f"not within the band of any plane: {off_facet:,} points "
          f"({100 * off_facet / len(points):.1f}%) "
          f"[chimneys, dormers below min_points_frac, filter leftovers]")

    if not args.no_view:
        show_facets(facets)

    # --- Z-verification gate, BEFORE any trusted numbers ---
    residual, pairs = z_tilt_residual(facets)
    if residual is None:
        print("\nGATE: no opposing facet pair found. No instrument for Z.")
        print("STOP: a fallback vertical reference must be chosen before any")
        print("pitch from this cloud can be trusted.")
        return
    print("\nZ gate evidence, one row per opposing pair "
          "(a true gable pair: azimuths ~180 apart, comparable sizes):")
    print(f"{'pair':>7} {'az_i':>6} {'az_j':>6} {'az diff':>8} {'pitch_i':>8} "
          f"{'pitch_j':>8} {'pts_i':>10} {'pts_j':>10} {'residual':>9}")
    for i, j in pairs:
        ai, aj = azimuth_degrees(facets[i]["normal"]), azimuth_degrees(facets[j]["normal"])
        diff = 180.0 - abs(abs(ai - aj) - 180.0)  # angular separation
        r = abs(facets[i]["pitch"] - facets[j]["pitch"]) / 2.0
        print(f"{i:>3},{j:>3} {ai:>6.1f} {aj:>6.1f} {diff:>8.1f} "
              f"{facets[i]['pitch']:>8.2f} {facets[j]['pitch']:>8.2f} "
              f"{len(facets[i]['points']):>10,} {len(facets[j]['points']):>10,} "
              f"{r:>9.2f}")
    print(f"\nGATE residual (worst pair): {residual:.2f} deg "
          f"(limit {cfg['gate_limit_deg']})")
    if residual > cfg["gate_limit_deg"]:
        print("GATE FAILED: the cloud's Z axis is tilted by this residual and")
        print("every pitch below would be wrong by it. STOPPING before the")
        print("area report. Leveling (vertical_from_pair + level_cloud) is")
        print("available but is a human decision, not an automatic one.")
        return

    # --- 7a report ---
    print(f"\n{'facet':>5} {'points':>11} {'pitch deg':>10} {'rise:run':>9} "
          f"{'azimuth':>8} {'area':>10}")
    total = 0.0
    for k, f in enumerate(facets):
        pts_f = f["points"]
        note = ""
        if len(pts_f) > AREA_MAX_POINTS:
            pts_f = pts_f[rng.choice(len(pts_f), AREA_MAX_POINTS, replace=False)]
            note = "*"
        s_f = median_nn_spacing(pts_f)
        area = facet_area(pts_f, f["normal"], alpha=cfg["alpha_mult"] * s_f)
        total += area
        rise = 12.0 * np.tan(np.radians(f["pitch"]))
        print(f"{k:>5} {len(f['points']):>11,} {f['pitch']:>10.2f} "
              f"{rise:>7.1f}:12 {azimuth_degrees(f['normal']):>8.1f} "
              f"{area:>10.2f}{note}")
    print(f"\n(* area computed on a {AREA_MAX_POINTS:,}-point subsample; "
          f"alpha derived from that subsample's own spacing)")
    print(f"total roof area: {total:.2f} cloud units^2")
    print(f"pitch uncertainty floor (gate residual): {residual:.2f} deg")
    print("scale note: multiply areas by (tape scale factor)^2 before "
          "comparing to real dimensions.")


if __name__ == "__main__":
    main()
