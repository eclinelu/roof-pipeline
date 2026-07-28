# THE M1a PLATEAU SWEEP.
#
#   .venv/Scripts/python.exe -u scripts/sweep_m1a.py C:/odm/datasets/big_house
#
# Writes reports/big_house/m1a-sweep-<date>.json            (standing rule R2)
#
# Pre-registered 2026-07-27 (decisions/2026-07-27-m1a-connectivity-preregistration.md)
# Amended      2026-07-28 (decisions/2026-07-28-m1a-preregistration-amendment.md)
#
# NOTHING HERE IS ADOPTED. canonical-2026-07-26-r2 is never written and remains
# canonical; published facet coverage stays 88.40 pct. This script writes ONE
# new dated artifact and touches nothing else.
#
# ---------------------------------------------------------------------------
# WHAT IT DOES
#
# One BASELINE run with the filter off, then 20 runs over the pre-registered
# grid with it on. Each run is the FULL pipeline (main discovery -> quality bar
# -> coverage -> residual blobs -> recovery -> coverage again), because the
# pre-registration is explicit that recovered facets are not insulated: main
# planes move, so dist moves, so the residual moves, so recovery re-runs on
# different input.
#
#     connectivity scale   1.5, 2.0, 2.5, 3.5, 5.0   x median point spacing
#     minimum component    1.0, 0.01, 0.001, 0.0001  x largest component points
#
# A PLATEAU IS A REGION OVER WHICH THE ANSWER DOES NOT CHANGE. If there is no
# plateau this script says so and picks nothing. No value is chosen from a
# monotone curve.
#
# ---------------------------------------------------------------------------
# THE INDEPENDENT ASSERTIONS (standing rule 2026-07-27-silent-failure-standing-rule,
# and the P2 replacement required by the 2026-07-28 amendment)
#
# A0  the BASELINE reproduces canonical-2026-07-26-r2 facet for facet.
#     Independent of this run's results; it is a committed artifact.
#
# A1  POINT-DOMAIN SEPARATION, the primary. For every facet, the minimum plan
#     distance between the KEPT set and the REMOVED set exceeds the
#     connectivity scale. Computed with a cKDTree on raw XY and the output
#     partition ONLY: no occupancy raster, no cell indices, no ndimage.label,
#     no component sizes, no argmax. Provable from the definition of a
#     connectivity cut, therefore true whatever the sweep's outcome is.
#
# A2  COMPONENT COUNT re-derived by a DIFFERENT ALGORITHM: a sparse cell
#     adjacency graph over unique cells plus scipy.sparse.csgraph, versus the
#     filter's dense raster scanline labelling. Closes A1's blind spot, which
#     is that A1 permits a kept set that is itself in two well-separated
#     pieces.
#
# A3  THE NO-OP TRIPWIRE, and it is the one that matters most. If the filter
#     is never actually invoked, every grid point returns the baseline, every
#     number is identical everywhere, and the sweep displays a PERFECT
#     PLATEAU. The report would then read "plateau found" for a fix that did
#     nothing. At 2.5 x spacing, removals must be non-zero on all 8 main
#     facets, which is an assertion against fragments-2026-07-27.json, a
#     committed artifact written by different code.
#
# A4  FACET IDENTITY. find_roof_planes runs on the seeded subsample BEFORE the
#     filter, so the discovered plane list must be bit-identical in all 21
#     runs. If it is not, facet k is not the same surface across runs and every
#     per-facet delta in this report is meaningless.
#
# A5  CONSERVATION. kept and removed are disjoint and sum to the pre-filter
#     membership.
# ---------------------------------------------------------------------------
import argparse
import gc
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
from scipy.ndimage import label
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                            # noqa: E402
from recon_common import discover_facets                          # noqa: E402
from roofkit.stats import median_nn_spacing                       # noqa: E402
from roofkit.segment import level_cloud, assert_single_ownership  # noqa: E402
from roofkit.measure import up_from_tilt, facet_area              # noqa: E402
from roofkit import coverage as cov                               # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"

