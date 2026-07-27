# Task 6 diagnostics against the CANONICAL state (probability=1.0 + size floor).
#
#   .venv/Scripts/python.exe -u scripts/diag_task6.py C:/odm/datasets/big_house
#
# Writes (standing rule R2, every actionable number goes to a file):
#   reports/big_house/blob0-coverage-<date>.json    step 3
#   reports/big_house/merge-<date>.json             step 5  (6B)
#   reports/big_house/empty-blobs-<date>.json       step 6  (6C)
#   reports/big_house/coverage-map-<date>.json      step 7
#   reports/big_house/coverage-map-<date>.png       step 7 render
#
# ---------------------------------------------------------------------------
# THIS SCRIPT FITS NOTHING. It loads the canonical facet state from disk (the
# saved plane coefficients and inlier indices) and describes it. The plan-view
# masks ARE recomputed, but that is pure NumPy/SciPy arithmetic over fixed
# points: no RANSAC, no random numbers, so it cannot produce a different state
# than the one on disk.
#
# That separation is the point. The 2026-07-23 diagnostics re-ran the fit to
# reproduce the state they described, which worked until the day it did not.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")            # render to a file, never open a window
import matplotlib.pyplot as plt
from scipy.ndimage import distance_transform_edt, label

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar                     # noqa: E402
from roofkit import coverage as cov                              # noqa: E402
from roofkit.measure import azimuth_degrees, facet_area          # noqa: E402
from roofkit.segment import level_cloud                          # noqa: E402
from roofkit.measure import up_from_tilt                         # noqa: E402

REPO = Path(__file__).resolve().parents[1]

# The 2026-07-23 numbers this run is being compared against, quoted from
# reports/big_house/residual-map-2026-07-23.json. Hard-coded on purpose: they
# describe a state that no longer exists and can never be recomputed, so they
# can only ever be quoted, never re-derived.
OLD = dict(
    source="residual-map-2026-07-23.json",
    blob0_building_cu2=21.3786, blob0_explained_cu2=14.7015,
    blob0_residual_cu2=4.252, blob0_explained_pct=68.77,
    blob0_facet_n_points=99482, blob0_facet_pitch_deg=23.53,
    coverage_pct=93.14, interior_building_cu2=202.171, residual_cu2=13.8768,
)

# Coordinate shorthand for the RAW georeferenced frame (see diag_task5.py).
X_ORIGIN, Y_ORIGIN = 553400.0, 4543000.0
# The query box the 2026-07-23 blob-0 measurement used, in RAW UTM shorthand.
BLOB0_BOX_SHORT = ((84.0, 285.0), (90.0, 291.0))

HEADLINE_RING = 2       # 6E: report coverage excluding a 2-cell edge ring


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


def write_json(path, doc):
    path.write_text(json.dumps(jsonable(doc), indent=2))
    print(f"  wrote {path}")


def level_rotation(cfg):
    """The same rotation level_cloud applies, as an invertible object, so a
    leveled location can be reported back in the RAW frame a human can act on."""
    from scipy.spatial.transform import Rotation
    if cfg["level_tilt_deg"] is None:
        return None
    up = np.asarray(up_from_tilt(cfg["level_tilt_deg"],
                                 cfg["level_uphill_az_deg"]), float)
    up = up / np.linalg.norm(up)
    axis = np.cross(up, [0.0, 0.0, 1.0])
    n = np.linalg.norm(axis)
    if n < 1e-8:
        return None
    return Rotation.from_rotvec(axis / n * np.arccos(np.clip(up[2], -1, 1)))


def to_raw(pts, R):
    return np.asarray(pts) if R is None else R.inv().apply(np.asarray(pts))


# ---------------------------------------------------------------------------
# Plan-view cell ids. A cell is identified by one integer instead of an (i, j)
# pair, so set operations (which facets share cells, does A touch B) become
# plain array intersections instead of full-grid boolean images. With 25 facets
# that is the difference between 25 six-megabyte masks and 25 short lists.
# ---------------------------------------------------------------------------
def cell_ids(pts, g):
    i = np.clip(((pts[:, 0] - g["xlo"]) / g["cell"]).astype(np.int64),
                0, g["nx"] - 1)
    j = np.clip(((pts[:, 1] - g["ylo"]) / g["cell"]).astype(np.int64),
                0, g["ny"] - 1)
    return np.unique(i * np.int64(g["ny"] + 1) + j)


def dilate_ids(ids, g):
    """Grow a cell set by one cell in every direction (the 8 neighbours plus
    itself). Two facets whose RAW cell sets merely abut, sharing an edge but no
    cell, are physically adjacent; without the dilation they would read as
    disconnected."""
    stride = np.int64(g["ny"] + 1)
    out = [ids + di * stride + dj for di in (-1, 0, 1) for dj in (-1, 0, 1)]
    return np.unique(np.concatenate(out))


