# Task 7A: MEASUREMENT ONLY. Changes no state, adopts no threshold, decides
# nothing. Every question here feeds a decision that comes later.
#
#   .venv/Scripts/python.exe -u scripts/probe_task7a.py C:/odm/datasets/big_house
#
# Writes reports/big_house/task7a-<date>.json  (standing rule R2), plus
#        reports/big_house/task7a-holes-<date>.png for A5.
#
# A1  Pitch of EVERY plane peeled across ALL blobs, before any pitch filtering.
#     Is there an empty band between real low-slope roof and artifact?
# A2  Does lowering min_pitch change MAIN facet discovery? This is the one that
#     could propagate to the frozen comparison.
# A3  What is min_pitch actually protecting against, given that ground is
#     removed upstream and walls are near-vertical?
# A4  How much plan area inside the footprint is VERTICAL surface, which no
#     roof facet can ever explain? Restate coverage against explainable area.
# A5  Why does the coverage denominator collapse 202 -> 141 -> 96 -> 72 cu^2
#     across erosion rings? Test the sub-threshold-holes hypothesis.
#
# The canonical state is READ, never rebuilt. Where a question needs a fit that
# the canonical state cannot answer (A1's fuller peel sweep, A2's alternative
# min_pitch values), that fit is run into a PROBE file and never written back.
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import (binary_fill_holes, distance_transform_edt, label)

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar, leveled_points      # noqa: E402
from dataset_config import load_config                            # noqa: E402
from recon_common import discover_facets                          # noqa: E402
from roofkit import coverage as cov                               # noqa: E402
from roofkit.stats import median_nn_spacing                       # noqa: E402

REPO = Path(__file__).resolve().parents[1]
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
PITCH_WINDOW = (10.0, 60.0)


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    return o


def fhex(x):
    return float(x).hex()


def gap_table(values, upto):
    """EVERY empty interval between consecutive values below `upto`, widest
    first, plus where the current threshold sits.

    This is how the project decides whether a threshold is defensible: a value
    inside a gap can move anywhere in that gap without changing one decision,
    so it cannot have been tuned to the answer. Reporting only the single
    widest gap hides whether the threshold is actually IN it, which is the
    thing that matters. The size floor's bands, for comparison, were 15.9x and
    9.0x wide."""
    v = np.sort(np.asarray([x for x in values if x <= upto], float))
    if len(v) < 2:
        return dict(values_below=[round(float(x), 3) for x in v], gaps=[])
    gaps = [dict(lo=round(float(v[k]), 3), hi=round(float(v[k + 1]), 3),
                 width_deg=round(float(v[k + 1] - v[k]), 3))
            for k in range(len(v) - 1)]
    return dict(values_below=[round(float(x), 3) for x in v],
                gaps=sorted(gaps, key=lambda r: -r["width_deg"]))


def gap_containing(values, floor):
    """The interval the current threshold actually sits in, and how much slack
    it has on each side before a plane changes side."""
    v = np.sort(np.asarray(values, float))
    below, above = v[v < floor], v[v >= floor]
    if not len(below) or not len(above):
        return dict(floor=floor, in_gap=False,
                    note="no plane on one side of the floor")
    lo, hi = float(below[-1]), float(above[0])
    return dict(floor=floor, nearest_below=round(lo, 3),
                nearest_above=round(hi, 3),
                gap_width_deg=round(hi - lo, 3),
                slack_down_deg=round(floor - lo, 3),
                slack_up_deg=round(hi - floor, 3), in_gap=True)


