# Wall-quality reconnaissance BEFORE the tape comes out (2026-07-14): the
# cloud is the fixed thing and the tape is the flexible thing, so find the
# edge the cloud measures best and tape THAT. No tape number enters this
# script. Every candidate span is derived from the cloud alone, with a
# split-half repeatability, and ranked by the error a tape measurement of
# that edge would actually deliver.
#
#   python scripts/wall_recon.py C:\odm\datasets\big_house [--no-view]
#
# Pipeline: crop -> level -> per-point normals on a subsample -> keep
# near-vertical surfaces (walls) -> RANSAC-peel wall planes -> split
# coplanar-but-disjoint segments into separate faces -> find corners
# (plane intersections that real points actually support on BOTH sides,
# the same contact idea that validates ridges) -> derive every span a
# face with two corners offers -> split-half repeatability -> rank.
#
# The viewer paints each wall face a named palette color over the true-
# color cloud and draws every validated corner line in red, so weak walls
# are visible as sparse paint, not just as numbers.
import argparse
import numpy as np
import open3d as o3d
from dataset_config import load_config
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box
from roofkit.stats import median_nn_spacing
from roofkit.segment import find_roof_planes, fit_plane_trimmed, level_cloud
from roofkit.measure import (tilt_degrees, azimuth_degrees,
                             plane_intersection, up_from_tilt)

RECON_SAMPLE = 4_000_000   # covariance-estimation cap (memory bound)
MAX_VIEW_POINTS = 1_500_000
MIN_WALL_TILT = 75.0       # a surface steeper than this reads as wall
NORMAL_RADIUS_MULT = 20.0  # neighborhood for normals; must be several x
                           # the sheet noise or normals read as confetti
                           # (first run: 5x gave 59% "vertical" points)
MIN_FACE_POINTS = 1_200    # sample points; smaller cannot anchor a fit
MIN_FACE_LEN = 1.5         # cu; shorter vertical patches are not walls
MIN_FACE_HEIGHT = 1.0      # cu
MIN_CORNER_POINTS = 300    # per side inside the corner contact zone
MIN_CORNER_HEIGHT = 1.0    # cu; a corner needs vertical extent, not a spot
MIN_PLUMB_DZ = 0.99        # corner line within ~8 deg of vertical
MIN_STRIKE_DIFF = 15.0     # deg between wall directions to form a corner
                           # (this house's wings meet at ~24 deg in plan,
                           # so 30 was too strict; below ~15 the line
                           # position degrades as 1/sin and is not worth it)
CONTACT_MULT = 15.0        # corner contact radius = mult * spacing
MIN_SPAN = 2.0             # cu; shorter edges dilute nothing
TAPE_ERR = 0.01            # m; the tape is good to about a centimeter
# Parallel-pair instrument: two near-parallel wall planes bounding the
# same wing. The span is the perpendicular separation, taped across the
# wing's END face (hook the two corner arrises). Out-of-square end walls
# enter only as sec(angle): 2 deg off-square is 0.06%, negligible.
PARALLEL_STRIKE_MAX = 5.0  # deg; wall strikes this close count as parallel
MIN_OVERLAP = 1.0          # cu of shared extent along the wing
SEP_MIN, SEP_MAX = 2.0, 20.0  # cu; plausible building-width window

PALETTE = [("blue", (0.12, 0.29, 0.69)), ("orange", (1.0, 0.50, 0.05)),
           ("green", (0.10, 0.60, 0.20)), ("purple", (0.50, 0.20, 0.60)),
           ("cyan", (0.00, 0.70, 0.80)), ("yellow", (0.90, 0.80, 0.10)),
           ("magenta", (0.90, 0.20, 0.60)), ("brown", (0.55, 0.35, 0.15)),
           ("lime", (0.50, 0.90, 0.20)), ("navy", (0.05, 0.10, 0.40)),
           ("teal", (0.00, 0.50, 0.50)), ("olive", (0.50, 0.50, 0.10))]


def wall_length(face):
    """Horizontal extent of a face along its own wall direction."""
    n = face["normal"]
    u = np.cross(n, [0.0, 0.0, 1.0])
    u = u / np.linalg.norm(u)
    along = face["points"] @ u
    return float(along.max() - along.min())


def strike_diff_deg(na, nb):
    """Angle between two walls' horizontal facings, folded to [0, 90]."""
    ha, hb = na.copy(), nb.copy()
    ha[2] = 0.0
    hb[2] = 0.0
    la, lb = np.linalg.norm(ha), np.linalg.norm(hb)
    if la < 1e-9 or lb < 1e-9:
        return 0.0
    c = abs(ha @ hb) / (la * lb)
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def line_contact(pts, p0, d, radius):
    """Points of a face within radius of a corner line."""
    rel = pts - p0
    along = rel @ d
    radial = np.linalg.norm(rel - np.outer(along, d), axis=1)
    return pts[radial <= radius]