# ---------------------------------------------------------------------------
# STEP 3: blob 0, old state versus new
# ---------------------------------------------------------------------------
def step3_blob0(doc, points, facets, cfg, masks, g, dist, band, out, stamp):
    R = level_rotation(cfg)
    cell_area = g["cell"] ** 2
    building, explained, residual = (masks["building"], masks["explained"],
                                     masks["residual"])

    # -- the 2026-07-23 measurement, replicated exactly -------------------
    # Selection is by RAW UTM box on the POINTS (that is the frame the old
    # measurement used), then the cells those points occupy are read from the
    # LEVELED grid. The two frames are never compared directly.
    (sx0, sy0), (sx1, sy1) = BLOB0_BOX_SHORT
    bx0, by0 = sx0 + X_ORIGIN, sy0 + Y_ORIGIN
    bx1, by1 = sx1 + X_ORIGIN, sy1 + Y_ORIGIN
    raw = to_raw(points, R)
    in_box = ((raw[:, 0] >= bx0) & (raw[:, 0] <= bx1) &
              (raw[:, 1] >= by0) & (raw[:, 1] <= by1))
    del raw
    ids = cell_ids(points[in_box], g)
    ci = (ids // np.int64(g["ny"] + 1)).astype(int)
    cj = (ids % np.int64(g["ny"] + 1)).astype(int)
    box_bld = float(building[ci, cj].sum()) * cell_area
    box_exp = float((building[ci, cj] & explained[ci, cj]).sum()) * cell_area
    box_res = float(residual[ci, cj].sum()) * cell_area
    box_pct = 100.0 * box_exp / box_bld if box_bld > 0 else 0.0

    # -- the same measurement over blob 0's OWN cells ---------------------
    # The query box above is a rectangle drawn around the feature; blob 0 is
    # the connected residual component itself. Both are reported because the
    # box is what makes the old number comparable, and the blob is what the
    # recovery pass actually worked on.
    b0 = doc["blobs"][0]
    (px0, py0), (px1, py1) = b0["box"]
    inb = ((points[:, 0] >= px0) & (points[:, 0] <= px1) &
           (points[:, 1] >= py0) & (points[:, 1] <= py1))
    bids = cell_ids(points[inb], g)
    bi_ = (bids // np.int64(g["ny"] + 1)).astype(int)
    bj_ = (bids % np.int64(g["ny"] + 1)).astype(int)
    blob_bld = float(building[bi_, bj_].sum()) * cell_area
    blob_exp = float((building[bi_, bj_] & explained[bi_, bj_]).sum()) * cell_area
    blob_res = float(residual[bi_, bj_].sum()) * cell_area
    blob_pct = 100.0 * blob_exp / blob_bld if blob_bld > 0 else 0.0

    # -- the facets blob 0 produced ---------------------------------------
    produced = [dict(facet=f["facet"], n_points=int(len(f["points"])),
                     pitch_deg=round(float(f["pitch"]), 3),
                     azimuth_deg=round(float(azimuth_degrees(f["normal"])), 2),
                     quality=f["quality"])
                for f in facets if f.get("blob") == 0]
    n_new = sum(p["n_points"] for p in produced)

    d_pct = box_pct - OLD["blob0_explained_pct"]
    d_res = box_res - OLD["blob0_residual_cu2"]
    doc3 = dict(
        task="Task 6 step 3: blob 0 coverage, 2026-07-23 state vs canonical "
             f"{stamp} state",
        dataset=doc["dataset"], date=stamp,
        the_question=(
            "The new partition of blob 0 into two planes is better in MEANING "
            "(two real surfaces instead of one fit spanning both), but it "
            "explains FEWER points: 76,595 against 99,482. Better meaning and "
            "worse coverage are different things and the second has to be "
            "measured, not assumed away."),
        point_accounting=dict(
            old_facet_points=OLD["blob0_facet_n_points"],
            old_facet_pitch_deg=OLD["blob0_facet_pitch_deg"],
            new_facets=produced, new_facet_points_total=n_new,
            delta_points=n_new - OLD["blob0_facet_n_points"],
            note="point counts are NOT the coverage measure. A point count says "
                 "how many points a plane owns; coverage asks how much PLAN "
                 "AREA is explained. A facet can own fewer points and still "
                 "cover the same footprint, if the points it dropped sat on top "
                 "of area other points already cover."),
        query_box=dict(
            method="RAW UTM box on points, cells read from the leveled grid; "
                   "identical to the 2026-07-23 measurement",
            box_short=dict(x=[sx0, sx1], y=[sy0, sy1]),
            box_utm=dict(x=[bx0, bx1], y=[by0, by1]),
            roof_points_in_box=int(in_box.sum()),
            old=dict(building_cu2=OLD["blob0_building_cu2"],
                     explained_cu2=OLD["blob0_explained_cu2"],
                     residual_cu2=OLD["blob0_residual_cu2"],
                     explained_pct=OLD["blob0_explained_pct"],
                     source=OLD["source"]),
            new=dict(building_cu2=round(box_bld, 4),
                     explained_cu2=round(box_exp, 4),
                     residual_cu2=round(box_res, 4),
                     explained_pct=round(box_pct, 2)),
            delta=dict(explained_pct=round(d_pct, 2),
                       residual_cu2=round(d_res, 4),
                       explained_cu2=round(box_exp - OLD["blob0_explained_cu2"], 4),
                       building_cu2=round(box_bld - OLD["blob0_building_cu2"], 4)),
            verdict=("COVERAGE IMPROVED" if d_pct > 0.5 else
                     ("COVERAGE DROPPED" if d_pct < -0.5 else
                      "COVERAGE UNCHANGED (within 0.5 pct)"))),
        blob0_own_cells=dict(
            method="the same measurement over blob 0's own bounding box from "
                   "the canonical blob table, not the hand-drawn query box",
            blob_plan_area_cu2=b0["area_cu2"],
            box_leveled=b0["box"],
            building_cu2=round(blob_bld, 4),
            explained_cu2=round(blob_exp, 4),
            residual_cu2=round(blob_res, 4),
            explained_pct=round(blob_pct, 2)),
        caveat=("The old building_cu2 and the new one are both measured on the "
                "same cloud with the same cell size, so any difference between "
                "them is a difference in which cells hold >= 2 roof points, "
                "which cannot change between runs. A non-zero building delta "
                "would mean the two measurements are not over the same region "
                "and the comparison is invalid."),
    )
    write_json(out / f"blob0-coverage-{stamp}.json", doc3)
    return doc3


# ---------------------------------------------------------------------------
# STEP 5 (6B): merge check. Coplanar AND spatially connected.
# ---------------------------------------------------------------------------
def step5_merge(doc, points, facets, g, band, out, stamp):
    F = len(facets)
    ang, off = cov.pairwise_matrix(facets)

    # Plan footprints as cell sets, and the dilated version used for adjacency.
    ids = [cell_ids(f["points"], g) for f in facets]
    dil = [dilate_ids(a, g) for a in ids]

    def touches(i, j):
        """Do the two plan footprints overlap, or lie within one cell of each
        other? Either counts as spatially connected."""
        return len(np.intersect1d(dil[i], ids[j], assume_unique=True)) > 0

    def contact(i, j):
        """How the two footprints meet, in detail. OVERLAP and ABUT are
        different physical situations and the merge rule cannot tell them
        apart on its own:

          overlapping  -> the same surface counted twice, a real merge
          merely abutting -> two DIFFERENT surfaces that happen to be coplanar
                             and adjacent, e.g. two dormers side by side on the
                             same roof slope with their faces in the same plane

        Merging the second case would fuse two real facets into one and
        undercount the roof. So the numbers are reported and the physical call
        is left to a human looking at the render."""
        shared = int(len(np.intersect1d(ids[i], ids[j], assume_unique=True)))
        near = int(len(np.intersect1d(dil[i], ids[j], assume_unique=True)))
        return dict(
            shared_cells=shared,
            cells_within_one=near,
            footprint_cells_a=int(len(ids[i])), footprint_cells_b=int(len(ids[j])),
            shared_pct_of_smaller=round(
                100.0 * shared / max(min(len(ids[i]), len(ids[j])), 1), 2),
            contact=("OVERLAPPING" if shared else
                     ("ABUTTING (share no cell, but come within one)"
                      if near else "SEPARATE")),
            physical_question=(
                "one surface split in two (merge) or two coplanar neighbours "
                "such as adjacent dormer faces (do not merge)? Overlap argues "
                "for the first, pure abutment for the second. This is a call "
                "to make from the render, not from the numbers alone."))

    # TOLERANCES, stated rather than assumed.
    #   angle: 2.0 deg. Adjacent standard roof pitches differ by roughly 3 deg,
    #     so a 2 deg window cannot bridge two genuinely different pitch classes.
    #   offset: the RANSAC band. Two planes closer together than the band the
    #     fit used cannot be told apart BY that fit, so that is the natural
    #     "same sheet" distance. It is a length, so it rescales with the cloud.
    ANG_TOL, OFF_TOL = 2.0, float(band)

    pairs, coplanar_only, merge_now = [], [], []
    for i in range(F):
        for j in range(i + 1, F):
            cop = bool(ang[i, j] <= ANG_TOL and off[i, j] <= OFF_TOL)
            con = touches(i, j)
            row = dict(a=facets[i]["facet"], b=facets[j]["facet"],
                       kind_a=facets[i]["kind"], kind_b=facets[j]["kind"],
                       angle_deg=round(float(ang[i, j]), 4),
                       offset_cu=round(float(off[i, j]), 5),
                       offset_over_band=round(float(off[i, j] / band), 3),
                       coplanar=cop, connected=bool(con),
                       merge=bool(cop and con))
            if cop:
                pairs.append(row)
                if con:
                    row["contact_detail"] = contact(i, j)
                    row["n_points_a"] = int(len(facets[i]["points"]))
                    row["n_points_b"] = int(len(facets[j]["points"]))
                    row["blob_a"] = facets[i]["blob"]
                    row["blob_b"] = facets[j]["blob"]
                    merge_now.append(row)
                else:
                    coplanar_only.append(row)

    # SENSITIVITY. One tolerance pair is a choice; a sweep shows whether the
    # answer depends on it. If the merge set is empty across the whole sweep,
    # the conclusion is not hostage to the numbers picked above.
    sweep = []
    for a_tol in (1.0, 2.0, 3.0, 5.0):
        for o_mult in (0.5, 1.0, 2.0):
            o_tol = o_mult * band
            cop_n = con_n = 0
            for i in range(F):
                for j in range(i + 1, F):
                    if ang[i, j] <= a_tol and off[i, j] <= o_tol:
                        cop_n += 1
                        if touches(i, j):
                            con_n += 1
            sweep.append(dict(angle_tol_deg=a_tol, offset_tol_bands=o_mult,
                              coplanar_pairs=cop_n, also_connected=con_n))

    doc5 = dict(
        task="Task 6 step 5 (6B): adjacent-coplanar merge check on the "
             f"canonical {stamp} state",
        dataset=doc["dataset"], date=stamp, n_facets=F,
        rule=("A merge requires coplanarity AND spatial connectivity (decision "
              "2026-07-25). Plane agreement alone is necessary but not "
              "sufficient: opposite slopes of a hip roof, or the same dormer "
              "face repeated across a building, are parallel and offset by "
              "almost nothing in the offset metric while being metres apart on "
              "the roof. Merging those would fuse two real facets into one."),
        tolerances=dict(
            angle_deg=ANG_TOL,
            angle_reasoning="adjacent standard roof pitches differ by about "
                            "3 deg, so a 2 deg window cannot bridge two pitch "
                            "classes; scale-independent because it is an angle",
            offset_cu=round(float(OFF_TOL), 6),
            offset_form="1 x the RANSAC band",
            offset_reasoning="two planes closer than the band the fit used are "
                             "indistinguishable to that fit; the band is a "
                             "length derived from point spacing, so this "
                             "rescales with any cloud",
            connectivity="plan footprints overlap or lie within one grid cell "
                         f"({round(float(g['cell']), 6)} cu) of each other"),
        merge_pairs=merge_now,
        coplanar_but_disconnected=coplanar_only,
        summary=dict(
            coplanar_pairs=len(pairs),
            coplanar_and_connected=len(merge_now),
            coplanar_but_disconnected=len(coplanar_only),
            verdict=("NO MERGES: no facet pair is both coplanar and touching, "
                     "so the state shows no over-segmentation under this rule"
                     if not merge_now else
                     f"{len(merge_now)} MERGE CANDIDATE(S): see merge_pairs")),
        nothing_was_merged=("This diagnostic FLAGS candidates; it merges "
                            "nothing. Whether a flagged pair is one surface "
                            "split in two or two genuinely separate coplanar "
                            "neighbours is a physical judgement about the "
                            "building, so it belongs to Emmett with the render "
                            "in front of him, not to a tolerance."),
        sensitivity=sweep,
        note=("coplanar_but_disconnected is the interesting column: those are "
              "the pairs a coplanarity-only rule would have merged wrongly. A "
              "non-empty list here is the evidence for the adjacency clause."),
    )
    write_json(out / f"merge-{stamp}.json", doc5)
    if merge_now or coplanar_only:
        render_merge(points, facets, g, merge_now, coplanar_only,
                     out / f"merge-{stamp}.png", stamp)
    return doc5


def step5b_duplicates(doc, points, facets, cfg, out, stamp):
    """Do two facets literally own the SAME points?

    This is a sharper test than coplanarity. Two facets can be coplanar and
    adjacent and still be two real surfaces. But if they share actual point
    INDICES, the same measured points have been fitted twice, and that is not a
    modelling judgement, it is double counting. The test is only possible
    because R1 persists inlier indices; with summary rows alone it is invisible.
    """
    idx = {f["facet"]: np.asarray(f["idx"], np.int64) for f in facets}
    allc = np.concatenate([idx[k] for k in sorted(idx)])
    uniq = np.unique(allc)

    shared_rows = []
    keys = sorted(idx)
    for ai in range(len(keys)):
        for bi in range(ai + 1, len(keys)):
            a, b = keys[ai], keys[bi]
            s = np.intersect1d(idx[a], idx[b], assume_unique=True)
            if len(s) == 0:
                continue
            shared_rows.append(dict(
                a=a, b=b, shared_points=int(len(s)),
                n_a=int(len(idx[a])), n_b=int(len(idx[b])),
                pct_of_smaller=round(
                    100.0 * len(s) / min(len(idx[a]), len(idx[b])), 2),
                blob_a=facets[a]["blob"], blob_b=facets[b]["blob"]))
    shared_rows.sort(key=lambda r: -r["shared_points"])

    # Which blob BOUNDING BOXES overlap? Connected-component labelling makes
    # blobs disjoint as CELL SETS, but their bounding boxes can still overlap or
    # nest, and the recovery pass selects its candidate points by BOX.
    bl = doc["blobs"]
    box_overlaps = []
    for i in range(len(bl)):
        for j in range(i + 1, len(bl)):
            (ax0, ay0), (ax1, ay1) = bl[i]["box"]
            (bx0, by0), (bx1, by1) = bl[j]["box"]
            ox = min(ax1, bx1) - max(ax0, bx0)
            oy = min(ay1, by1) - max(ay0, by0)
            if ox > 0 and oy > 0:
                area_i = (ax1 - ax0) * (ay1 - ay0)
                area_j = (bx1 - bx0) * (by1 - by0)
                box_overlaps.append(dict(
                    blob_a=bl[i]["blob"], blob_b=bl[j]["blob"],
                    overlap_cu2=round(ox * oy, 5),
                    pct_of_smaller_box=round(
                        100.0 * ox * oy / min(area_i, area_j), 2)))
    box_overlaps.sort(key=lambda r: -r["pct_of_smaller_box"])

    # Area impact of the worst offender, measured rather than assumed.
    impact = None
    if shared_rows:
        w = shared_rows[0]
        a, b = w["a"], w["b"]
        pa, pb = points[idx[a]], points[idx[b]]
        both = np.union1d(idx[a], idx[b])

        def gross(pts, normal):
            s_f = float(np.median(cov._nn(pts)))
            return float(facet_area(pts, normal, cfg["alpha_mult"] * s_f))

        na = facets[a]["normal"]
        ga, gb = gross(pa, na), gross(pb, facets[b]["normal"])
        gu = gross(points[both], na)
        impact = dict(
            pair=[a, b],
            gross_a_cu2=round(ga, 5), gross_b_cu2=round(gb, 5),
            gross_of_union_cu2=round(gu, 5),
            sum_if_counted_separately_cu2=round(ga + gb, 5),
            overcount_cu2=round(ga + gb - gu, 5),
            overcount_pct_of_union=round(100.0 * (ga + gb - gu) / max(gu, 1e-9), 1),
            note=("This is the GROSS overcount, i.e. what the total would be "
                  "inflated by if the two were summed naively. The area "
                  "accounting stage resolves contested plan cells by "
                  "highest-surface-wins and charges the loser an occlusion, so "
                  "the reported NET total is largely protected. The facet "
                  "COUNT is not protected: it is inflated by one, and facet "
                  f"{b}'s per-facet numbers describe a fragment of facet {a}, "
                  "not a surface of its own."))

    doc5b = dict(
        task=f"Task 6 step 5b: are any points owned by more than one facet? "
             f"canonical {stamp} state",
        dataset=doc["dataset"], date=stamp,
        why_this_test=("Coplanarity asks whether two facets lie on the same "
                       "plane, which is a modelling judgement. This asks "
                       "whether they own the same measured POINTS, which is "
                       "not a judgement at all. Only possible because standing "
                       "rule R1 persists inlier indices."),
        totals=dict(
            facet_point_entries=int(len(allc)),
            distinct_points=int(len(uniq)),
            duplicated_entries=int(len(allc) - len(uniq)),
            pct_duplicated=round(100.0 * (len(allc) - len(uniq)) / len(allc), 4)),
        sharing_pairs=shared_rows,
        blob_box_overlaps=box_overlaps,
        mechanism=(
            "recover_facets selects a blob's candidate points with a BOUNDING "
            "BOX test (roof[:, 0] between the blob's x limits, and likewise y), "
            "not with the blob's own cells. Connected-component labelling "
            "guarantees blobs are disjoint as CELL SETS, but says nothing about "
            "their bounding boxes, which can overlap or nest. Second, `dist` is "
            "computed ONCE against the main facets before recovery starts and "
            "is never updated as recovered facets are accepted. So a point "
            "already claimed by an earlier blob's facet still reads as "
            "unexplained when a later, box-overlapping blob looks at it, and "
            "gets fitted a second time."),
        verdict=("NO DUPLICATION: every point belongs to exactly one facet"
                 if not shared_rows else
                 f"DUPLICATION FOUND: {len(shared_rows)} facet pair(s) share "
                 f"points; {len(allc) - len(uniq)} point entries are duplicates"),
        area_impact=impact,
        not_fixed=("Nothing was changed. Two repairs are available and they "
                   "are not equivalent: (a) select a blob's candidates by its "
                   "CELLS instead of its bounding box, which is the narrow fix "
                   "for exactly this leak; (b) update `dist` as each recovered "
                   "facet is accepted, so no later blob can re-fit claimed "
                   "points, which is the general fix and also makes the "
                   "recovery order matter. Choosing between them is Emmett's "
                   "call, and either one changes the canonical state, so it "
                   "cannot be slipped in mid-diagnostic."),
    )
    write_json(out / f"duplicate-points-{stamp}.json", doc5b)
    return doc5b


def render_merge(points, facets, g, merge_now, coplanar_only, path, stamp):
    """Plan view with the flagged facets picked out in colour, so the physical
    call (one surface split, or two coplanar neighbours) can be made by
    looking at the roof rather than at a tolerance."""
    involved = {}
    for r in merge_now:
        involved[r["a"]] = "merge"
        involved[r["b"]] = "merge"
    for r in coplanar_only:
        involved.setdefault(r["a"], "coplanar_only")
        involved.setdefault(r["b"], "coplanar_only")

    img = np.zeros((g["nx"], g["ny"], 3))
    palette = {"merge": [(0.95, 0.15, 0.15), (1.0, 0.65, 0.0)],
               "coplanar_only": [(0.20, 0.45, 0.95), (0.35, 0.75, 0.95)]}
    used = {"merge": 0, "coplanar_only": 0}

    for f in facets:                       # everything else, mid grey
        ids = cell_ids(f["points"], g)
        i = (ids // np.int64(g["ny"] + 1)).astype(int)
        j = (ids % np.int64(g["ny"] + 1)).astype(int)
        if f["facet"] in involved:
            continue
        img[i, j] = [0.55, 0.55, 0.55]

    labels = []
    for f in facets:
        if f["facet"] not in involved:
            continue
        kind = involved[f["facet"]]
        colour = palette[kind][used[kind] % len(palette[kind])]
        used[kind] += 1
        ids = cell_ids(f["points"], g)
        i = (ids // np.int64(g["ny"] + 1)).astype(int)
        j = (ids % np.int64(g["ny"] + 1)).astype(int)
        img[i, j] = colour
        labels.append((f["facet"], kind, colour, float(i.mean()), float(j.mean())))

    fig, ax = plt.subplots(figsize=(9, 11))
    ax.imshow(np.transpose(img, (1, 0, 2)), origin="lower")
    for fid, kind, colour, ci, cj in labels:
        ax.annotate(str(fid), (ci, cj), color="white", fontsize=9,
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc=colour, ec="none"))
    ax.set_title(f"big_house canonical {stamp}: coplanar facet pairs\n"
                 f"warm = coplanar AND touching (merge candidate), "
                 f"cool = coplanar but disconnected (rule correctly declines)",
                 fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"  wrote {path}")


# ---------------------------------------------------------------------------
# STEP 6 (6C): the blobs that produced no facet
# ---------------------------------------------------------------------------
def step6_empty_blobs(doc, out, stamp, points=None, cfg=None, band=None,
                      spacing=None, bar=None, dist=None, blobs_raw=None, g=None):
    # Measure the QUALITY of what each empty blob contains, not just its pitch.
    # Without this the report says "rejected for pitch" and stops, which cannot
    # distinguish a junk plane from a well-fitted real surface that the pitch
    # definition happens to exclude. That distinction is the whole question, and
    # leaving it out once already cost a round trip (Task 7A3).
    measured = {}
    if points is not None and blobs_raw is not None:
        from roofkit.segment import find_roof_planes
        from roofkit.measure import rise_over_12
        ny1 = np.int64(g["ny"] + 1)
        pi = np.clip(((points[:, 0] - g["xlo"]) / g["cell"]).astype(np.int64),
                     0, g["nx"] - 1)
        pj = np.clip(((points[:, 1] - g["ylo"]) / g["cell"]).astype(np.int64),
                     0, g["ny"] - 1)
        pcell = pi * ny1 + pj
        unexplained = dist > band
        empty_ids = {e["blob"] for e in doc["recovery_log"] if not e["planes"]}
        for bi in empty_ids:
            if bi >= len(blobs_raw):
                continue
            b = blobs_raw[bi]
            bc = (b["cells"][:, 0].astype(np.int64) * ny1 +
                  b["cells"][:, 1].astype(np.int64))
            cand = points[np.flatnonzero(unexplained & np.isin(pcell, bc))]
            if len(cand) < 300:
                continue
            planes = find_roof_planes(cand, distance_threshold=band,
                                      min_points=300, min_pitch=0.0,
                                      max_pitch=90.0, max_planes=6,
                                      probability=1.0)
            got = []
            for p in planes:
                pts = np.asarray(p["points"], float)
                q, _ = cov.facet_quality(pts, p["normal"], spacing)
                s_f = float(np.median(cov._nn(pts)))
                gross = float(facet_area(pts, p["normal"],
                                         cfg["alpha_mult"] * s_f))
                got.append(dict(n_points=int(len(pts)),
                                pitch_deg=round(float(p["pitch"]), 3),
                                rise_over_12=round(rise_over_12(p["pitch"]), 2),
                                quality=round(float(q), 3),
                                quality_bar=round(float(bar), 3),
                                passes_quality_bar=bool(q <= bar),
                                gross_cu2=round(gross, 4)))
            measured[bi] = got

    rows = []
    for e in doc["recovery_log"]:
        if e["planes"]:
            continue
        peels = e.get("peels", [])
        found = [p for p in peels if "n_inliers" in p]
        stops = [p for p in peels if "stopped" in p]
        near_vert = [p for p in found if p["pitch_deg"] > 60.0]
        near_flat = [p for p in found if p["pitch_deg"] < 10.0]
        lo_pitch = found[0]["pitch_window"][0] if found else 10.0
        hi_pitch = found[0]["pitch_window"][1] if found else 60.0
        vert_str = ", ".join("%.1f" % p["pitch_deg"] for p in near_vert)
        flat_str = ", ".join("%.1f" % p["pitch_deg"] for p in near_flat)
        if not found:
            why = ("RANSAC proposed nothing: too few unexplained points to "
                   "start a peel")
        elif len(near_vert) == len(found):
            why = (f"every surface here is near-VERTICAL ({vert_str} deg, "
                   f"above the {hi_pitch} deg maximum). Vertical surfaces are "
                   f"not roof facets: they are dormer cheeks, gable ends or "
                   f"wall tops. Nothing is missing here.")
        elif len(near_flat) == len(found):
            why = (f"every surface here is near-FLAT ({flat_str} deg, below "
                   f"the {lo_pitch} deg minimum). This is a low-slope surface "
                   f"sitting outside the roof-facet definition, not a facet "
                   f"the fit failed to find.")
        else:
            why = (f"mixed: {len(near_vert)} near-vertical ({vert_str} deg) and "
                   f"{len(near_flat)} near-flat ({flat_str} deg) surface(s), "
                   f"none inside the {lo_pitch}-{hi_pitch} deg roof window")
        rows.append(dict(
            blob=e["blob"], plan_area_cu2=round(float(e["area_cu2"]), 4),
            n_unexplained_points=e["n_candidate"],
            n_planes_peeled=len(found),
            points_in_peeled_planes=sum(p["n_inliers"] for p in found),
            pitches_deg=[p["pitch_deg"] for p in found],
            n_near_vertical=len(near_vert), n_near_flat=len(near_flat),
            terminated=(stops[0]["stopped"] if stops else
                        "hit max_planes_per_blob"),
            why_no_facet=why,
            contents_measured=measured.get(e["blob"], [])))
    rows.sort(key=lambda r: -r["plan_area_cu2"])

    # THE HEADLINE THIS DIAGNOSTIC MUST NOT BURY: an empty blob whose contents
    # are WELL FITTED is a surface the pitch definition is discarding, not a
    # surface the fit failed to find. Those are opposite findings.
    clean = []
    for r in rows:
        for p in r["contents_measured"]:
            if p["passes_quality_bar"] and p["pitch_deg"] < 10.0:
                clean.append(dict(blob=r["blob"], **p))
    clean.sort(key=lambda p: -p["gross_cu2"])

    doc6 = dict(
        task=f"Task 6 step 6 (6C): blobs producing no accepted facet, "
             f"canonical {stamp} state",
        dataset=doc["dataset"], date=stamp,
        instrument=("find_roof_planes now takes a peel_log and records EVERY "
                    "plane it peels, with its pitch, BEFORE the pitch window "
                    "filters it. Previously that filter was silent, so a blob "
                    "yielding no facet could not be told apart from a blob "
                    "where RANSAC found nothing at all. Those are different "
                    "diagnoses and only one of them is a problem."),
        pitch_window_deg=[10.0, 60.0],
        n_blobs_total=doc["counts"]["n_blobs"],
        n_blobs_empty=len(rows),
        blobs=rows,
        well_fitted_surfaces_excluded_by_pitch=dict(
            n=len(clean),
            total_gross_cu2=round(sum(p["gross_cu2"] for p in clean), 4),
            total_points=sum(p["n_points"] for p in clean),
            planes=clean,
            reading=("These planes CLEAR the same fit-quality bar the accepted "
                     "facets clear. They are excluded solely because their "
                     "pitch falls outside the roof window, which is a "
                     "DEFINITION, so this number is the area the current "
                     "definition of 'roof' is choosing not to measure. It "
                     "belongs in the report as a stated exclusion, never as "
                     "silence.")),
        interpretation=(
            "A residual blob is unexplained PLAN AREA. It is not automatically "
            "a missing roof facet. Coverage is a plan-view test, so a vertical "
            "surface standing inside the footprint (a dormer cheek, a gable "
            "end) occupies plan cells whose points belong to no roof facet, and "
            "registers as a gap that no roof facet can ever close. Those blobs "
            "are a permanent floor on coverage, not a defect."),
    )
    write_json(out / f"empty-blobs-{stamp}.json", doc6)
    return doc6


# ---------------------------------------------------------------------------
# STEP 7: coverage and residual map
# ---------------------------------------------------------------------------
def step7_coverage(doc, points, facets, cfg, masks, g, out, stamp):
    cell = g["cell"]
    cell_area = cell * cell
    building, residual = masks["building"], masks["residual"]
    interior_building = int((masks["interior"] & building).sum())
    resid_cells = int(residual.sum())
    frac = cov.coverage_fraction(masks)

    # EDT depth: how many cells each residual cell sits inside the footprint
    # edge. Ragged eaves produce residual at depth 1-2 that is a capture
    # artefact, not a missing facet; a real missing facet sits deep.
    depth = distance_transform_edt(building)
    rd = depth[residual]

    hist = []
    for lo in range(1, 12):
        n = int(((rd >= lo) & (rd < lo + 1)).sum())
        if n:
            hist.append(dict(depth_cells=lo, cells=n,
                             cu2=round(n * cell_area, 4),
                             pct_of_residual=round(100.0 * n / max(resid_cells, 1), 2)))
    deep = int((rd >= 12).sum())
    if deep:
        hist.append(dict(depth_cells=">=12", cells=deep,
                         cu2=round(deep * cell_area, 4),
                         pct_of_residual=round(100.0 * deep / max(resid_cells, 1), 2)))

    # 6E: report BOTH the raw coverage and coverage after excluding an edge
    # ring, each as its own number with its own denominator. Never the
    # perimeter/interior split as a single ratio: it swings from 58 to 90 pct
    # across ring widths 2 to 4 with no flat region, so any single value of it
    # is an artefact of the ring width chosen (measured 2026-07-23).
    rings = []
    for k in (1, 2, 3, 4):
        keep = depth > k                      # cells at least k+1 deep
        denom = int((keep & building).sum())
        res_k = int((keep & residual).sum())
        rings.append(dict(
            ring_excluded_cells=k,
            ring_excluded_cu=round(float(k * cell), 5),
            building_cells=denom,
            building_cu2=round(denom * cell_area, 3),
            residual_cells=res_k,
            residual_cu2=round(res_k * cell_area, 4),
            coverage_pct=round(100.0 * (1.0 - res_k / max(denom, 1)), 2)))
    headline_ring = next(r for r in rings
                         if r["ring_excluded_cells"] == HEADLINE_RING)

    doc7 = dict(
        task=f"Task 6 step 7: coverage and residual map, canonical {stamp} state",
        dataset=doc["dataset"], date=stamp,
        grid=dict(cell_cu=round(float(cell), 6),
                  cell_area_cu2=round(float(cell_area), 8),
                  nx=int(g["nx"]), ny=int(g["ny"]),
                  cell_mult_of_spacing=2.5,
                  spacing_cu=round(scalar(doc, "spacing_cu"), 6)),
        # THE HEADLINE NUMBERS (decision 2026-07-26). The single coverage
        # percentage was answering two questions at once against a base that
        # hole-erosion had shrunk by a third. It is split, and the footprint is
        # reported three ways so the base is visible rather than assumed.
        footprint=cov.footprint_three_ways(masks, cell),
        filled_holes=cov.filled_hole_report(masks, cell),
        coverage=cov.split_coverage(masks, cell),
        legacy_single_number=dict(
            note="the old single metric, kept only so the superseded numbers "
                 "can be compared like for like. It is NOT a headline: its "
                 "denominator excludes filled holes and it mixes a capture "
                 "shortfall into a segmentation score.",
            definition="1 - residual cells / interior building cells, where "
                       "interior is the footprint eroded by one cell",
            coverage_pct=round(100.0 * float(frac), 2),
            interior_building_cells=interior_building,
            interior_building_cu2=round(interior_building * cell_area, 3),
            residual_cells=resid_cells,
            residual_cu2=round(resid_cells * cell_area, 4)),
        coverage_excluding_edge_ring_DEPRECATED=dict(
            why_deprecated=(
                "the ring rows were an attempt to separate a ragged eave from "
                "real unexplained area, and they were measuring something "
                "else. 90 to 95 percent of what each ring removed was the "
                "boundary of an interior HOLE, not the building outline, so "
                "the deep rings sampled only the densest roof. Hole filling "
                "removes the reason these rows existed: the erosion now costs "
                "a few percent instead of a third. Kept for one revision so "
                "the superseded numbers remain checkable."),
            headline_ring_cells=HEADLINE_RING,
            headline=headline_ring,
            all_ring_widths=rings,
            why=("Two numbers, not one. The raw figure is the honest total. "
                 "The ring-excluded figure separates a ragged reconstructed "
                 "eave, which is a capture artefact, from unexplained area "
                 "inside the roof, which would be a missing facet. Reporting "
                 "the perimeter share as a single ratio is refused: it swings "
                 "58 to 90 pct across ring widths 2 to 4 with no flat region, "
                 "so it has no defensible value.")),
        depth_histogram=hist,
        comparison_to_superseded_state=dict(
            source=OLD["source"],
            note="the 2026-07-23 state is SUPERSEDED, not corrected. It is "
                 "quoted here for context only; it can never be recomputed.",
            old_coverage_pct=OLD["coverage_pct"],
            new_coverage_pct=round(100.0 * float(frac), 2),
            delta_pct=round(100.0 * float(frac) - OLD["coverage_pct"], 2),
            old_residual_cu2=OLD["residual_cu2"],
            new_residual_cu2=round(resid_cells * cell_area, 4),
            old_interior_building_cu2=OLD["interior_building_cu2"],
            new_interior_building_cu2=round(interior_building * cell_area, 3)),
    )
    write_json(out / f"coverage-map-{stamp}.json", doc7)
    render(masks, g, depth, out / f"coverage-map-{stamp}.png", stamp,
           doc7["coverage"]["facet_coverage"]["pct"])
    return doc7


def render(masks, g, depth, path, stamp, cov_pct):
    """Plan view: explained roof grey, edge-ring residual orange, interior
    residual red. Interior red is the only colour that means a possible missing
    facet; orange is eave raggedness."""
    building, residual = masks["building"], masks["residual"]
    explained = masks["explained"]
    perim = residual & (depth <= HEADLINE_RING)
    inter = residual & (depth > HEADLINE_RING)

    img = np.zeros((g["nx"], g["ny"], 3))
    img[building & explained] = [0.62, 0.62, 0.62]
    img[perim] = [1.0, 0.55, 0.0]
    img[inter] = [0.90, 0.08, 0.08]

    fig, ax = plt.subplots(figsize=(9, 11))
    ax.imshow(np.transpose(img, (1, 0, 2)), origin="lower")
    ax.set_title(f"big_house canonical {stamp}\n"
                 f"coverage {cov_pct:.2f} pct   "
                 f"grey = explained, orange = edge ring (<= {HEADLINE_RING} "
                 f"cells), red = interior residual", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"  wrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    # The blob-0 comparison targets the 2026-07-23 state by hard-coded numbers.
    # Once the blob table changes, "blob 0" is a different feature and the
    # comparison is meaningless, so it is opt-in rather than silently stale.
    ap.add_argument("--blob0", action="store_true",
                    help="run the legacy blob-0 comparison against 2026-07-23")
    args = ap.parse_args()

    out = REPO / "reports" / Path(args.dataset).name
    doc, points, facets, cfg = load_canonical(args.dataset, args.stamp)
    band = scalar(doc, "band_cu")
    cell = scalar(doc, "cell_cu")
    print(f"  loaded canonical {args.stamp}: {doc['counts']['n_total']} facets "
          f"({doc['counts']['n_main']} main + {doc['counts']['n_recovered']} "
          f"recovered), {len(points):,} points, cloud hash verified")

    # Plan-view masks POST-recovery: every accepted facet counts as an
    # explainer. Pure arithmetic over fixed points, no fitting.
    # POST-recovery masks: every accepted facet counts as an explainer. These
    # are what coverage is reported from.
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
    # PRE-recovery masks: main facets only. This is the state the recovery pass
    # actually saw, so it is the only way to reconstruct the blobs it worked on
    # and re-measure what they contain. Using the post-recovery masks here would
    # describe different blobs than the ones in the recovery log.
    main_only = [f for f in facets if f["kind"] == "main"]
    masks_main, g_main, _, dist_main = cov.coverage_masks(points, main_only,
                                                          band, cell)
    blobs_raw = cov.residual_blobs(masks_main["residual"], g_main, 0.15)

    if args.blob0:
        print("\n  step 3: blob 0, old state vs new")
        d3 = step3_blob0(doc, points, facets, cfg, masks, g, dist, band, out,
                         args.stamp)
        q = d3["query_box"]
        print(f"    old {q['old']['explained_pct']:.2f} pct explained, "
              f"residual {q['old']['residual_cu2']:.4f} cu^2")
        print(f"    new {q['new']['explained_pct']:.2f} pct explained, "
              f"residual {q['new']['residual_cu2']:.4f} cu^2")
        print(f"    {q['verdict']}")
    else:
        print("\n  step 3 (blob 0 vs 2026-07-23): SKIPPED. The blob table has "
              "changed, so 'blob 0' is no longer the same feature and the "
              "comparison would be nonsense. Pass --blob0 to force it.")

    print("\n  step 5 (6B): merge check")
    d5 = step5_merge(doc, points, facets, g, band, out, args.stamp)
    print(f"    {d5['summary']['verdict']}")
    print(f"    coplanar pairs {d5['summary']['coplanar_pairs']}, "
          f"of which connected {d5['summary']['coplanar_and_connected']}, "
          f"disconnected {d5['summary']['coplanar_but_disconnected']}")

    print("\n  step 5b: do any two facets own the same points?")
    d5b = step5b_duplicates(doc, points, facets, cfg, out, args.stamp)
    print(f"    {d5b['verdict']}")
    for r in d5b["sharing_pairs"]:
        print(f"    facets {r['a']} & {r['b']} share {r['shared_points']:,} "
              f"points ({r['pct_of_smaller']}% of the smaller), from blobs "
              f"{r['blob_a']} and {r['blob_b']}")
    if d5b["area_impact"]:
        ai = d5b["area_impact"]
        print(f"    gross overcount if summed naively: "
              f"{ai['overcount_cu2']} cu^2 ({ai['overcount_pct_of_union']}%)")

    print("\n  step 6 (6C): blobs producing no facet")
    d6 = step6_empty_blobs(doc, out, args.stamp, points=points, cfg=cfg,
                           band=band, spacing=scalar(doc, "spacing_cu"),
                           bar=scalar(doc, "quality_bar"), dist=dist_main,
                           blobs_raw=blobs_raw, g=g_main)
    for r in d6["blobs"]:
        print(f"    blob {r['blob']:>2}  {r['plan_area_cu2']:.4f} cu^2  "
              f"pitches {r['pitches_deg']}")
    w = d6["well_fitted_surfaces_excluded_by_pitch"]
    print(f"    WELL-FITTED surface excluded by the pitch definition: "
          f"{w['n']} plane(s), {w['total_gross_cu2']} cu^2 gross, "
          f"{w['total_points']:,} points")
    for p_ in w["planes"][:5]:
        print(f"      blob {p_['blob']:>2}  {p_['n_points']:>8,} pts  "
              f"{p_['pitch_deg']:>6.3f} deg ({p_['rise_over_12']}:12)  "
              f"quality {p_['quality']} vs bar {p_['quality_bar']}  "
              f"gross {p_['gross_cu2']} cu^2")

    print("\n  step 7: coverage and residual map")
    d7 = step7_coverage(doc, points, facets, cfg, masks, g, out, args.stamp)
    fp = d7["footprint"]
    print(f"    footprint  raw {fp['raw_cu2']} -> filled {fp['filled_cu2']} -> "
          f"eroded {fp['eroded_cu2']} cu^2 "
          f"(erosion costs {fp['erosion_cost_pct_of_filled']}%)")
    c1 = d7["coverage"]["density_testable_fraction"]
    c2 = d7["coverage"]["facet_coverage"]
    print(f"    density-testable fraction (CAPTURE)  {c1['pct']:.2f} pct  "
          f"({c1['testable_cu2']} of {c1['footprint_cu2']} cu^2)")
    print(f"    facet coverage (SEGMENTATION)        {c2['pct']:.2f} pct  "
          f"({c2['explained_cu2']} of {c2['testable_cu2']} cu^2)")


if __name__ == "__main__":
    main()
