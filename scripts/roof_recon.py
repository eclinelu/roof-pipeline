# Roof-derived scale reconnaissance BEFORE the tape (2026-07-14): walls
# have no coverage on big_house, so the scale span comes from the roof,
# a logged EXCEPTION for this dataset. Same recon-before-tape principle
# as wall_recon.py: derive every candidate span from fitted geometry,
# rank by predicted error, and only then choose where the tape goes.
#
#   python scripts/roof_recon.py C:\odm\datasets\big_house [--no-view]
#
# Bias and noise are NEVER folded together (decision 2026-07-14):
# split-half repeatability cannot see edge erosion, because both halves
# are eroded identically. Eave positions therefore carry a two-cloud
# bracket: tight (filtered roof points, lower bound) vs loose (raw crop
# gated only by distance to the plane plus an in-plane window, upper
# bound). Output is lower/upper/delta, never an average.
import argparse
import numpy as np
import open3d as o3d
from dataset_config import load_config
from recon_common import discover_facets
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box
from roofkit.stats import median_nn_spacing
from roofkit.segment import level_cloud, fit_plane_trimmed
from roofkit.measure import (plane_intersection, azimuth_degrees,
                             up_from_tilt, eave_line, line_extent,
                             line_pair_span)

MIN_CONTACT = 200        # points per side to validate a line (sample size)
RIDGE_FRAC = 0.8         # contact-height fraction: >= on BOTH sides = ridge
VALLEY_FRAC = 0.2        # <= on both sides = valley (unitless, scale-free)
MIN_EDGE_SUPPORT = 50    # points in an eave's supporting bin (sample size)
PAIR_TOL_DEG = 2.0       # lines within this angle count as parallel; an
                         # angle, scale-free (spec: divergence reported)
PLANE_TOL_DEG = 2.0      # facet planes within this angle are parallel
MIN_SPAN = 2.0           # cu; shorter spans dilute nothing (scale-DEPENDENT)
SEP_MIN, SEP_MAX = 0.3, 30.0  # cu; plausible plane-pair window (scale-DEP.)
LOOSE_MARGIN_DOWN = 120.0 # x spacing past the tight eave the loose window
                         # extends downslope (readmits the eroded strip).
                         # Must clear EAVE_FLAG_CU (0.4) so a real overhang
                         # or a contaminated blowout can reach the flag
                         # instead of being clipped: 120 x spacing ~ 0.62 cu
                         # at big_house density, comfortably past 0.4.
LOOSE_MARGIN_ALONG = 10.0  # x spacing beyond the tight along-eave extent
EAVE_FLAG_CU = 0.4       # cu; a bracket wider than this is loose-set
                         # CONTAMINATION, not erosion (scale-DEPENDENT:
                         # real overhang+fascia geometry is ~0.1-0.3 m and
                         # 1 cu ~ 1 m within GPS scale error; flag only)
TAPE_ERR = 0.01          # m; tape accuracy. RANKING term only: treats
                         # 1 cu ~ 1 m exactly as wall_recon.py documents


def contact_points(facet, p0, d, radius):
    """A facet's points within radius of a line (the ridge_line contact
    idea, kept here because the recon needs the points themselves)."""
    rel = facet["points"] - p0
    along = rel @ d
    radial = np.linalg.norm(rel - np.outer(along, d), axis=1)
    return facet["points"][radial <= radius]