# ---------------------------------------------------------------------------
# A1: the pitch distribution of every peeled plane
# ---------------------------------------------------------------------------
def a1_pitch_distribution(doc, points, cfg, band, spacing, bar, dist, blobs_raw,
                          out, stamp):
    # (a) The canonical run's own peels: authoritative, but TRUNCATED twice.
    canon = []
    for e in doc["recovery_log"]:
        for p in e.get("peels", []):
            if "n_inliers" in p:
                canon.append(dict(blob=e["blob"], peel=p["peel"],
                                  n=p["n_inliers"], pitch=p["pitch_deg"],
                                  kept=p["kept_by_pitch"]))

    # (b) A DEEPER sweep, so the distribution is not an artefact of where the
    # canonical run happened to stop. The point floor is dropped to the old
    # stability floor and the per-blob plane budget is raised, so RANSAC keeps
    # peeling well past the point the canonical run quits. This is a probe: it
    # writes no state and the canonical facets are untouched.
    deep_log = []
    cov.recover_facets(points, blobs_raw, None, dist, band, spacing, bar,
                       alpha_mult=cfg["alpha_mult"], probability=1.0,
                       size_floor=300, min_points_hard=None,
                       min_area_hard=None, max_planes_per_blob=12,
                       log=deep_log)
    deep = []
    for e in deep_log:
        for p in e.get("peels", []):
            if "n_inliers" in p:
                deep.append(dict(blob=e["blob"], peel=p["peel"],
                                 n=p["n_inliers"], pitch=p["pitch_deg"],
                                 kept=p["kept_by_pitch"]))

    def summarise(rows, label):
        pit = [r["pitch"] for r in rows]
        below = sorted([r for r in rows if r["pitch"] < PITCH_WINDOW[0]],
                       key=lambda r: -r["n"])
        inside = [r for r in rows if PITCH_WINDOW[0] <= r["pitch"] <= PITCH_WINDOW[1]]
        above = sorted([r for r in rows if r["pitch"] > PITCH_WINDOW[1]],
                       key=lambda r: -r["n"])
        # 2-degree histogram over the whole range, so the shape is visible
        # without reading 60 individual numbers.
        edges = np.arange(0, 92, 2.0)
        h, _ = np.histogram(pit, bins=edges)
        hist = [dict(deg_lo=float(edges[i]), deg_hi=float(edges[i + 1]),
                     n_planes=int(h[i])) for i in range(len(h)) if h[i]]
        return dict(
            label=label, n_planes=len(rows),
            n_below_min_pitch=len(below), n_inside_window=len(inside),
            n_above_max_pitch=len(above),
            histogram_2deg=hist,
            all_pitches_sorted=sorted(round(p, 3) for p in pit),
            below_min_pitch=below, above_max_pitch=above,
            # THE BAND QUESTION. Every gap below the window, widest first, plus
            # the interval min_pitch=10 actually sits in.
            gaps_below_window=gap_table(pit, PITCH_WINDOW[0] + 6.0),
            where_min_pitch_sits=gap_containing(pit, PITCH_WINDOW[0]),
            where_max_pitch_sits=gap_containing(pit, PITCH_WINDOW[1]))

    # (c) MAIN discovery's own peels. Worth having separately because the pitch
    # window does NOT affect peeling: find_roof_planes removes each peeled
    # plane's points whether it keeps the plane or not, so one run enumerates
    # every plane main discovery ever proposes, at any min_pitch.
    from roofkit.segment import find_roof_planes
    from roofkit.stats import median_nn_spacing as _mnn
    rng = np.random.default_rng(0)
    import open3d as o3d
    o3d.utility.random.seed(0)
    n_fit = min(cfg["fit_sample"], len(points))
    sub = points[rng.choice(len(points), n_fit, replace=False)]
    sub_band = cfg["band_mult"] * _mnn(sub)
    main_peels = []
    find_roof_planes(sub, distance_threshold=sub_band,
                     min_points=int(cfg["min_points_frac"] * n_fit),
                     max_planes=cfg["max_planes"], probability=1.0,
                     peel_log=main_peels)
    main_rows = [dict(peel=p["peel"], n=p["n_inliers"], pitch=p["pitch_deg"],
                      kept=p["kept_by_pitch"])
                 for p in main_peels if "n_inliers" in p]

    return dict(
        question="pitch of EVERY plane peeled across ALL blobs, before the "
                 "pitch window filters anything",
        pitch_window_deg=list(PITCH_WINDOW),
        main_discovery=dict(
            note="main-facet discovery on the 200k subsample. The pitch window "
                 "does not change WHICH planes are peeled (each peel removes "
                 "its points whether the plane is kept or not), so this one "
                 "run enumerates every plane main discovery can ever propose.",
            **summarise(main_rows, "main discovery peels")),
        canonical_run=summarise(canon, "canonical run peels"),
        canonical_caveat=(
            "TRUNCATED TWICE and therefore not the full distribution: the peel "
            "loop stops as soon as the largest remaining plane falls below the "
            "point floor (1933-2000), and it is capped at 4 planes per blob. "
            "Both cut off exactly the small planes a distribution question "
            "cares about."),
        deeper_sweep=summarise(deep, "probe sweep, floor 300, 12 planes/blob"),
        deeper_sweep_note=(
            "A PROBE. Same points, same band, same quality bar, but the point "
            "floor is dropped to 300 and the per-blob budget raised to 12 so "
            "peeling continues far past where the canonical run stops. No "
            "state was written and the canonical facets are unchanged. Note "
            "this is not a superset of the canonical peels: a lower floor "
            "changes which planes get peeled at all, because each peel removes "
            "its points before the next one runs."),
    )