def corner_between(face_a, face_b, radius):
    """A validated corner: the two planes intersect in a near-plumb line
    that real points support on both sides. Returns None (with a reason)
    when they do not."""
    inter = plane_intersection(face_a["normal"], face_a["centroid"],
                               face_b["normal"], face_b["centroid"])
    if inter is None:
        return None, "planes near-parallel"
    p0, d = inter
    if abs(d[2]) < MIN_PLUMB_DZ:
        return None, f"line off plumb by {np.degrees(np.arccos(min(abs(d[2]), 1.0))):.1f} deg"
    ca = line_contact(face_a["points"], p0, d, radius)
    cb = line_contact(face_b["points"], p0, d, radius)
    if min(len(ca), len(cb)) < MIN_CORNER_POINTS:
        return None, f"contact too sparse ({len(ca):,}/{len(cb):,} pts)"
    z_all = np.concatenate([ca[:, 2], cb[:, 2]])
    zlo, zhi = float(z_all.min()), float(z_all.max())
    if zhi - zlo < MIN_CORNER_HEIGHT:
        return None, f"contact zone only {zhi - zlo:.2f} cu tall"
    d = d / d[2]  # rescale: stepping z by 1 walks the line once
    return {"p0": p0, "d": d, "n_a": len(ca), "n_b": len(cb),
            "zlo": zlo, "zhi": zhi,
            "plumb": float(np.degrees(np.arccos(
                min(1.0, 1.0 / np.linalg.norm(d)))))}, None


def line_at_z(p0, d, z):
    return p0 + d * (z - p0[2])


def span_from_points(pts_w, pts_a, pts_b, trim_mult, z_eval):
    """Derive the corner-to-corner span from raw point sets alone (used by
    the split-half check, so it must not reuse the full-set fits)."""
    fits = []
    for pts in (pts_w, pts_a, pts_b):
        normal, keep = fit_plane_trimmed(pts, trim_mult=trim_mult)
        fits.append((normal, pts[keep].mean(axis=0)))
    lines = []
    for k in (1, 2):
        inter = plane_intersection(fits[0][0], fits[0][1],
                                   fits[k][0], fits[k][1])
        if inter is None or abs(inter[1][2]) < MIN_PLUMB_DZ:
            return None
        p0, d = inter
        lines.append((p0, d / d[2]))
    return float(np.linalg.norm(line_at_z(*lines[0], z_eval)
                                - line_at_z(*lines[1], z_eval)))