def intersection_lines(facets, contact_dist, spacing):
    """Every contact-validated plane-plane intersection line: ridges,
    valleys, junctions. Direction re-measured from the contact points
    (real geometry at the line, not extrapolated fits). Each line
    carries per-end extent sensitivity: the extent re-read with the
    contact radius halved and doubled, because the ENDS live in the
    eroded zone and must wear their uncertainty visibly."""
    lines = []
    for i in range(len(facets)):
        for j in range(i + 1, len(facets)):
            fi, fj = facets[i], facets[j]
            inter = plane_intersection(fi["normal"], fi["points"].mean(axis=0),
                                       fj["normal"], fj["points"].mean(axis=0))
            if inter is None:
                continue
            p0, d = inter
            touch, fracs = [], []
            for f in (fi, fj):
                t = contact_points(f, p0, d, contact_dist)
                if len(t) < MIN_CONTACT:
                    touch = None
                    break
                lo, hi = np.percentile(f["points"][:, 2], [1.0, 99.0])
                fracs.append(float(np.clip(
                    (np.median(t[:, 2]) - lo) / max(hi - lo, 1e-12), 0, 1)))
                touch.append(t)
            if touch is None:
                continue
            contact = np.vstack(touch)
            _, _, vt = np.linalg.svd(contact - contact.mean(axis=0),
                                     full_matrices=False)
            v = vt[0]
            if v @ d < 0:
                v = -v
            v = v / np.linalg.norm(v)
            c0 = contact.mean(axis=0)
            ext = line_extent(contact, c0, v, spacing)
            # per-end sensitivity: how far each end moves when the
            # contact radius changes 2x either way (bias bound, cu)
            end_bias = [0.0, 0.0]
            for mult in (0.5, 2.0):
                alt = np.vstack([contact_points(f, p0, d, mult * contact_dist)
                                 for f in (fi, fj)])
                if len(alt) < 2 * MIN_CONTACT:
                    continue
                e2 = line_extent(alt, c0, v, spacing)
                end_bias[0] = max(end_bias[0], abs(e2["t_lo"] - ext["t_lo"]))
                end_bias[1] = max(end_bias[1], abs(e2["t_hi"] - ext["t_hi"]))
            kind = ("ridge" if min(fracs) >= RIDGE_FRAC else
                    "valley" if max(fracs) <= VALLEY_FRAC else "junction")
            az = float(np.degrees(np.arctan2(v[0], v[1])) % 360.0)
            if az >= 180.0:
                az -= 180.0
            lines.append({"i": i, "j": j, "kind": kind, "p0": c0, "d": v,
                          "azimuth_deg": az, "fracs": fracs,
                          "n_contact": len(contact), "extent": ext,
                          "end_bias": end_bias, "contacts": contact})
    return lines


def loose_set(raw_points, facet, tight_eave, band, spacing):
    """The loose point set for one facet's bracket: raw cropped points
    gated by (a) perpendicular distance to the TIGHT-fit plane and (b)
    an in-plane window around the tight facet, extended downslope past
    the tight eave. Gate (b) exists because an extended roof plane
    eventually slices terrain and canopy; without it the loose set is
    unbounded contamination (spec: in-plane region gate)."""
    n = facet["normal"] / np.linalg.norm(facet["normal"])
    c = facet["points"].mean(axis=0)
    d_perp = np.abs((raw_points - c) @ n)
    near = raw_points[d_perp <= band]
    d, w = tight_eave["d"], tight_eave["w"]
    a = (near - c) @ d
    t = (near - c) @ w
    a_t = (facet["points"] - c) @ d
    t_t = (facet["points"] - c) @ w
    keep = ((a >= a_t.min() - LOOSE_MARGIN_ALONG * spacing) &
            (a <= a_t.max() + LOOSE_MARGIN_ALONG * spacing) &
            (t >= t_t.min()) &
            (t <= tight_eave["t_edge"] + LOOSE_MARGIN_DOWN * spacing))
    return near[keep]