# Same constants canonical_state.py uses, so the sweep is commensurable with
# every existing artifact.
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
MIN_AREA_POINTS_EQUIV = 3704

# THE PRE-REGISTERED GRID (values fixed in the 2026-07-28 amendment).
SCALES = [1.5, 2.0, 2.5, 3.5, 5.0]
FRACS = [1.0, 0.01, 0.001, 0.0001]

# The connectivity scale at which the no-op tripwire fires. Chosen because it
# is the cell fragments-2026-07-27.json measured at, so the assertion compares
# against a committed number rather than against an expectation.
TRIPWIRE_SCALE = 2.5

# Extent inflation is ALWAYS measured at this cell, whatever the sweep's
# connectivity scale is. Measuring it with the same knob that produced the
# filtering would be circular: a coarser connectivity scale would "improve"
# inflation simply by relabelling the same points.
INFLATION_CELL_MULT = 2.5
STRUCT8 = np.ones((3, 3), dtype=bool)


# ===========================================================================
# INDEPENDENT INSTRUMENTS. Nothing below imports or reuses connected_core.
# ===========================================================================
def independent_component_count(xy, cell, origin=None):
    """A2. Count plan-connected components WITHOUT the filter's machinery.

    The filter rasterises to a dense boolean grid and calls
    scipy.ndimage.label, which is a scanline algorithm over that raster. This
    builds a SPARSE ADJACENCY GRAPH over the unique occupied cells and calls
    scipy.sparse.csgraph.connected_components, which is a graph traversal.
    Different data structure, different algorithm, different library
    subpackage. A bug in one has no reason to reproduce in the other.

    Fully vectorised: np.unique gives lexicographically sorted cell keys, so a
    single encoded integer per cell is sorted too, and each of the four
    forward neighbour directions is one searchsorted. The four backward
    directions are the same edges undirected, so they are not built twice."""
    # The origin must be the one the FILTER used, not one re-derived from the
    # subset handed in. Re-deriving lands on a different raster phase and
    # produces a disagreement about ALIGNMENT that reads as a disagreement
    # about LABELLING. That is exactly how this assertion first failed.
    lo = xy.min(axis=0) if origin is None else np.asarray(origin, float)
    ij = np.stack([np.floor((xy[:, 0] - lo[0]) / cell).astype(np.int64),
                   np.floor((xy[:, 1] - lo[1]) / cell).astype(np.int64)],
                  axis=1)
    keys = np.unique(ij, axis=0)
    nk = len(keys)
    if nk == 0:
        return 0
    # Encode (i, j) as one sorted integer. np.unique(axis=0) sorts by column 0
    # then column 1, and j >= 0, so i * BIG + j is ascending for BIG > max(j).
    big = int(keys[:, 1].max()) + 2
    enc = keys[:, 0] * big + keys[:, 1]
    rows, cols = [], []
    for da, db in ((1, 0), (0, 1), (1, 1), (1, -1)):
        target = (keys[:, 0] + da) * big + (keys[:, 1] + db)
        pos = np.clip(np.searchsorted(enc, target), 0, nk - 1)
        hit = enc[pos] == target
        rows.append(np.flatnonzero(hit))
        cols.append(pos[hit])
    r = np.concatenate(rows) if rows else np.array([], dtype=np.int64)
    c = np.concatenate(cols) if cols else np.array([], dtype=np.int64)
    if len(r) == 0:
        return nk
    g = coo_matrix((np.ones(len(r), dtype=np.int8), (r, c)), shape=(nk, nk))
    n, _ = connected_components(g, directed=False)
    return int(n)


def min_cross_distance(kept_xy, removed_xy):
    """A1. Minimum plan distance between the kept set and the removed set.

    Reads raw XY and the output partition, nothing else. Builds the tree on
    the smaller set (the removed points) and queries with the larger, which is
    the cheap direction; the minimum is symmetric so the choice cannot change
    the answer."""
    if len(removed_xy) == 0 or len(kept_xy) == 0:
        return None
    tree = cKDTree(removed_xy)
    d, _ = tree.query(kept_xy, k=1, workers=-1)
    return float(d.min())