# ---------------------------------------------------------------------------
# A2: does lowering min_pitch move the MAIN facets?
# ---------------------------------------------------------------------------
def a2_main_discovery(cfg, points, spacing, doc, out, stamp):
    """THE QUESTION THAT COULD PROPAGATE TO THE FROZEN RESULT.

    The frozen 313.188 cu^2 is a sum over the main facets. Rather than
    recomputing that total at each min_pitch (alpha shapes over 8 facets, and
    a number that would then have to be trusted), this compares the FACETS
    THEMSELVES bit for bit. If the facets are identical, every quantity
    derived from them is identical too, including the total, and that is a
    stronger statement than two areas agreeing to some number of decimals."""
    def fingerprint(fs):
        rows = []
        for f in fs:
            pts = np.asarray(f["points"], float)
            n = np.asarray(f["normal"], float)
            n = n / np.linalg.norm(n)
            c = pts.mean(axis=0)
            rows.append(dict(n_points=int(len(pts)),
                             pitch=fhex(f["pitch"]),
                             normal=[fhex(v) for v in n],
                             plane_d=fhex(float(-(n @ c))),
                             _pitch_deg=round(float(f["pitch"]), 4),
                             _n=int(len(pts))))
        return rows

    results, base = {}, None
    for mp in (10.0, 5.0, 2.0):
        facets, band, _ = discover_facets(points, cfg, probability=1.0,
                                          spacing=spacing, min_pitch=mp)
        fp = fingerprint(facets)
        if base is None:
            base = fp
        same = (fp == base)
        results[f"min_pitch_{mp:g}"] = dict(
            min_pitch=mp, n_main_facets=len(fp),
            identical_to_min_pitch_10=bool(same),
            facets=[dict(pitch_deg=r["_pitch_deg"], n_points=r["_n"]) for r in fp],
            differences=([] if same else
                         [dict(facet=i,
                               at_10=dict(pitch=base[i]["_pitch_deg"],
                                          n=base[i]["_n"]) if i < len(base) else None,
                               at_this=dict(pitch=fp[i]["_pitch_deg"],
                                            n=fp[i]["_n"]) if i < len(fp) else None)
                          for i in range(max(len(fp), len(base)))
                          if i >= len(base) or i >= len(fp) or fp[i] != base[i]]))

    # Cross-check the min_pitch=10 run against the canonical state on disk, so
    # "identical" is anchored to the state the project actually uses and not
    # merely to this script's own first run.
    canon_rows = [r for r in doc["facets"] if r["kind"] == "main"]
    vs_canonical = all(
        base[i]["normal"] == canon_rows[i]["plane_abcd_hex"][:3] and
        base[i]["plane_d"] == canon_rows[i]["plane_abcd_hex"][3] and
        base[i]["n_points"] == canon_rows[i]["n_points"]
        for i in range(min(len(base), len(canon_rows)))) and \
        len(base) == len(canon_rows)

    allsame = all(v["identical_to_min_pitch_10"] for v in results.values())
    return dict(
        question="does lowering min_pitch change MAIN facet discovery, and so "
                 "reach the frozen 313.188 cu^2 total?",
        method="main-facet discovery only, at min_pitch 10 / 5 / 2, compared "
               "bit for bit on point count, unit normal and plane offset d",
        why_not_recompute_area=("if the facets are bit-identical then every "
                                "derived quantity is identical, including the "
                                "total. Comparing the facets is stronger than "
                                "comparing two area numbers, and it cannot be "
                                "confounded by the area code."),
        control_matches_canonical_state=bool(vs_canonical),
        runs=results,
        verdict=("SAFE: main facet discovery is bit-identical at min_pitch 10, "
                 "5 and 2, so no min_pitch change in this range can reach the "
                 "frozen total" if allsame else
                 "MAIN FACETS MOVE: lowering min_pitch changes main discovery, "
                 "so any change would propagate to the frozen comparison"),
        frozen_total_cu2=313.188,
        frozen_file="preregistered-2026-07-18.json (read-only, never edited)",
    )


