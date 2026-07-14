# Stages 5-7a on any isolated roof: segment facets, run the Z gate, report
# per-facet pitch and slope area. Run:
#   python scripts/measure_roof.py C:\odm\datasets\big_house [--no-view]
#
# Plane DISCOVERY runs on a random subsample (cfg fit_sample); membership,
# refit, pitch, azimuth, and area use the full cloud. Band diagnostics
# print in CLOUD UNITS before any render (georeferenced scale is untested;
# no diagnostic labels it as cm/m). The vertical reference is the
# RIDGE INSTRUMENT (decision 2026-07-13): real ridges are level, so a
# measured ridge inclination IS cloud tilt, no symmetry assumption. The
# symmetry residual is demoted to an asymmetry report. Above gate_limit_deg
# the script STOPS and prints the measured tilt vector; putting it into
# roofkit.json (level_tilt_deg / level_uphill_az_deg) is a human decision,
# never automatic. Areas are in cloud units squared until the tape scale
# factor is applied; that scale is a SEPARATE untested assumption from the
# rotation this corrects.
import argparse
import numpy as np
import open3d as o3d
from dataset_config import load_config
from roofkit.stats import median_nn_spacing
from roofkit.segment import (find_roof_planes, assign_to_planes,
                             fit_plane_trimmed, level_cloud)