def extent_inflation(xy, cell):
    """Full plan extent over main-body extent, measured at a FIXED cell.
    Same definition probe_fragments.py used, so the numbers are comparable to
    fragments-2026-07-27.json."""
    lo = xy.min(axis=0)
    i = ((xy[:, 0] - lo[0]) / cell).astype(np.int64)
    j = ((xy[:, 1] - lo[1]) / cell).astype(np.int64)
    occ = np.zeros((i.max() + 1, j.max() + 1), dtype=bool)
    occ[i, j] = True
    lab, n = label(occ, structure=STRUCT8)
    per = lab[i, j]
    sizes = np.bincount(per, minlength=n + 1)
    sizes[0] = 0
    core = per == int(np.argmax(sizes))
    fw = xy[:, 0].max() - xy[:, 0].min()
    fh = xy[:, 1].max() - xy[:, 1].min()
    cxy = xy[core]
    cw = cxy[:, 0].max() - cxy[:, 0].min()
    ch = cxy[:, 1].max() - cxy[:, 1].min()
    return float(max(fw, fh) / max(max(cw, ch), 1e-12)), int(n)


# ===========================================================================
# ONE FULL PIPELINE RUN
# ===========================================================================
def run_once(points, cfg, spacing, connect_mult, frac, min_points_hard=None):
    """The whole pipeline at one grid point. Returns everything the
    pre-registration asks to be reported."""
    planes_seen = []
    facets, band, s_full = discover_facets(
        points, cfg, probability=1.0, spacing=spacing,
        connect_mult=connect_mult, min_component_frac=frac,
        plane_out=planes_seen)
    bar, ratios = cov.calibrate_quality_bar(facets, s_full)

    # The derived point floor, exactly as canonical_state.py computes it. It is
    # derived from THIS run's main facets, so it can move when the facets do;
    # that is by design and the value used is reported.
    min_area = MIN_AREA_POINTS_EQUIV * spacing ** 2
    if min_points_hard is None:
        d = []
        for f in facets:
            pts = np.asarray(f["points"], float)
            s_f = float(np.median(cov._nn(pts)))
            gross = float(facet_area(pts, f["normal"], cfg["alpha_mult"] * s_f))
            d.append(len(pts) * spacing ** 2 / max(gross, 1e-12))
        density = float(np.median(d))
        min_points_hard = int(round(MIN_AREA_POINTS_EQUIV * density))
    else:
        density = None

    cell = COVERAGE_CELL_MULT * s_full
    masks, g, _, dist_pre = cov.coverage_masks(points, facets, band, cell)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    log = []
    new = cov.recover_facets(points, blobs, None, dist_pre, band, s_full, bar,
                             alpha_mult=cfg["alpha_mult"], probability=1.0,
                             min_points_hard=min_points_hard,
                             min_area_hard=min_area, log=log, grid=g)
    allf = facets + new
    assert_single_ownership(allf, where="sweep_m1a")
    masks_post, _, _, _ = cov.coverage_masks(points, allf, band, cell)
    split = cov.split_coverage(masks_post, cell)
    return dict(facets=facets, recovered=new, band=band, s_full=s_full,
                bar=bar, ratios=ratios, cell=cell, blobs=blobs, log=log,
                dist_pre=dist_pre, split=split, planes=planes_seen,
                min_points_hard=min_points_hard, density=density,
                n_main=len(facets), n_recovered=len(new), n_total=len(allf))


# Cell (i, j) as one integer, for comparing blob cell SETS between runs. The
# plan grid is identical in every run (same points, same cell size), so the
# same (i, j) means the same patch of ground. 10**7 comfortably exceeds any
# grid dimension here.
CELL_ENCODE = 10 ** 7


def blob_cellset(blob):
    return set((blob["cells"][:, 0].astype(np.int64) * CELL_ENCODE +
                blob["cells"][:, 1].astype(np.int64)).tolist())