# ---------------------------------------------------------------------------
# A3: what is min_pitch protecting against?
# ---------------------------------------------------------------------------
def a3_what_min_pitch_protects(a1, points, cfg, spacing, band, bar, dist,
                               blobs_raw):
    """THE SHARP TEST: would the QUALITY BAR alone reject the sub-10-degree
    planes?

    If it would, min_pitch does no independent work: it is a DEFINITION of what
    counts as a roof, not a filter against error, and it should be argued from
    what a roof is. If it would not, min_pitch is rejecting surfaces that are
    genuinely planar and well fitted, which on this cloud means real low-slope
    roof is being discarded.

    The peel log records pitch and inlier count but not points, so quality
    cannot be read back from it. Instead each blob is re-peeled with the pitch
    window OPENED (0 to 90), which returns the sub-window planes as facets so
    their quality and gross area can be measured. Opening the window does not
    change WHICH planes are peeled, only which are returned, so the planes
    measured here are the same ones the canonical run discarded."""
    from roofkit.segment import find_roof_planes
    from roofkit.measure import facet_area

    rows = []
    for bi, blob in enumerate(blobs_raw):
        (cx0, cy0), (cx1, cy1) = blob["box"]
        inbox = ((points[:, 0] >= cx0) & (points[:, 0] <= cx1) &
                 (points[:, 1] >= cy0) & (points[:, 1] <= cy1))
        cand = points[inbox & (dist > band)]
        if len(cand) < 300:
            continue
        planes = find_roof_planes(cand, distance_threshold=band, min_points=300,
                                  min_pitch=0.0, max_pitch=90.0,
                                  max_planes=12, probability=1.0)
        for p in planes:
            pitch = float(p["pitch"])
            if pitch >= PITCH_WINDOW[0]:
                continue                      # only the ones min_pitch rejects
            pts = np.asarray(p["points"], float)
            q, _ = cov.facet_quality(pts, p["normal"], spacing)
            s_f = float(np.median(cov._nn(pts)))
            gross = float(facet_area(pts, p["normal"], cfg["alpha_mult"] * s_f))
            rows.append(dict(
                blob=bi, n_points=int(len(pts)), pitch_deg=round(pitch, 3),
                quality=round(float(q), 3), quality_bar=round(float(bar), 3),
                passes_quality_bar=bool(q <= bar),
                gross_cu2=round(gross, 4),
                pitch_as_rise_over_12=round(12.0 * np.tan(np.radians(pitch)), 2)))
    rows.sort(key=lambda r: -r["n_points"])

    n_clean = sum(1 for r in rows if r["passes_quality_bar"])
    total_pts = sum(r["n_points"] for r in rows)
    clean_pts = sum(r["n_points"] for r in rows if r["passes_quality_bar"])
    clean_area = sum(r["gross_cu2"] for r in rows if r["passes_quality_bar"])

    if not rows:
        verdict = "min_pitch rejects nothing on this cloud; it is inert here."
    elif n_clean == 0:
        verdict = ("REDUNDANT on this cloud: every sub-window plane also fails "
                   "the quality bar, so min_pitch rejects nothing the quality "
                   "bar would not already reject.")
    else:
        verdict = (f"NOT REDUNDANT: {n_clean} of {len(rows)} sub-window planes "
                   f"PASS the quality bar, carrying {clean_pts:,} points and "
                   f"{clean_area:.3f} cu^2 of gross surface. min_pitch is "
                   f"discarding well-fitted planar surface, so it is acting as "
                   f"a DEFINITION of what counts as a roof, not as a filter "
                   f"against error.")

    return dict(
        method="each residual blob re-peeled with the pitch window opened to "
               "0-90 so the sub-window planes are returned and can be measured. "
               "Opening the window does not change which planes are peeled, "
               "only which are returned.",
        sub_window_planes_measured=rows,
        n_sub_window_planes=len(rows),
        n_passing_quality_bar=n_clean,
        points_in_sub_window_planes=total_pts,
        points_in_clean_sub_window_planes=clean_pts,
        gross_cu2_in_clean_sub_window_planes=round(clean_area, 4),
        verdict=verdict,
        question="what does a 10 degree floor reject that nothing else rejects?",
        upstream_filters=dict(
            ground=("removed by crop box + z_min height cutoff BEFORE any "
                    "segmentation (decision 2026-07-12: no ground-plane "
                    "RANSAC). So min_pitch is not the ground filter."),
            walls=("near-vertical, so they are rejected by max_pitch=60, not "
                   "by min_pitch."),
            foliage=("removed by the ExG colour cutoff then the planarity "
                     "score (decision 2026-07-12). Foliage is not planar, so "
                     "the quality bar is its backstop, not min_pitch."),
            noise_planes=("held out by the fit-quality bar, which a recovered "
                          "facet must clear at the same value the roughest "
                          "main facet already achieves.")),
        quality_bar=round(float(bar), 3),
        reading=("A definition boundary and a safety filter are defended "
                 "differently. A filter is justified by what goes wrong "
                 "without it; a definition is justified by what a roof IS, and "
                 "has to be stated as a scope choice rather than as a margin."),
    )


