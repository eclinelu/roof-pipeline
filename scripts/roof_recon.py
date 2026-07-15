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
    return


if __name__ == "__main__":
    main()