def bracket_eaves(facets, raw_points, band, spacing):
    """Each facet's eave, twice: tight (lower bound) and loose (upper).
    The plane and the coordinate origin ALWAYS come from the tight set,
    so the two t_edge values share one axis and their difference is the
    bracket delta. Split-half repeatability of the tight reading rides
    along so the table shows noise and bias side by side."""
    # Invariant (decision 2026-07-15): the loose window must stay wider
    # than the contamination flag. Facets read contaminated ONLY because
    # the window clips them above EAVE_FLAG_CU; if LOOSE_MARGIN_DOWN x
    # spacing ever narrows below the flag, those same contaminated eaves
    # get clipped UNDER it and misread as clean, silently admitting a bad
    # scale candidate. Guard it, do not trust the constants to stay sane.
    window_margin = LOOSE_MARGIN_DOWN * spacing
    assert window_margin > EAVE_FLAG_CU, (
        f"loose window {window_margin:.3f} cu must exceed the contamination "
        f"flag {EAVE_FLAG_CU} cu; raise LOOSE_MARGIN_DOWN")
    brackets = []
    for k, f in enumerate(facets):
        c = f["points"].mean(axis=0)
        tight = eave_line(f["points"], f["normal"], spacing, origin=c)
        if tight is None or tight["n_edge"] < MIN_EDGE_SUPPORT:
            brackets.append(None)
            continue
        # Addition A (decision 2026-07-15): make the superset true by
        # CONSTRUCTION, not by assumption. delta >= 0 only holds if every
        # tight point is also a loose point; the distance gate does not
        # guarantee that, so union the tight core in. Tight points are
        # legitimately near-plane, so the union does not corrupt loose's
        # meaning; if tight is already inside the gate it is a no-op.
        loose_pts = np.vstack([loose_set(raw_points, f, tight, band, spacing),
                               f["points"]])
        # Shared absolute floor (decision 2026-07-15): read the loose set
        # against 0.5 * the TIGHT central density, not its own, so the
        # denser loose cloud cannot raise its cutoff and read inboard.
        loose = eave_line(loose_pts, f["normal"], spacing, origin=c,
                          min_count=0.5 * tight["central"])
        halves = []
        for off in (0, 1):
            half_pts = f["points"][off::2]
            normal, keep = fit_plane_trimmed(half_pts, trim_mult=3.0)
            h = eave_line(half_pts[keep], normal, spacing, origin=c)
            if h is not None:
                halves.append(h["t_edge"])
        rep = abs(halves[0] - halves[1]) if len(halves) == 2 else None
        delta = (loose["t_edge"] - tight["t_edge"]) if loose else None
        flagged = delta is not None and delta > EAVE_FLAG_CU
        brackets.append({"facet": k, "tight": tight, "loose": loose,
                         "rep": rep, "delta": delta, "flagged": flagged,
                         "n_loose": len(loose_pts)})
    return brackets


def _where(p, origin):
    r = p - origin
    return f"dx={r[0]:.1f} dy={r[1]:.1f} z={r[2]:.1f}"


def _overlap_window(line_a, pts_b, p0a, da):
    """Evaluation window along line A: the overlap of A's supported
    extent and B's support projected onto A. The span gets read where
    BOTH lines actually have data under them."""
    ta = line_a
    tb = (pts_b - p0a) @ da
    lo = max(ta["t_lo"], float(tb.min()))
    hi = min(ta["t_hi"], float(tb.max()))
    return (lo, hi) if hi > lo else None