# ---------------------------------------------------------------------------
# A4: vertical surface inside the footprint, and explainable coverage
# ---------------------------------------------------------------------------
def a4_vertical_surfaces(points, masks, g, cell, spacing, band, bar):
    """How much plan area is occupied by VERTICAL surface?

    A plan-view coverage test can never explain a vertical surface: a wall,
    dormer cheek or gable end standing inside the footprint fills plan cells
    whose points belong to no roof facet, and no roof facet will ever claim
    them. That area is a structural ceiling on coverage, not a defect, and
    reporting coverage against raw building area silently charges the pipeline
    for it.

    THE INSTRUMENT: the vertical EXTENT of the points inside each plan cell.
    A roof surface crossing one small cell spans very little height; a wall
    crossing the same cell spans its whole height. No normals are estimated,
    which keeps this cheap and free of another tuning parameter."""
    building, residual = masks["building"], masks["explained"] * 0 + masks["residual"]
    nx, ny = g["nx"], g["ny"]
    i = np.clip(((points[:, 0] - g["xlo"]) / cell).astype(np.int64), 0, nx - 1)
    j = np.clip(((points[:, 1] - g["ylo"]) / cell).astype(np.int64), 0, ny - 1)
    flat = i * np.int64(ny) + j

    # z max and min per cell, in one pass each.
    zmax = np.full(nx * ny, -np.inf)
    zmin = np.full(nx * ny, np.inf)
    np.maximum.at(zmax, flat, points[:, 2])
    np.minimum.at(zmin, flat, points[:, 2])
    span = (zmax - zmin).reshape(nx, ny)
    span[~np.isfinite(span)] = 0.0

    # The geometric bound: the most height a single surface inside the roof
    # pitch window can span across one cell, plus the fit scatter the quality
    # bar permits. Anything above this cannot be one roof-pitched surface.
    geo = cell * np.sqrt(2.0) * np.tan(np.radians(PITCH_WINDOW[1]))
    scatter = 6.0 * bar * spacing         # +/- 3 RMS at the worst allowed bar
    bound = float(geo + scatter)

    b = building
    vals = span[b]
    qs = [50, 75, 90, 95, 99, 99.9]
    dist_rows = [dict(percentile=q, z_span_cu=round(float(np.percentile(vals, q)), 5))
                 for q in qs]
    # A histogram in units of the bound, so the reader sees whether there is a
    # separation rather than trusting the threshold.
    edges = np.array([0, .25, .5, .75, 1.0, 1.5, 2, 3, 5, 10, np.inf]) * bound
    h, _ = np.histogram(vals, bins=edges)
    hist = [dict(z_span_lo_cu=round(float(edges[k]), 5),
                 z_span_hi_cu=(round(float(edges[k + 1]), 5)
                               if np.isfinite(edges[k + 1]) else None),
                 multiple_of_bound=f"{edges[k]/bound:.2f}-"
                                   f"{edges[k+1]/bound:.2f}" if np.isfinite(edges[k+1])
                                   else f">{edges[k]/bound:.2f}",
                 cells=int(h[k])) for k in range(len(h)) if h[k]]

    cell_area = cell * cell
    vertical = b & (span > bound)
    interior_b = masks["interior"] & b
    res = masks["residual"]
    vert_res = res & (span > bound)

    n_int = int(interior_b.sum())
    n_res = int(res.sum())
    n_vres = int(vert_res.sum())
    raw_cov = 100.0 * (1.0 - n_res / max(n_int, 1))
    exp_cov = 100.0 * (1.0 - (n_res - n_vres) / max(n_int - n_vres, 1))

    return dict(
        question="how much plan area inside the footprint is vertical surface "
                 "that no roof facet can ever explain?",
        instrument=dict(
            what="vertical extent (z max minus z min) of the points in each "
                 "plan cell",
            threshold_cu=round(bound, 5),
            threshold_derivation=(
                f"a single surface at the {PITCH_WINDOW[1]} deg pitch limit "
                f"spans at most cell x sqrt(2) x tan(60) = {geo:.5f} cu across "
                f"one cell diagonal; the fit-quality bar permits scatter up to "
                f"{bar:.3f} x spacing RMS, so +/- 3 RMS adds {scatter:.5f} cu. "
                f"A cell spanning more than their sum cannot hold one "
                f"roof-pitched surface."),
            not_tuned="derived from the pitch window, the cell size and the "
                      "quality bar, all of which already exist. No new "
                      "parameter was introduced."),
        z_span_distribution=dict(percentiles=dist_rows, histogram=hist),
        areas=dict(
            building_cells=int(b.sum()),
            building_cu2=round(float(b.sum()) * cell_area, 3),
            vertical_cells=int(vertical.sum()),
            vertical_cu2=round(float(vertical.sum()) * cell_area, 4),
            vertical_pct_of_building=round(100.0 * vertical.sum() / max(b.sum(), 1), 2),
            interior_building_cells=n_int,
            interior_building_cu2=round(n_int * cell_area, 3),
            residual_cells=n_res,
            residual_cu2=round(n_res * cell_area, 4),
            vertical_residual_cells=n_vres,
            vertical_residual_cu2=round(n_vres * cell_area, 4),
            vertical_share_of_residual_pct=round(100.0 * n_vres / max(n_res, 1), 2)),
        coverage_two_denominators=dict(
            raw=dict(
                definition="residual / interior building area",
                denominator_cu2=round(n_int * cell_area, 3),
                unexplained_cu2=round(n_res * cell_area, 4),
                coverage_pct=round(raw_cov, 2)),
            explainable=dict(
                definition="vertical-surface cells removed from BOTH the "
                           "numerator and the denominator, since they are "
                           "neither explainable nor a failure to explain",
                denominator_cu2=round((n_int - n_vres) * cell_area, 3),
                unexplained_cu2=round((n_res - n_vres) * cell_area, 4),
                coverage_pct=round(exp_cov, 2)),
            both_reported="deliberately. The raw figure is the honest total "
                          "and stays the headline; the explainable figure is "
                          "what the segmentation can actually be held to."),
    )