from roofkit.measure import (tilt_degrees, azimuth_degrees, opposing_pairs,
                             ridge_line, tilt_from_ridges, up_from_tilt,
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

    # Leveling happens HERE, before anything reads a coordinate, so every
    # downstream quantity that references Z (pitch, azimuth, the ridge
    # readings, the gate) inherits the corrected frame. The correction is
    # measured site data, so it lives in roofkit.json, not in code.
    if cfg["level_tilt_deg"] is not None:
        up = up_from_tilt(cfg["level_tilt_deg"], cfg["level_uphill_az_deg"])
        points = level_cloud(points, up)
        print(f"LEVELED: removed {cfg['level_tilt_deg']:.3f} deg tilt, uphill "
              f"azimuth {cfg['level_uphill_az_deg']:.1f} (ridge-measured). "
              f"Null check: ridge inclinations below must read ~0.")
    else:
        print("NOT LEVELED: georeferenced Z taken as vertical, pending the "
              "ridge readings below.")

    s_full = median_nn_spacing(points)
    rng = np.random.default_rng(0)
    n_fit = min(cfg["fit_sample"], len(points))
    sub = points[rng.choice(len(points), n_fit, replace=False)]
    s_sub = median_nn_spacing(sub)
    band = cfg["band_mult"] * s_sub
    # Diagnostics print in CLOUD UNITS (cu), never cm/m: the georeferenced
    # scale is an untested assumption, and labeling it as a real unit
    # presents GPS scale as fact (the 2026-07-13 lesson, applied to units).
    print(f"{len(points):,} roof points")
    print(f"median spacing: full cloud {s_full:.4f} cu, "
          f"fit subsample ({n_fit:,} pts) {s_sub:.4f} cu")
    print(f"RANSAC/assignment band = {cfg['band_mult']} x subsample spacing "
          f"= {band:.4f} cu")

    facets = find_roof_planes(sub, distance_threshold=band,
                              min_points=int(cfg["min_points_frac"] * n_fit),
                              max_planes=cfg["max_planes"])
    print(f"\n{len(facets)} planes discovered on the subsample")

    # Full-cloud membership, with the band-vs-sheet diagnostic per facet:
    # scatter is measured in a generous 5x band window so a sheet thicker
    # than the band shows up as a number, not as a moth-eaten render.
    owner, dist = assign_to_planes(points, facets, max_dist=np.inf)
    print(f"\nband vs sheet thickness (cloud units) [p90 = 90% of a facet's "
          f"points sit closer than this]:")
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
        print(f"{k:>5} {member.sum():>11,} {med:>9.4f} {p90:>7.4f} "
              f"{band:>6.4f}  {verdict}")
        if k in clutter_ids:
            clutter_views.append((k, points[near], dist[near]))
        mine = points[member]
        # Robust refit: least squares squares its errors, so clutter riding
        # inside the band (dormer surfaces) pulls a plain fit. Trim to each
        # facet's own median scatter and refit (decision 2026-07-13).
        normal, keep = fit_plane_trimmed(mine, trim_mult=cfg["trim_mult"])
        trim_cu = cfg["trim_mult"] * np.median(
            np.abs((mine[keep] - mine[keep].mean(axis=0)) @ normal))
        kept.append({"points": mine[keep], "normal": normal,
                     "pitch": tilt_degrees(normal),
                     "kept_frac": keep.mean(), "trim_cu": trim_cu})
    facets = kept

    print(f"\ntrimmed refit (trim_mult {cfg['trim_mult']} x per-facet median "
          f"scatter):")
    print(f"{'facet':>5} {'kept %':>7} {'trim cu':>8} {'pitch deg':>10}")
    for k, f in enumerate(facets):
        print(f"{k:>5} {100 * f['kept_frac']:>6.1f} {f['trim_cu']:>8.4f} "
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

    # --- Vertical reference gate: ridge inclination (2026-07-13) ---
    # One row per opposing pair. The contact-height fractions certify a
    # TRUE ridge pair (contact at the TOP of both facets); only those are
    # instruments. The symmetry residual column is now the pair's measured
    # ASYMMETRY, a property of the building, not the gate.
    pairs = opposing_pairs(facets)
    if not pairs:
        print("\nGATE: no opposing facet pair found. No instrument for Z.")
        print("STOP: a fallback vertical reference must be chosen before any")
        print("pitch from this cloud can be trusted.")
        return
    contact_dist = cfg["ridge_contact_mult"] * s_full
    print(f"\nridge instrument, contact zone {contact_dist:.4f} cu "
          f"({cfg['ridge_contact_mult']} x full-cloud spacing):")
    print(f"{'pair':>7} {'ridge az':>9} {'incline':>8} {'frac_i':>7} "
          f"{'frac_j':>7} {'contacts':>17} {'sym resid':>10}  verdict")
    ridge_readings = []
    worst = None
    for i, j in pairs:
        sym = abs(facets[i]["pitch"] - facets[j]["pitch"]) / 2.0
        r = ridge_line(facets[i]["points"], facets[j]["points"], contact_dist)
        if r is None:
            print(f"{i:>3},{j:>3} {'-':>9} {'-':>8} {'-':>7} {'-':>7} "
                  f"{'-':>17} {sym:>10.2f}  planes do not meet")
            continue
        is_ridge = (r["frac_a"] >= cfg["ridge_frac_min"]
                    and r["frac_b"] >= cfg["ridge_frac_min"])
        verdict = "RIDGE" if is_ridge else "not a ridge pair (no instrument)"
        contacts = f"{r['n_a']:,}/{r['n_b']:,}"
        print(f"{i:>3},{j:>3} {r['azimuth_deg']:>9.1f} "
              f"{r['inclination_deg']:>8.2f} {r['frac_a']:>7.2f} "
              f"{r['frac_b']:>7.2f} {contacts:>17} {sym:>10.2f}  {verdict}")
        if is_ridge:
            ridge_readings.append((r["azimuth_deg"], r["inclination_deg"]))
            worst = max(worst if worst is not None else 0.0,
                        abs(r["inclination_deg"]))
    if not ridge_readings:
        print("\nGATE: no TRUE ridge pair (contact fractions all below "
              f"{cfg['ridge_frac_min']}). No instrument for Z. STOP.")
        return
    if len(ridge_readings) >= 2:
        t_deg, az_deg = tilt_from_ridges(ridge_readings)
        print(f"\ntilt vector from {len(ridge_readings)} ridges: "
              f"{t_deg:.3f} deg, uphill azimuth {az_deg:.1f}")
    print(f"\nGATE residual (worst ridge inclination): {worst:.2f} deg "
          f"(limit {cfg['gate_limit_deg']})")
    if worst > cfg["gate_limit_deg"]:
        print("GATE FAILED: real ridges are level and this cloud's are not,")
        print("so its vertical is tilted and every pitch below would be wrong")
        print("by it. STOPPING before the area report. To level: copy the")
        print("tilt vector above into roofkit.json as level_tilt_deg and")
        print("level_uphill_az_deg (a human decision, never automatic; with")
        print("only one ridge, only the component along it is measurable).")
        return
    residual = worst

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
    print(f"pitch uncertainty floor (worst residual ridge inclination): "
          f"{residual:.2f} deg")
    print("scale note: areas are CLOUD UNITS squared. Multiply by (tape "
          "scale factor)^2 before comparing to real dimensions; the "
          "georeferenced scale is a separate, untested assumption.")


if __name__ == "__main__":
    main()