def enumerate_candidates(facets, lines, brackets, spacing, origin):
    cands = []
    # class 1: parallel facet-plane separations (interior fits, no edges)
    for i in range(len(facets)):
        for j in range(i + 1, len(facets)):
            ni = facets[i]["normal"] / np.linalg.norm(facets[i]["normal"])
            nj = facets[j]["normal"] / np.linalg.norm(facets[j]["normal"])
            if ni[2] < 0:
                ni = -ni
            if nj[2] < 0:
                nj = -nj
            ang = np.degrees(np.arccos(np.clip(ni @ nj, -1.0, 1.0)))
            if ang > PLANE_TOL_DEG:
                continue
            ci = facets[i]["points"].mean(axis=0)
            sep_ij = np.abs((facets[j]["points"] - ci) @ ni).mean()
            cj = facets[j]["points"].mean(axis=0)
            sep_ji = np.abs((facets[i]["points"] - cj) @ nj).mean()
            sep = float((sep_ij + sep_ji) / 2.0)
            if not SEP_MIN <= sep <= SEP_MAX:
                continue
            halves = []
            for off in (0, 1):
                pi = facets[i]["points"][off::2]
                pj = facets[j]["points"][off::2]
                n1, k1 = fit_plane_trimmed(pi, trim_mult=3.0)
                if n1[2] < 0:
                    n1 = -n1
                halves.append(float(np.abs((pj - pi[k1].mean(axis=0)) @ n1)
                                    .mean()))
            cands.append({
                "cand_id": f"planes:{i}|{j}", "kind": "plane pair",
                "span": sep, "rep": abs(halves[0] - halves[1]), "bias": 0.0,
                "where": _where((ci + cj) / 2.0, origin), "dz": None,
                "tape_plan": "perpendicular offset between two parallel "
                             "roof planes; tapeable only if a step or "
                             "junction physically joins them, judge on "
                             "site"})
    # class 2: parallel derived-line pairs. Pool intersection lines and
    # unflagged eaves; every pair within PAIR_TOL_DEG is a candidate.
    pool = []
    for L in lines:
        pool.append({"tag": f"{L['kind'][0]}{L['i']},{L['j']}", "p0": L["p0"],
                     "d": L["d"], "sup": L["contacts"], "ext": L["extent"],
                     "bias": 0.0, "eave": False, "line": L})
    for b in brackets:
        if b is None or b["flagged"] or b["delta"] is None:
            continue
        f = facets[b["facet"]]
        t = (f["points"] - f["points"].mean(axis=0)) @ b["tight"]["d"]
        ext = {"t_lo": float(t.min()), "t_hi": float(t.max())}
        pool.append({"tag": f"e{b['facet']}", "p0": b["tight"]["p0"],
                     "d": b["tight"]["d"], "sup": f["points"], "ext": ext,
                     "bias": b["delta"], "eave": True,
                     "facet": b["facet"], "rep_e": b["rep"]})
    for a in range(len(pool)):
        for c in range(a + 1, len(pool)):
            A, B = pool[a], pool[c]
            fold = abs(A["d"] @ B["d"])
            ang = np.degrees(np.arccos(np.clip(fold, 0.0, 1.0)))
            if ang > PAIR_TOL_DEG:
                continue
            # extent window of A, intersected with B's support footprint
            win = _overlap_window(A["ext"], B["sup"], A["p0"], A["d"])
            r = line_pair_span(A["p0"], A["d"], B["p0"], B["d"],
                               *(win if win else (A["ext"]["t_lo"],
                                                  A["ext"]["t_hi"])))
            if r["span"] < MIN_SPAN:
                continue
            bias = A["bias"] + B["bias"]  # once per eave involved
            both_eave = A["eave"] and B["eave"]
            dz = abs(float(A["p0"][2] - B["p0"][2])) if both_eave else None
            reps = [x["rep_e"] for x in (A, B)
                    if x["eave"] and x.get("rep_e") is not None]
            rep = float(np.hypot(*reps)) if len(reps) == 2 else (
                reps[0] if reps else r["sens"])
            plan = ("ground: plumb drops from both drip edges, tape the "
                    "horizontal" if both_eave else
                    "on roof: hook the drip edge, run up the slope"
                    if A["eave"] or B["eave"] else
                    "on roof: between the two lines")
            cands.append({
                "cand_id": f"lines:{A['tag']}-{B['tag']}",
                "kind": "line pair", "span": float(r["span"]), "rep": rep,
                "bias": float(bias), "dz": dz,
                "where": _where((A["p0"] + B["p0"]) / 2.0, origin),
                "tape_plan": plan + f" (divergence {r['divergence_deg']:.2f} "
                                    f"deg, pos-sens {r['sens']:.3f} cu)"})
    # class 3: intersection-line lengths (fallback, endpoint bias visible)
    for L in lines:
        length = L["extent"]["length"]
        if length < MIN_SPAN:
            continue
        cands.append({
            "cand_id": f"length:{L['kind'][0]}{L['i']},{L['j']}",
            "kind": f"{L['kind']} length", "span": float(length),
            "rep": None, "bias": float(sum(L["end_bias"])), "dz": None,
            "where": _where(L["p0"], origin),
            "tape_plan": "on roof, along the line; BOTH ends are eroded "
                         "edge zone, bias is one-sided (reads short)"})
    return cands