# ---------------------------------------------------------------------------
# A5: why does the denominator collapse under erosion?
# ---------------------------------------------------------------------------
def a5_denominator_collapse(points, masks, g, cell, out, stamp):
    """Emmett's hypothesis: the building mask is peppered with sub-threshold
    holes, and erosion widens every one of them, so each ring costs far more
    than the outline of a compact shape would.

    THE TEST: erode the mask as it is, and erode a HOLE-FILLED copy of it. The
    filled copy loses only its outer outline. Whatever the real mask loses on
    top of that is the holes' contribution, and the two can be compared ring by
    ring instead of argued about."""
    b = masks["building"]
    filled = binary_fill_holes(b)
    holes = filled & ~b

    lab, n = label(holes)
    sizes = np.bincount(lab.ravel())[1:] if n else np.array([], int)
    cell_area = cell * cell

    buckets = [(1, 1), (2, 2), (3, 4), (5, 9), (10, 24), (25, 99),
               (100, 999), (1000, 10 ** 9)]
    size_hist = []
    for lo, hi in buckets:
        c = int(((sizes >= lo) & (sizes <= hi)).sum())
        if c:
            size_hist.append(dict(hole_size_cells=(f"{lo}" if lo == hi
                                                   else f"{lo}-{hi}"),
                                  n_holes=c,
                                  total_cells=int(sizes[(sizes >= lo) &
                                                        (sizes <= hi)].sum())))

    # Sub-threshold cells: a cell is "building" only with >= 2 points, so cells
    # holding exactly 1 point are holes the threshold PUNCHED, not gaps in the
    # data. Counting them tests the hypothesis directly.
    nx, ny = g["nx"], g["ny"]
    i = np.clip(((points[:, 0] - g["xlo"]) / cell).astype(np.int64), 0, nx - 1)
    j = np.clip(((points[:, 1] - g["ylo"]) / cell).astype(np.int64), 0, ny - 1)
    counts = np.bincount(i * np.int64(ny) + j, minlength=nx * ny).reshape(nx, ny)
    one_pt = filled & (counts == 1)
    zero_pt = filled & (counts == 0)

    depth = distance_transform_edt(b)
    depth_f = distance_transform_edt(filled)
    rings = []
    prev = prev_f = None
    for k in (0, 1, 2, 3, 4):
        cur = int((depth > k).sum())
        cur_f = int((depth_f > k).sum())
        row = dict(ring=k,
                   real_mask_cells=cur, real_mask_cu2=round(cur * cell_area, 3),
                   filled_mask_cells=cur_f,
                   filled_mask_cu2=round(cur_f * cell_area, 3))
        if prev is not None:
            lost, lost_f = prev - cur, prev_f - cur_f
            row.update(cells_lost_this_ring=lost,
                       cells_lost_if_no_holes=lost_f,
                       extra_lost_to_holes=lost - lost_f,
                       hole_share_of_loss_pct=round(
                           100.0 * (lost - lost_f) / max(lost, 1), 1))
        rings.append(row)
        prev, prev_f = cur, cur_f

    total_holes = int(n)
    confirmed = bool(total_holes > 1000 and
                     any(r.get("hole_share_of_loss_pct", 0) > 30 for r in rings))
    return dict(
        question="the coverage denominator falls 202 -> 141 -> 96 -> 72 cu^2 "
                 "across erosion rings. Eroding a compact shape by one cell "
                 "should cost its outline, a few thousand cells; this costs "
                 "about 360,000. Why?",
        hypothesis="the building mask is peppered with sub-threshold holes and "
                   "erosion widens every one of them",
        method="erode the real mask and a hole-FILLED copy of it, ring by ring. "
               "The filled copy can only lose its outer outline, so everything "
               "the real mask loses beyond that is the holes' contribution.",
        holes=dict(
            n_holes=total_holes,
            total_hole_cells=int(sizes.sum()) if n else 0,
            total_hole_cu2=round(float(sizes.sum()) * cell_area, 4) if n else 0.0,
            median_hole_cells=(int(np.median(sizes)) if n else 0),
            largest_hole_cells=(int(sizes.max()) if n else 0),
            size_histogram=size_hist),
        threshold_punched_holes=dict(
            note="a cell counts as building only with >= 2 points, so cells "
                 "inside the footprint holding 0 or 1 point are holes the "
                 "THRESHOLD created, not gaps in the data",
            cells_with_exactly_1_point=int(one_pt.sum()),
            cells_with_0_points=int(zero_pt.sum()),
            combined_cu2=round(float(one_pt.sum() + zero_pt.sum()) * cell_area, 4)),
        erosion_rings=rings,
        # What the headline coverage number is actually measured over. The
        # "interior" mask in coverage_masks is building eroded by one cell, so
        # the reported denominator is ALREADY post-erosion; on a hole-riddled
        # mask that is a much bigger cut than the one-cell fringe it was
        # designed to remove.
        what_the_headline_measures=dict(
            building_cells=int(b.sum()),
            building_cu2=round(float(b.sum()) * cell_area, 3),
            interior_cells=int((masks["interior"] & b).sum()),
            interior_cu2=round(float((masks["interior"] & b).sum()) * cell_area, 3),
            discarded_by_the_one_cell_erosion_cu2=round(
                float(b.sum() - (masks["interior"] & b).sum()) * cell_area, 3),
            discarded_pct=round(
                100.0 * (b.sum() - (masks["interior"] & b).sum()) / max(b.sum(), 1), 1),
            reading=("the one-cell erosion was introduced to stop the "
                     "partially-filled perimeter fringe masquerading as "
                     "unexplained area. On a mask with this many interior "
                     "holes it removes far more than a fringe, so the headline "
                     "coverage denominator is not the building footprint.")),
        verdict=("CONFIRMED: the collapse is dominated by hole boundaries, not "
                 "by the building outline" if confirmed else
                 "NOT CONFIRMED: hole boundaries do not dominate the loss; the "
                 "collapse has another cause"),
        caveat_for_deep_rings=(
            "If confirmed, the deep-ring coverage figures (3 and 4 cells) do "
            "not measure 'the roof away from its eaves'. They measure whatever "
            "survives after every hole has been widened by 3 or 4 cells, which "
            "is the DENSEST roof only. Those rows must carry that caveat or be "
            "dropped; the 1 and 2 cell rows are the defensible ones."),
    ), holes, b, filled