def best_candidate_quality(log, blob_index):
    """The best (lowest) fit quality any candidate plane achieved inside a
    blob, and whether any candidate was accepted. None if the blob produced no
    candidate at all, which is a different diagnosis from a bad one."""
    for e in log:
        if e["blob"] == blob_index:
            qs = [p["quality"] for p in e.get("planes", [])]
            if not qs:
                return None, False, e.get("skipped"), int(e.get("n_candidate", 0))
            return (float(min(qs)),
                    any(p["kept"] for p in e["planes"]), None,
                    int(e.get("n_candidate", 0)))
    return None, False, "blob absent", 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    ap.add_argument("--smoke", action="store_true",
                    help="baseline + one grid point only, to check the "
                         "harness before committing an hour to it")
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name
    out.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()

    cfg = load_config(args.dataset)
    raw = np.load(cfg["roof_path"])
    points = raw
    if cfg["level_tilt_deg"] is not None:
        points = level_cloud(raw, up_from_tilt(cfg["level_tilt_deg"],
                                               cfg["level_uphill_az_deg"]))
    spacing = median_nn_spacing(points)

    in_per_cu = 40.4541
    sc = out / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])

    print(f"  {len(points):,} points   spacing {spacing:.6f} cu   "
          f"1 cu = {in_per_cu:.4f} in")

    # ---------------- BASELINE, filter off ---------------------------------
    print("\n  BASELINE (filter off) ...", flush=True)
    t0 = time.perf_counter()
    base = run_once(points, cfg, spacing, None, 1.0)
    print(f"    {base['n_main']} main + {base['n_recovered']} recovered = "
          f"{base['n_total']}   bar {base['bar']:.4f}   "
          f"facet coverage {base['split']['facet_coverage']['pct']:.2f}%   "
          f"[{time.perf_counter() - t0:.0f} s]")

    base_centroids = [np.asarray(f["points"], float).mean(axis=0)
                      for f in base["facets"]]
    base_normals = [np.asarray(f["normal"], float) /
                    np.linalg.norm(f["normal"]) for f in base["facets"]]
    base_pitch = [float(f["pitch"]) for f in base["facets"]]
    base_npts = [len(f["points"]) for f in base["facets"]]
    base_expl = base["dist_pre"] <= base["band"]
    infl_cell = INFLATION_CELL_MULT * base["s_full"]
    base_infl = [extent_inflation(np.asarray(f["points"], float)[:, :2],
                                  infl_cell)[0] for f in base["facets"]]
    # blob 0 by AREA RANK in the baseline, then tracked by CELL OVERLAP in
    # every later run. Rank is not identity: if the residual changes, the
    # largest blob may be a different piece of roof, and comparing "blob 0" to
    # "blob 0" by rank would silently compare two different places.
    base_blob0_cells = (blob_cellset(base["blobs"][0])
                        if base["blobs"] else set())
    b0q, b0kept, b0note, b0n = best_candidate_quality(base["log"], 0)

    # ---------------- A0: does the baseline reproduce the canonical? -------
    checks = []
    canon_path = out / f"canonical-{CANONICAL_STAMP}.json"
    if canon_path.exists():
        cdoc = json.loads(canon_path.read_text())
        cmain = [r for r in cdoc["facets"] if r["kind"] == "main"]
        pts_ok = [(r["n_points"], n) for r, n in zip(cmain, base_npts)]
        pitch_ok = [(r["pitch_deg"], round(p, 4))
                    for r, p in zip(cmain, base_pitch)]
        a0 = (len(cmain) == len(base_npts)
              and all(a == b for a, b in pts_ok)
              and all(abs(a - b) < 1e-3 for a, b in pitch_ok))
        checks.append(dict(
            id="A0", passed=bool(a0),
            check="the filter-off BASELINE reproduces canonical-2026-07-26-r2 "
                  "main facets (point counts exactly, pitch to 1e-3 deg)",
            detail=dict(n_points=pts_ok, pitch=pitch_ok)))
    else:
        checks.append(dict(id="A0", passed=None,
                           check="baseline vs canonical-2026-07-26-r2",
                           detail="canonical artifact absent"))
    print(f"    A0 {'PASS' if checks[0]['passed'] else 'FAIL'}: baseline "
          f"reproduces canonical-{CANONICAL_STAMP}")

    base_plane_hex = [[float(v).hex() for v in n] for n in base["planes"]]
    ft = in_per_cu / 12.0

    grid = ([(SCALES[2], FRACS[0])] if args.smoke
            else [(s, q) for s in SCALES for q in FRACS])
    rows = []
    a1_fail, a2_fail, a4_fail, a5_fail = [], [], [], []
    tripwire = {}

    for gi, (scale, frac) in enumerate(grid):
        t0 = time.perf_counter()
        r = run_once(points, cfg, spacing, scale, frac)
        conn_cell = scale * r["s_full"]

        # ---- A4: facet identity. The discovery planes must be bit-identical.
        this_hex = [[float(v).hex() for v in n] for n in r["planes"]]
        if this_hex != base_plane_hex:
            a4_fail.append(dict(scale=scale, frac=frac))

        per_facet = []
        for k, f in enumerate(r["facets"]):
            fd = f["filter"]
            pts = np.asarray(f["points"], float)
            xy = pts[:, :2]
            c_new = pts.mean(axis=0)
            n_new = np.asarray(f["normal"], float)
            n_new = n_new / np.linalg.norm(n_new)
            c_old, n_old = base_centroids[k], base_normals[k]
            # Normals are sign-arbitrary out of SVD; align before differencing
            # or a 180 degree flip reads as a catastrophic rotation.
            if n_new @ n_old < 0:
                n_new_a = -n_new
            else:
                n_new_a = n_new

            # ---- THE TWO CHANNELS, reported separately (2026-07-28) --------
            dot = float(np.clip(n_new_a @ n_old, -1.0, 1.0))
            normal_change_deg = float(np.degrees(np.arccos(dot)))
            dc = c_new - c_old
            centroid_shift_in = float(np.linalg.norm(dc) * in_per_cu)
            # THE OFFSET CHANNEL: only the along-normal part moves the plane.
            # An in-plane centroid shift moves the anchor and nothing else.
            offset_channel_in = float(-(dc @ n_new_a) * in_per_cu)
            # THE ROTATION CHANNEL, evaluated at THIS facet's own stray radius
            # so the two are compared where the strays actually sit. Bound:
            # |(p - c_old).(n_new - n_old)| <= R * |n_new - n_old|.
            rem_idx = fd["removed_idx"]
            if len(rem_idx):
                rvec = points[rem_idx] - c_old
                r_stray = float(np.linalg.norm(rvec, axis=1).max())
            else:
                r_stray = 0.0
            rot_channel_in = float(r_stray * np.linalg.norm(n_new_a - n_old)
                                   * in_per_cu)

            # ---- A1: point-domain separation ------------------------------
            kept_pre = fd["kept_idx_premtrim"]
            mind = min_cross_distance(points[kept_pre][:, :2],
                                      points[rem_idx][:, :2])
            a1_ok = True if mind is None else (mind > conn_cell)
            if not a1_ok:
                a1_fail.append(dict(scale=scale, frac=frac, facet=k,
                                    min_dist=mind, conn_cell=conn_cell))
            # ---- A2: independent component count of the KEPT set ----------
            a2_n = independent_component_count(points[kept_pre][:, :2],
                                               conn_cell,
                                               origin=fd["origin"])
            a2_ok = (a2_n == fd["n_components_kept"])
            if not a2_ok:
                a2_fail.append(dict(scale=scale, frac=frac, facet=k,
                                    independent=a2_n,
                                    filter_said=fd["n_components_kept"]))
            # ---- A5: conservation -----------------------------------------
            a5_ok = (len(kept_pre) + len(rem_idx) == fd["n_points_in"]
                     and len(np.intersect1d(kept_pre, rem_idx)) == 0)
            if not a5_ok:
                a5_fail.append(dict(scale=scale, frac=frac, facet=k))

            infl, ncomp_at_fixed = extent_inflation(xy, infl_cell)
            per_facet.append(dict(
                facet=k,
                n_points=int(len(pts)), n_points_base=base_npts[k],
                kept_fraction=round(float(fd["kept_fraction"]), 6),
                removed_points=int(len(rem_idx)),
                n_components=int(fd["n_components"]),
                n_components_kept=int(fd["n_components_kept"]),
                count_area_agree=bool(fd["count_area_agree"]),
                second_over_largest=round(float(fd["second_over_largest"]), 8),
                extent_inflation=round(infl, 4),
                extent_inflation_base=round(base_infl[k], 4),
                pitch_deg=round(float(f["pitch"]), 4),
                pitch_deg_base=round(base_pitch[k], 4),
                pitch_delta_deg=round(float(f["pitch"]) - base_pitch[k], 4),
                # the two channels, never summed
                normal_change_deg=round(normal_change_deg, 4),
                centroid_shift_in=round(centroid_shift_in, 4),
                centroid_shift_normal_in=round(offset_channel_in, 4),
                rotation_at_stray_radius_in=round(rot_channel_in, 4),
                stray_radius_ft=round(r_stray * ft, 2),
                a1_min_cross_dist_cu=(None if mind is None else round(mind, 8)),
                a1_conn_cell_cu=round(conn_cell, 8),
                a1_passed=bool(a1_ok), a2_passed=bool(a2_ok),
                a5_passed=bool(a5_ok)))

        if abs(scale - TRIPWIRE_SCALE) < 1e-9:
            tripwire[str(frac)] = [p["removed_points"] for p in per_facet]

        # ---- P8: the residual pool --------------------------------------
        now_expl = r["dist_pre"] <= r["band"]
        newly_unexplained = int((base_expl & ~now_expl).sum())
        newly_explained = int((~base_expl & now_expl).sum())
        total_removed = sum(p["removed_points"] for p in per_facet)

        # ---- blob 0, tracked by CELL OVERLAP not by rank -----------------
        b0 = dict(found=False)
        if base_blob0_cells and r["blobs"]:
            best_i, best_ov = -1, 0
            for i, b in enumerate(r["blobs"]):
                ov = len(blob_cellset(b) & base_blob0_cells)
                if ov > best_ov:
                    best_i, best_ov = i, ov
            if best_i >= 0:
                q, kept, note, ncand = best_candidate_quality(r["log"], best_i)
                b0 = dict(found=True, matched_blob=best_i,
                          overlap_cells=int(best_ov),
                          overlap_fraction=round(
                              best_ov / max(len(base_blob0_cells), 1), 4),
                          area_cu2=round(float(r["blobs"][best_i]["area_cu2"]), 4),
                          best_candidate_quality=(None if q is None else round(q, 4)),
                          bar=round(float(r["bar"]), 4),
                          margin_to_bar=(None if q is None else round(q - r["bar"], 4)),
                          accepted=bool(kept), note=note, n_candidate=ncand)

        fc = r["split"]["facet_coverage"]
        dt = r["split"]["density_testable_fraction"]
        rows.append(dict(
            scale_mult=scale, min_component_frac=frac,
            connectivity_cell_cu=round(conn_cell, 8),
            n_main=r["n_main"], n_recovered=r["n_recovered"],
            n_total=r["n_total"],
            quality_bar=round(float(r["bar"]), 4),
            quality_bar_base=round(float(base["bar"]), 4),
            quality_bar_delta=round(float(r["bar"] - base["bar"]), 4),
            facet_coverage_pct=fc["pct"],
            facet_coverage_pct_base=base["split"]["facet_coverage"]["pct"],
            density_testable_pct=dt["pct"],
            min_points_hard=r["min_points_hard"],
            total_points_removed=total_removed,
            newly_unexplained_points=newly_unexplained,
            newly_explained_points=newly_explained,
            max_abs_pitch_delta_deg=round(
                max(abs(p["pitch_delta_deg"]) for p in per_facet), 4),
            max_normal_change_deg=round(
                max(p["normal_change_deg"] for p in per_facet), 4),
            max_offset_channel_in=round(
                max(abs(p["centroid_shift_normal_in"]) for p in per_facet), 4),
            max_rotation_channel_in=round(
                max(p["rotation_at_stray_radius_in"] for p in per_facet), 4),
            count_area_disagreements=[p["facet"] for p in per_facet
                                      if not p["count_area_agree"]],
            blob0=b0, per_facet=per_facet,
            seconds=round(time.perf_counter() - t0, 1)))

        print(f"  [{gi + 1:>2}/{len(grid)}] scale {scale:>4.1f}  frac "
              f"{frac:<7g}  main {r['n_main']} + rec {r['n_recovered']:>2} = "
              f"{r['n_total']:>2}   bar {r['bar']:.4f}   cov "
              f"{fc['pct']:.2f}%   maxdpitch "
              f"{rows[-1]['max_abs_pitch_delta_deg']:.4f}   removed "
              f"{total_removed:,}   [{rows[-1]['seconds']:.0f} s]", flush=True)
        del r
        gc.collect()

    # ---- A3: the no-op tripwire ------------------------------------------
    if tripwire:
        a3 = all(all(v > 0 for v in vals) for vals in tripwire.values())
        checks.append(dict(
            id="A3", passed=bool(a3),
            check=f"at connectivity scale {TRIPWIRE_SCALE} x spacing the "
                  f"filter removes a non-zero number of points from ALL 8 "
                  f"main facets. Contradicting this would contradict "
                  f"fragments-2026-07-27.json, a committed artifact written "
                  f"by different code; a filter that removes nothing "
                  f"everywhere produces a PERFECT PLATEAU and would be "
                  f"reported as success.",
            detail=tripwire))
    else:
        checks.append(dict(id="A3", passed=None,
                           check="no-op tripwire", detail="scale not in grid"))

    checks.append(dict(
        id="A1", passed=bool(not a1_fail),
        check="POINT-DOMAIN SEPARATION: for every facet at every grid point, "
              "the minimum plan distance between the KEPT set and the REMOVED "
              "set exceeds the connectivity scale. Uses raw XY and the output "
              "partition only (cKDTree); touches no cell index, no occupancy "
              "raster, no component label and no argmax.",
        n_failures=len(a1_fail), detail=a1_fail[:20]))
    checks.append(dict(
        id="A2", passed=bool(not a2_fail),
        check="component count of the KEPT set re-derived by a sparse cell "
              "adjacency graph + scipy.sparse.csgraph, versus the filter's "
              "dense raster scipy.ndimage.label",
        n_failures=len(a2_fail), detail=a2_fail[:20]))
    checks.append(dict(
        id="A4", passed=bool(not a4_fail),
        check="FACET IDENTITY: find_roof_planes runs on the seeded subsample "
              "before the filter, so the discovered plane list is bit-identical "
              "in all runs. If it is not, facet k is not the same surface "
              "across runs and every per-facet delta here is meaningless.",
        n_failures=len(a4_fail), detail=a4_fail[:20]))
    checks.append(dict(
        id="A5", passed=bool(not a5_fail),
        check="CONSERVATION: kept and removed are disjoint and sum to the "
              "pre-filter membership",
        n_failures=len(a5_fail), detail=a5_fail[:20]))

    # ---- PLATEAU ANALYSIS -------------------------------------------------
    # A plateau is a region over which THE ANSWER does not change. The answer
    # is taken to be the tuple of things the pass would adopt: the facet count,
    # the per-facet pitch (to 0.01 deg), facet coverage (to 0.01 pct) and the
    # quality bar (to 0.001). Two grid points are in the same plateau when
    # every one of those agrees.
    def answer_key(row):
        return (row["n_main"], row["n_recovered"],
                tuple(round(p["pitch_deg"], 2) for p in row["per_facet"]),
                round(row["facet_coverage_pct"], 2),
                round(row["quality_bar"], 3))

    groups = {}
    for row in rows:
        groups.setdefault(answer_key(row), []).append(
            (row["scale_mult"], row["min_component_frac"]))
    plateau = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    plateau_report = [dict(n_grid_points=len(v), grid_points=v,
                           n_main=k[0], n_recovered=k[1],
                           facet_coverage_pct=k[3], quality_bar=k[4])
                      for k, v in plateau]

    doc = dict(
        task="M1a connectivity filter: pre-registered plateau sweep",
        dataset=name, date=args.stamp,
        status="NOTHING ADOPTED. canonical-2026-07-26-r2 remains canonical and "
               "published facet coverage remains 88.40 pct. This artifact is a "
               "measurement, not a new baseline.",
        preregistration="decisions/2026-07-27-m1a-connectivity-preregistration.md",
        amendment="decisions/2026-07-28-m1a-preregistration-amendment.md",
        grid=dict(scales_x_spacing=SCALES, min_component_fractions=FRACS,
                  n_grid_points=len(grid),
                  inflation_measured_at_cell_mult=INFLATION_CELL_MULT,
                  inflation_note="extent inflation is measured at a FIXED cell "
                                 "whatever the sweep's connectivity scale is; "
                                 "measuring it with the knob that produced the "
                                 "filtering would be circular"),
        scale=dict(in_per_cu=in_per_cu, spacing_cu=round(float(spacing), 6)),
        baseline=dict(
            n_main=base["n_main"], n_recovered=base["n_recovered"],
            n_total=base["n_total"],
            quality_bar=round(float(base["bar"]), 4),
            facet_coverage_pct=base["split"]["facet_coverage"]["pct"],
            density_testable_pct=base["split"]["density_testable_fraction"]["pct"],
            min_points_hard=base["min_points_hard"],
            pitch_deg=[round(p, 4) for p in base_pitch],
            n_points=base_npts,
            extent_inflation=[round(v, 4) for v in base_infl],
            n_blobs=len(base["blobs"]),
            blob0=dict(area_cu2=(round(float(base["blobs"][0]["area_cu2"]), 4)
                                 if base["blobs"] else None),
                       best_candidate_quality=(None if b0q is None else round(b0q, 4)),
                       bar=round(float(base["bar"]), 4),
                       margin_to_bar=(None if b0q is None
                                      else round(b0q - base["bar"], 4)),
                       accepted=bool(b0kept), note=b0note, n_candidate=b0n)),
        cross_checks=checks,
        plateau=dict(
            definition="a plateau is a region over which THE ANSWER does not "
                       "change. The answer is (n_main, n_recovered, per-facet "
                       "pitch to 0.01 deg, facet coverage to 0.01 pct, quality "
                       "bar to 0.001).",
            n_distinct_answers=len(plateau_report),
            groups=plateau_report),
        rows=rows,
        wall_clock_s=round(time.perf_counter() - t_start, 1))
    p = out / f"m1a-sweep-{args.stamp}.json"
    p.write_text(json.dumps(doc, indent=2, default=float))

    print("\n  ASSERTIONS")
    for c in checks:
        mark = {True: "PASS", False: "FAIL", None: "SKIP"}[c["passed"]]
        print(f"    {c['id']} {mark}: {c['check'][:88]}")
    print(f"\n  distinct answers across the grid: {len(plateau_report)}")
    for pr in plateau_report[:6]:
        print(f"    {pr['n_grid_points']:>2} grid points  main {pr['n_main']} "
              f"+ rec {pr['n_recovered']:>2}  cov {pr['facet_coverage_pct']:.2f}%  "
              f"bar {pr['quality_bar']:.3f}   {pr['grid_points']}")
    print(f"\n  wrote {p}   [{doc['wall_clock_s']:.0f} s total]")


if __name__ == "__main__":
    main()