def sep_at(pts_i, pts_j, trim_mult, t_eval, u):
    """Separation between two near-parallel wall planes at strike
    coordinate t_eval. Fit one plane, take the other face's signed
    perpendicular distances to it as a LINEAR function of position along
    the wing, read it at t_eval; then swap roles and average. The linear
    fit means slightly non-parallel walls still yield the separation AT
    one chosen spot, which is where the tape will physically go."""
    seps = []
    for a, b in ((pts_i, pts_j), (pts_j, pts_i)):
        normal, keep = fit_plane_trimmed(a, trim_mult=trim_mult)
        ca = a[keep].mean(axis=0)
        d = (b - ca) @ normal
        coef = np.polyfit(b @ u, d, 1)
        seps.append(abs(float(np.polyval(coef, t_eval))))
    return float(np.mean(seps))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="dataset directory (holds roofkit.json)")
    ap.add_argument("--no-view", action="store_true",
                    help="skip the painted-walls viewer")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    o3d.utility.random.seed(0)
    rng = np.random.default_rng(0)

    points, colors = load_xyz_rgb(cfg["cloud_path"])
    if cfg["crop_min"] is None or cfg["crop_max"] is None:
        raise SystemExit("set crop_min/crop_max in roofkit.json first")
    points, mask = crop_box(points, cfg["crop_min"], cfg["crop_max"])
    colors = colors[mask]

    if cfg["level_tilt_deg"] is not None:
        points = level_cloud(points, up_from_tilt(cfg["level_tilt_deg"],
                                                  cfg["level_uphill_az_deg"]))
        print(f"leveled by {cfg['level_tilt_deg']} deg, uphill azimuth "
              f"{cfg['level_uphill_az_deg']} (from roofkit.json)")
    else:
        print("WARNING: no measured tilt in roofkit.json; verticality and "
              "span heights use unleveled Z")
    origin = points.min(axis=0)  # leveled frame, for relative printouts

    # --- vertical-surface extraction on a subsample ---
    sub = points
    if len(points) > RECON_SAMPLE:
        sub = points[rng.choice(len(points), RECON_SAMPLE, replace=False)]
    frac = len(sub) / len(points)
    s = median_nn_spacing(sub)
    print(f"cropped cloud {len(points):,} points; recon subsample "
          f"{len(sub):,} ({100 * frac:.0f}%), spacing {s:.4f} cu")

    # One covariance pass gives BOTH signals: the smallest-spread direction
    # is the normal (vertical test) and the eigenvalue ratio is planarity
    # (foliage test). A wall point must pass both; foliage has random
    # normals AND no sheet structure, so it fails both. Same two-signal
    # logic as the isolation stage, computed once.
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(sub)
    # max_nn must be large enough that the radius BINDS: hybrid search
    # returns the max_nn nearest within radius, so a small cap silently
    # shrinks the neighborhood back to confetti scale (found empirically:
    # max_nn=30 at this density is a ~3 cm ball whatever the radius says,
    # and roof points then leak through the vertical gate).
    cloud.estimate_covariances(o3d.geometry.KDTreeSearchParamHybrid(
        radius=NORMAL_RADIUS_MULT * s, max_nn=150))
    w, v = np.linalg.eigh(np.asarray(cloud.covariances))  # ascending
    total = w.sum(axis=1)
    ok = total > 1e-12
    score = np.full(len(sub), 1.0)
    score[ok] = w[ok, 0] / total[ok]
    normal_z = np.abs(v[:, 2, 0])  # z component of the smallest eigenvector
    keep = (score <= cfg["score_max"]) & \
           (normal_z <= np.cos(np.radians(MIN_WALL_TILT)))
    vertical = sub[keep]
    print(f"planar AND near-vertical points (score <= {cfg['score_max']}, "
          f"tilt >= {MIN_WALL_TILT} deg): {len(vertical):,} "
          f"({100 * len(vertical) / len(sub):.1f}% of subsample)")
    if len(vertical) < MIN_FACE_POINTS:
        raise SystemExit("almost no vertical surface reconstructed; no wall "
                         "is measurable from this cloud")

    band = cfg["band_mult"] * s
    walls = find_roof_planes(vertical, distance_threshold=band,
                             min_points=MIN_FACE_POINTS,
                             min_pitch=MIN_WALL_TILT, max_pitch=90.0,
                             max_planes=40)
    print(f"{len(walls)} wall planes peeled")

    # Split coplanar-but-disjoint segments (two collinear wall runs share a
    # plane but are different physical walls) into separate faces.
    faces = []
    for w in walls:
        pc = o3d.geometry.PointCloud()
        pc.points = o3d.utility.Vector3dVector(w["points"])
        labels = np.asarray(pc.cluster_dbscan(eps=20.0 * s, min_points=30))
        for lab in range(labels.max() + 1):
            seg = w["points"][labels == lab]
            if len(seg) < MIN_FACE_POINTS:
                continue
            normal, keep = fit_plane_trimmed(seg, trim_mult=cfg["trim_mult"])
            core = seg[keep]
            centroid = core.mean(axis=0)
            scatter = float(np.median(np.abs((core - centroid) @ normal)))
            face = {"points": core, "normal": normal,
                    "centroid": centroid, "scatter": scatter}
            ht = float(core[:, 2].max() - core[:, 2].min())
            if wall_length(face) < MIN_FACE_LEN or ht < MIN_FACE_HEIGHT:
                continue  # a wall has extent; vertical confetti does not
            faces.append(face)

    print(f"\n{len(faces)} wall faces (coplanar segments split):")
    print(f"{'face':>5} {'color':>8} {'az':>6} {'len cu':>7} {'ht cu':>6} "
          f"{'pts':>9} {'scatter':>8} {'tilt':>6}")
    for k, f in enumerate(faces):
        name = PALETTE[k % len(PALETTE)][0]
        ht = float(f["points"][:, 2].max() - f["points"][:, 2].min())
        print(f"{k:>5} {name:>8} {azimuth_degrees(f['normal']):>6.1f} "
              f"{wall_length(f):>7.2f} {ht:>6.2f} {len(f['points']):>9,} "
              f"{f['scatter']:>8.4f} {tilt_degrees(f['normal']):>6.1f}")

    # --- corners: intersections with real point support on both sides ---
    contact = CONTACT_MULT * s
    corners = {}      # (i, j) -> corner dict
    near_misses = []  # rejected pairs that had SOME support (the killers)
    for i in range(len(faces)):
        for j in range(i + 1, len(faces)):
            if strike_diff_deg(faces[i]["normal"],
                               faces[j]["normal"]) < MIN_STRIKE_DIFF:
                continue
            c, why = corner_between(faces[i], faces[j], contact)
            if c is not None:
                corners[(i, j)] = c
            else:
                near_misses.append((i, j, why))

    print(f"\n{len(corners)} validated corners "
          f"(contact radius {contact:.4f} cu):")
    print(f"{'faces':>7} {'dx':>7} {'dy':>7} {'plumb':>6} "
          f"{'contact pts':>13} {'zlo..zhi':>13}")
    for (i, j), c in corners.items():
        xy = line_at_z(c["p0"], c["d"],
                       (c["zlo"] + c["zhi"]) / 2.0) - origin
        print(f"{i:>3},{j:>3} {xy[0]:>7.2f} {xy[1]:>7.2f} {c['plumb']:>6.2f} "
              f"{c['n_a']:>6,}/{c['n_b']:<6,} "
              f"{c['zlo'] - origin[2]:>6.2f}..{c['zhi'] - origin[2]:.2f}")
    if near_misses:
        print("rejected face pairs (strike angle passed, corner did not):")
        for i, j, why in near_misses:
            print(f"  faces {i},{j}: {why}")

    candidates = []

    # --- instrument 1: corner-to-corner span along one wall face ---
    for f in range(len(faces)):
        mine = [(pair, c) for pair, c in corners.items() if f in pair]
        for a in range(len(mine)):
            for b in range(a + 1, len(mine)):
                (pa, ca), (pb, cb) = mine[a], mine[b]
                ra = pa[0] if pa[1] == f else pa[1]  # return faces
                rb = pb[0] if pb[1] == f else pb[1]
                if ra == rb:
                    continue
                z_eval = float(np.median(faces[f]["points"][:, 2]))
                span = float(np.linalg.norm(
                    line_at_z(ca["p0"], ca["d"], z_eval)
                    - line_at_z(cb["p0"], cb["d"], z_eval)))
                if span < MIN_SPAN:
                    continue
                sens = max(abs(float(np.linalg.norm(
                    line_at_z(ca["p0"], ca["d"], z_eval + dz)
                    - line_at_z(cb["p0"], cb["d"], z_eval + dz))) - span)
                    for dz in (-1.0, 1.0))
                halves = []
                for off in (0, 1):
                    hs = span_from_points(
                        faces[f]["points"][off::2],
                        faces[ra]["points"][off::2],
                        faces[rb]["points"][off::2],
                        cfg["trim_mult"], z_eval)
                    if hs is not None:
                        halves.append(hs)
                rep = abs(halves[0] - halves[1]) if len(halves) == 2 else None
                az = azimuth_degrees(faces[f]["normal"])
                candidates.append({
                    "kind": "corner span", "span": span, "sens": sens,
                    "rep": rep,
                    "support": min(ca["n_a"], ca["n_b"], cb["n_a"], cb["n_b"]),
                    "desc": f"along wall {f} (az {az:.0f}), corners with "
                            f"faces {ra} and {rb}"})

    # --- instrument 2: wing width between parallel wall planes ---
    # No corner needed anywhere: the span is the perpendicular separation
    # of a wing's two side-wall planes, taped across the wing's END face.
    for i in range(len(faces)):
        for j in range(i + 1, len(faces)):
            ni, nj = faces[i]["normal"], faces[j]["normal"]
            if strike_diff_deg(ni, nj) > PARALLEL_STRIKE_MAX:
                continue
            u = np.cross(ni, [0.0, 0.0, 1.0])
            u = u / np.linalg.norm(u)
            ti = faces[i]["points"] @ u
            tj = faces[j]["points"] @ u
            lo, hi = max(ti.min(), tj.min()), min(ti.max(), tj.max())
            if hi - lo < MIN_OVERLAP:
                continue  # the faces do not bound the same stretch of wing
            pi, pj = faces[i]["points"], faces[j]["points"]
            mid = (lo + hi) / 2.0
            sep_mid = sep_at(pi, pj, cfg["trim_mult"], mid, u)
            if not SEP_MIN <= sep_mid <= SEP_MAX:
                continue
            ends = [sep_at(pi, pj, cfg["trim_mult"], t, u) for t in (lo, hi)]
            sens = max(abs(e - sep_mid) for e in ends)
            halves = [sep_at(pi[off::2], pj[off::2], cfg["trim_mult"],
                             mid, u) for off in (0, 1)]
            azi = azimuth_degrees(ni)
            loc = ((faces[i]["centroid"] + faces[j]["centroid"]) / 2.0
                   - origin)
            # NOTE: same-facing (facade setback) and opposite-facing (wing
            # width) pairs cannot be told apart here: RANSAC normal signs
            # are arbitrary on vertical planes. Only the person who knows
            # the building can say which this is and whether it is
            # tapeable flat across a connecting face.
            candidates.append({
                "kind": "parallel walls", "span": sep_mid, "sens": sens,
                "rep": abs(halves[0] - halves[1]),
                "support": min(len(pi), len(pj)),
                "desc": f"faces {i},{j} (az {azi:.0f} strike), overlap "
                        f"{hi - lo:.1f} cu, sep at overlap ends "
                        f"{ends[0]:.3f}/{ends[1]:.3f}, near "
                        f"dx={loc[0]:.0f} dy={loc[1]:.0f}"})

    if not candidates:
        print("\nNO measurable span: no wall face has two validated corners "
              "and no parallel wall pair bounds a wing.")
        return

    # Predicted error if this span were taped: split-half instrument noise
    # plus the tape's centimeter, in quadrature, over the length. Treats
    # 1 cu ~ 1 m for the tape term only, which is fine for RANKING (GPS
    # scale is right to a few percent even though untested).
    for e in candidates:
        rep = e["rep"] if e["rep"] is not None else e["sens"]
        e["lin_pct"] = 100.0 * float(np.hypot(rep, TAPE_ERR)) / e["span"]
        e["area_pct"] = 2.0 * e["lin_pct"]
    candidates.sort(key=lambda e: e["lin_pct"])

    print(f"\ncandidate spans, ranked by predicted error "
          f"(tape term {TAPE_ERR} m):")
    print(f"{'rank':>4} {'kind':>12} {'span cu':>8} {'rep cu':>7} "
          f"{'pos-sens':>8} {'support':>8} {'lin %':>6} {'area %':>7}  where")
    for r, e in enumerate(candidates, 1):
        rep = f"{e['rep']:.4f}" if e["rep"] is not None else "n/a"
        print(f"{r:>4} {e['kind']:>12} {e['span']:>8.3f} {rep:>7} "
              f"{e['sens']:>8.4f} {e['support']:>8,} {e['lin_pct']:>6.2f} "
              f"{e['area_pct']:>7.2f}  {e['desc']}")
    print("\nnotes: a 'parallel walls' span is taped flat across whichever "
          "face CONNECTS the two planes. If that face is square to them, "
          "hook the two corner arrises and the skew error is sec(angle), "
          "negligible; if it is oblique, report which faces the tape ran "
          "between and the skew is corrected with the cloud-measured "
          "angle, not assumed. Watch corner TRIM standing proud of the "
          "siding plane: it adds its thickness to the tape reading, so "
          "note the construction at the corners you hook. pos-sens is the "
          "span's drift across the overlap; if it is large, say exactly "
          "where the tape went.")

    if not args.no_view:
        geoms = []
        view = points
        vcol = colors
        if len(view) > MAX_VIEW_POINTS:
            idx = rng.choice(len(view), MAX_VIEW_POINTS, replace=False)
            view, vcol = view[idx], vcol[idx]
        ctx = o3d.geometry.PointCloud()
        ctx.points = o3d.utility.Vector3dVector(view)
        ctx.colors = o3d.utility.Vector3dVector(vcol * 0.55)  # dimmed
        geoms.append(ctx)
        for k, f in enumerate(faces):
            pc = o3d.geometry.PointCloud()
            pc.points = o3d.utility.Vector3dVector(f["points"])
            pc.paint_uniform_color(PALETTE[k % len(PALETTE)][1])
            geoms.append(pc)
        for c in corners.values():
            seg = o3d.geometry.LineSet()
            seg.points = o3d.utility.Vector3dVector(
                [line_at_z(c["p0"], c["d"], c["zlo"] - 0.5),
                 line_at_z(c["p0"], c["d"], c["zhi"] + 0.5)])
            seg.lines = o3d.utility.Vector2iVector([[0, 1]])
            seg.paint_uniform_color((1.0, 0.0, 0.0))
            geoms.append(seg)
        print("\nviewer: walls painted by face color, corner lines in red, "
              "context dimmed. Q closes.")
        o3d.visualization.draw_geometries(
            geoms, window_name="wall recon: painted faces + corner lines")


if __name__ == "__main__":
    main()