def render_holes(b, filled, holes, path, stamp):
    img = np.zeros(b.shape + (3,))
    img[b] = [0.55, 0.55, 0.55]
    img[holes] = [0.95, 0.15, 0.15]
    fig, ax = plt.subplots(figsize=(9, 11))
    ax.imshow(np.transpose(img, (1, 0, 2)), origin="lower")
    ax.set_title(f"big_house {stamp}: building mask (grey) and its interior "
                 f"holes (red)\n{int(holes.sum()):,} hole cells that erosion "
                 f"widens from the inside", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"  wrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    ap.add_argument("--canonical", default="2026-07-26")
    args = ap.parse_args()
    out = REPO / "reports" / Path(args.dataset).name

    doc, points, facets, cfg = load_canonical(args.dataset, args.canonical)
    band, cell = scalar(doc, "band_cu"), scalar(doc, "cell_cu")
    spacing, bar = scalar(doc, "spacing_cu"), scalar(doc, "quality_bar")
    print(f"  canonical {args.canonical}: {doc['counts']['n_total']} facets, "
          f"{len(points):,} points, hash verified")

    # Pre-recovery masks, which is the state the recovery pass saw: coverage
    # against the MAIN facets only. A1 needs those blobs and that dist.
    main = [f for f in facets if f["kind"] == "main"]
    masks_main, g, _, dist_main = cov.coverage_masks(points, main, band, cell)
    blobs_raw = cov.residual_blobs(masks_main["residual"], g, MIN_BLOB_AREA)
    # Post-recovery masks, for A4 and A5: every accepted facet explains.
    masks, g2, _, _ = cov.coverage_masks(points, facets, band, cell)

    print("\n  A1: pitch of every peeled plane")
    a1 = a1_pitch_distribution(doc, points, cfg, band, spacing, bar, dist_main,
                               blobs_raw, out, args.stamp)
    for k in ("main_discovery", "canonical_run", "deeper_sweep"):
        s = a1[k]
        print(f"    {s['label']:<38} {s['n_planes']:>3} planes  "
              f"below {s['n_below_min_pitch']}, inside {s['n_inside_window']}, "
              f"above {s['n_above_max_pitch']}")
        print(f"      pitches below the window: {s['gaps_below_window']['values_below']}")
        w = s["where_min_pitch_sits"]
        if w["in_gap"]:
            print(f"      min_pitch=10 sits between {w['nearest_below']} and "
                  f"{w['nearest_above']} deg, a {w['gap_width_deg']} deg gap")
        widest = s["gaps_below_window"]["gaps"][:1]
        if widest:
            print(f"      widest gap below the window: {widest[0]['lo']} to "
                  f"{widest[0]['hi']} deg ({widest[0]['width_deg']} deg wide)")

    print("\n  A2: does min_pitch move the MAIN facets?")
    a2 = a2_main_discovery(cfg, points, spacing, doc, out, args.stamp)
    for k, v in a2["runs"].items():
        print(f"    {k:<16} {v['n_main_facets']} facets  "
              f"identical_to_10={v['identical_to_min_pitch_10']}")
    print(f"    control matches canonical state on disk: "
          f"{a2['control_matches_canonical_state']}")
    print(f"    {a2['verdict']}")

    print("\n  A3: what is min_pitch protecting against?")
    a3 = a3_what_min_pitch_protects(a1, points, cfg, spacing, band, bar,
                                    dist_main, blobs_raw)
    for r in a3["sub_window_planes_measured"]:
        print(f"    blob {r['blob']:>2}  {r['n_points']:>7,} pts  "
              f"{r['pitch_deg']:>6.2f} deg (~{r['pitch_as_rise_over_12']}:12)  "
              f"quality {r['quality']:>6.3f} vs bar {r['quality_bar']}  "
              f"passes={r['passes_quality_bar']}  gross {r['gross_cu2']} cu^2")
    print(f"    {a3['verdict']}")

    print("\n  A4: vertical surface inside the footprint")
    a4 = a4_vertical_surfaces(points, masks, g2, cell, spacing, band, bar)
    ar = a4["areas"]
    print(f"    threshold {a4['instrument']['threshold_cu']} cu of z-span per cell")
    print(f"    vertical {ar['vertical_cu2']} cu^2 "
          f"({ar['vertical_pct_of_building']}% of building); of the residual, "
          f"{ar['vertical_residual_cu2']} cu^2 "
          f"({ar['vertical_share_of_residual_pct']}%)")
    c = a4["coverage_two_denominators"]
    print(f"    coverage raw         {c['raw']['coverage_pct']:.2f}% "
          f"(denominator {c['raw']['denominator_cu2']} cu^2)")
    print(f"    coverage explainable {c['explainable']['coverage_pct']:.2f}% "
          f"(denominator {c['explainable']['denominator_cu2']} cu^2)")

    print("\n  A5: denominator collapse")
    a5, holes, b, filled = a5_denominator_collapse(points, masks, g2, cell,
                                                   out, args.stamp)
    w = a5["what_the_headline_measures"]
    print(f"    building {w['building_cu2']} cu^2; the one-cell erosion "
          f"discards {w['discarded_by_the_one_cell_erosion_cu2']} cu^2 "
          f"({w['discarded_pct']}%) before coverage is even computed")
    h = a5["holes"]
    print(f"    {h['n_holes']:,} interior holes, {h['total_hole_cells']:,} cells "
          f"({h['total_hole_cu2']} cu^2), median {h['median_hole_cells']} cell(s)")
    t = a5["threshold_punched_holes"]
    print(f"    cells inside the footprint with 0 or 1 point: "
          f"{t['cells_with_0_points']:,} + {t['cells_with_exactly_1_point']:,}")
    for r in a5["erosion_rings"]:
        if "cells_lost_this_ring" in r:
            print(f"    ring {r['ring']}: lost {r['cells_lost_this_ring']:>7,} "
                  f"cells, of which {r['extra_lost_to_holes']:>7,} to holes "
                  f"({r['hole_share_of_loss_pct']}%)")
    print(f"    {a5['verdict']}")
    render_holes(b, filled, holes, out / f"task7a-holes-{args.stamp}.png",
                 args.stamp)

    doc7a = dict(
        task="Task 7A: measurement only. No state changed, no threshold "
             "adopted, nothing decided.",
        dataset=doc["dataset"], date=args.stamp,
        canonical_state=f"canonical-{args.canonical}.json",
        scalars=dict(spacing_cu=round(spacing, 6), band_cu=round(band, 6),
                     cell_cu=round(cell, 6), quality_bar=round(bar, 4)),
        A1_pitch_distribution=a1,
        A2_main_discovery_sensitivity=a2,
        A3_what_min_pitch_protects=a3,
        A4_vertical_surfaces=a4,
        A5_denominator_collapse=a5,
    )
    p = out / f"task7a-{args.stamp}.json"
    p.write_text(json.dumps(jsonable(doc7a), indent=2))
    print(f"\n  wrote {p}")


if __name__ == "__main__":
    main()