def rank_and_print(cands):
    for e in cands:
        rep = e["rep"] if e["rep"] is not None else 0.0
        noise = float(np.hypot(rep, TAPE_ERR))
        e["noise_pct"] = 100.0 * noise / e["span"]
        e["bias_pct"] = 100.0 * e["bias"] / e["span"]
        e["lin_pct"] = e["noise_pct"] + e["bias_pct"]
        e["area_pct"] = 2.0 * e["lin_pct"]
    cands.sort(key=lambda e: e["lin_pct"])
    print(f"\ncandidate scale spans, ranked by predicted linear error "
          f"(noise and bias SHOWN SPLIT, tape term {TAPE_ERR} m):")
    print(f"{'rank':>4} {'id':>18} {'kind':>14} {'span cu':>8} "
          f"{'noise %':>8} {'bias %':>7} {'lin %':>6} {'area %':>7}  "
          f"where / tape plan")
    for r, e in enumerate(cands, 1):
        print(f"{r:>4} {e['cand_id']:>18} {e['kind']:>14} {e['span']:>8.3f} "
              f"{e['noise_pct']:>8.3f} {e['bias_pct']:>7.3f} "
              f"{e['lin_pct']:>6.2f} {e['area_pct']:>7.2f}  "
              f"{e['where']}; {e['tape_plan']}"
              + (f"; dz={e['dz']:.2f} cu" if e["dz"] is not None else ""))
    print("\nnotes: bias is a BOUND with known direction, not noise; a "
          "candidate with tiny noise and fat bias is not better than the "
          "reverse. Eave-based spans inherit the bracket delta once per "
          "eave. Physical access is Emmett's judgment, from the where "
          "column, not the script's.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="dataset directory (holds roofkit.json)")
    ap.add_argument("--no-view", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.dataset)

    roof = np.load(cfg["roof_path"])
    raw, _ = load_xyz_rgb(cfg["cloud_path"])
    if cfg["crop_min"] is None or cfg["crop_max"] is None:
        raise SystemExit("set crop_min/crop_max in roofkit.json first")
    raw, _ = crop_box(raw, cfg["crop_min"], cfg["crop_max"])
    if cfg["level_tilt_deg"] is None:
        raise SystemExit("no measured tilt in roofkit.json; run measure_roof "
                         "first, the recon needs the leveled frame")
    up = up_from_tilt(cfg["level_tilt_deg"], cfg["level_uphill_az_deg"])
    roof = level_cloud(roof, up)
    raw = level_cloud(raw, up)
    print(f"leveled both clouds by {cfg['level_tilt_deg']} deg, uphill az "
          f"{cfg['level_uphill_az_deg']} (roofkit.json)")
    origin = roof.min(axis=0)  # for relative dx/dy/z printouts

    facets, band, s = discover_facets(roof, cfg)
    # Vanish guard (decision 2026-07-15): once a dataset's facet count is
    # verified, a run that finds fewer means RANSAC dropped a real facet,
    # which would silently corrupt every downstream number. Fail loudly.
    if cfg["expected_facets"] is not None and len(facets) != cfg["expected_facets"]:
        raise SystemExit(f"expected {cfg['expected_facets']} facets, found "
                         f"{len(facets)}: a facet vanished or split. Recon "
                         f"aborted; investigate before trusting any output.")
    print(f"{len(roof):,} roof points, {len(raw):,} raw crop points, "
          f"spacing {s:.4f} cu, band {band:.4f} cu, {len(facets)} facets")
    print(f"\n{'facet':>5} {'points':>10} {'pitch':>7} {'azimuth':>8}")
    for k, f in enumerate(facets):
        print(f"{k:>5} {len(f['points']):>10,} {f['pitch']:>7.2f} "
              f"{azimuth_degrees(f['normal']):>8.1f}")

    contact_dist = cfg["ridge_contact_mult"] * s
    lines = intersection_lines(facets, contact_dist, s)
    print(f"\n{len(lines)} contact-validated intersection lines "
          f"(contact {contact_dist:.4f} cu, min {MIN_CONTACT}/side):")
    print(f"{'facets':>7} {'kind':>9} {'az':>7} {'length cu':>10} "
          f"{'end bias cu':>12} {'contacts':>9} {'fracs':>11}")
    for L in lines:
        print(f"{L['i']:>3},{L['j']:>3} {L['kind']:>9} "
              f"{L['azimuth_deg']:>7.1f} {L['extent']['length']:>10.3f} "
              f"{L['end_bias'][0]:>5.3f}/{L['end_bias'][1]:<5.3f} "
              f"{L['n_contact']:>9,} "
              f"{L['fracs'][0]:>5.2f}/{L['fracs'][1]:<5.2f}")

    brackets = bracket_eaves(facets, raw, band, s)
    print(f"\neave brackets (tight=filtered lower bound, loose=raw-crop "
          f"upper bound, delta=loose-tight; NEVER averaged):")
    print(f"{'facet':>5} {'az':>7} {'rep cu':>8} {'delta cu':>9} "
          f"{'loose pts':>10}  note")
    for b in brackets:
        if b is None:
            continue
        note = ("CONTAMINATED loose set (bracket wider than "
                f"{EAVE_FLAG_CU} cu): excluded from scale candidates"
                if b["flagged"] else "ok")
        rep = f"{b['rep']:.4f}" if b["rep"] is not None else "n/a"
        delta = f"{b['delta']:.3f}" if b["delta"] is not None else "n/a"
        print(f"{b['facet']:>5} {b['tight']['azimuth_deg']:>7.1f} {rep:>8} "
              f"{delta:>9} {b['n_loose']:>10,}  {note}")
    print("note: tight, loose, and a physical tape can be three different "
          "edges (shingle overhang, fascia, wall line); a bracket gap may "
          "be geometry, not erosion. Field notes must record which edge "
          "the tape hooked.")

    cands = enumerate_candidates(facets, lines, brackets, s, origin)
    if not cands:
        print("\nNO candidate span survived. The honest outcome per the "
              "spec: report it, do not paper over it.")
        return
    rank_and_print(cands)

    if not args.no_view:
        geoms = []
        view = roof
        rng = np.random.default_rng(0)
        if len(view) > 1_500_000:
            view = view[rng.choice(len(view), 1_500_000, replace=False)]
        pc = o3d.geometry.PointCloud()
        pc.points = o3d.utility.Vector3dVector(view)
        pc.paint_uniform_color((0.45, 0.45, 0.45))
        geoms.append(pc)
        for L in lines:  # intersection lines in red
            seg = o3d.geometry.LineSet()
            a = L["p0"] + L["extent"]["t_lo"] * L["d"]
            b = L["p0"] + L["extent"]["t_hi"] * L["d"]
            seg.points = o3d.utility.Vector3dVector([a, b])
            seg.lines = o3d.utility.Vector2iVector([[0, 1]])
            seg.paint_uniform_color((1.0, 0.0, 0.0))
            geoms.append(seg)
        for b in brackets:  # tight eaves green, loose eaves yellow
            if b is None:
                continue
            f = facets[b["facet"]]
            c = f["points"].mean(axis=0)
            t = (f["points"] - c) @ b["tight"]["d"]
            for key, col in (("tight", (0.0, 0.8, 0.2)),
                             ("loose", (0.95, 0.85, 0.1))):
                e = b[key]
                if e is None:
                    continue
                seg = o3d.geometry.LineSet()
                seg.points = o3d.utility.Vector3dVector(
                    [e["p0"] + t.min() * e["d"], e["p0"] + t.max() * e["d"]])
                seg.lines = o3d.utility.Vector2iVector([[0, 1]])
                seg.paint_uniform_color(col)
                geoms.append(seg)
        print("\nviewer: intersection lines red, tight eaves green, loose "
              "eaves yellow. A wide green-to-yellow gap IS the bracket. "
              "Q closes.")
        o3d.visualization.draw_geometries(
            geoms, window_name="roof recon: derived lines and brackets")


if __name__ == "__main__":
    main()
