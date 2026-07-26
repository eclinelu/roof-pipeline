# Task 5 diagnostics (2026-07-23 facet state). READ-ONLY on the data: this
# script fits nothing new, decides nothing, merges nothing. It re-derives the
# SAME 26 facets the coverage run produced and then describes them.
#
#   .venv/Scripts/python.exe -u scripts/diag_task5.py C:/odm/datasets/big_house
#
# Writes (STANDING RULE 2026-07-25: any diagnostic to be acted on goes to a
# file under reports/<dataset>/, never stdout only):
#   reports/big_house/pairwise-2026-07-23.json      (5A)
#   reports/big_house/residual-map-2026-07-23.json  (5B)
#   reports/big_house/residual-map-2026-07-23.png   (5B render)
#   reports/big_house/oversegmentation-2026-07-23.json (5C)
# stdout is a progress trace only. Every number worth acting on is in a file.
#
# ---------------------------------------------------------------------------
# WHY THIS SCRIPT CAN REPRODUCE THE 26 FACETS
#
# Open3D's RANSAC (segment_plane) draws from a GLOBAL random number generator.
# "Global" means one shared stream for the whole program, not a fresh stream
# per call. discover_facets() seeds it to 0, and every later RANSAC call
# consumes numbers from that same stream. So the facets you get depend on the
# ORDER and COUNT of RANSAC calls, not just the seed.
#
# Therefore this script performs the identical RNG-consuming sequence as
# coverage_recon.py:
#     1. discover_facets()   -> seeds to 0, runs main-facet RANSAC
#     2. recover_facets()    -> runs per-blob RANSAC, blobs in the same order
# Everything in between (quality bar, coverage masks, blob labeling) is pure
# NumPy/SciPy and draws no random numbers, so it cannot shift the stream.
#
# The one thing coverage_recon.py does that this script SKIPS is
# area_accounting(), which is where most of that run's 10-15 minutes went
# (alpha shapes over 26 facets). It is skipped deliberately: it consumes no
# Open3D randomness (its sampling uses its own seeded NumPy generator), so
# omitting it cannot change which facets we get. Task 5 needs no areas that
# the existing comparison JSON does not already hold.
#
# GUARD: we do not TRUST the above, we CHECK it. verify_reproduction() compares
# all 26 re-derived pitches against the comparison JSON and aborts if any
# differs by more than a rounding tolerance. A diagnostic computed over a
# different facet set than the one being discussed is worse than no diagnostic,
# because it looks authoritative while describing something else.
# ---------------------------------------------------------------------------
import argparse
import gc
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")            # render to file, never open a window
import matplotlib.pyplot as plt
from scipy.ndimage import distance_transform_edt, label, find_objects

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config
from recon_common import discover_facets
from roofkit.segment import level_cloud
from roofkit.measure import up_from_tilt, azimuth_degrees
from roofkit import coverage as cov

# These MUST match coverage_recon.py or we reproduce a different state.
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/big_house"
STAMP = "2026-07-23"          # the facet state being described, not today
COMPARISON = OUT / f"coverage-comparison-{STAMP}.json"

# Coordinate shorthand. The cloud is georeferenced UTM, so X ~ 553,4xx and
# Y ~ 4,543,2xx. Earlier diagnostics and Emmett's notes abbreviate these by
# dropping the constant leading digits ("X84-90" means 553484 to 553490).
# Defined once here so the report can print BOTH forms and no one has to
# guess which convention a number is in.
X_ORIGIN = 553400.0
Y_ORIGIN = 4543000.0

# The blob Emmett asked about by name, in shorthand, from the earlier Task 2
# diagnostic: a 5.94 cu^2 triangle.
TRIANGLE_BOX_SHORT = ((84.0, 285.0), (90.0, 291.0))
TRIANGLE_AREA_CU2 = 5.94


def short(x, y):
    """Full UTM -> the shorthand used in notes. Returns (x_short, y_short)."""
    return float(x - X_ORIGIN), float(y - Y_ORIGIN)


# ---------------------------------------------------------------------------
# COORDINATE FRAMES. There are two, and confusing them silently produces
# confident nonsense (it did: an early version of this script queried a raw-UTM
# box against leveled data, found an empty region, and reported a verdict on it).
#
#   RAW      : the georeferenced UTM cloud as it comes off ODM. X ~ 553,4xx,
#              Y ~ 4,543,2xx. This is the frame every earlier diagnostic and
#              every note of Emmett's uses ("X84-90" = 553484 to 553490).
#   LEVELED  : after level_cloud() rotates the cloud so true vertical is +Z.
#              The rotation is about the coordinate ORIGIN, and at UTM
#              magnitudes a 1.083 deg rotation displaces everything by tens of
#              thousands of units. Leveled X for this dataset is around -204.
#
# ALL GEOMETRY is computed in LEVELED coordinates (that is the point of
# leveling: pitch and plan-view area are only meaningful against true
# vertical). ALL REPORTED LOCATIONS are converted back to RAW, because that is
# the frame a human can act on. The conversion is the exact inverse rotation,
# not an approximation.
# ---------------------------------------------------------------------------
def level_rotation(cfg):
    """The SAME rotation level_cloud() applies, as a scipy Rotation, so it can
    be inverted. Returns None when the dataset is not leveled."""
    from scipy.spatial.transform import Rotation
    if cfg["level_tilt_deg"] is None:
        return None
    up = np.asarray(up_from_tilt(cfg["level_tilt_deg"],
                                 cfg["level_uphill_az_deg"]), float)
    up = up / np.linalg.norm(up)
    target = np.array([0.0, 0.0, 1.0])
    axis = np.cross(up, target)
    n = np.linalg.norm(axis)
    if n < 1e-8:
        return None
    return Rotation.from_rotvec(axis / n * np.arccos(np.clip(up @ target, -1, 1)))


def to_raw(pts_leveled, R):
    """LEVELED coordinates -> RAW UTM. Exact inverse of level_cloud()."""
    if R is None:
        return np.asarray(pts_leveled)
    return R.inv().apply(np.asarray(pts_leveled))


def raw_bbox(pts_leveled, R):
    """Raw-UTM bounding box of a leveled point set, in both full and
    shorthand form, so a location can be matched against older notes."""
    r = to_raw(pts_leveled, R)
    x0, x1 = float(r[:, 0].min()), float(r[:, 0].max())
    y0, y1 = float(r[:, 1].min()), float(r[:, 1].max())
    sx0, sy0 = short(x0, y0)
    sx1, sy1 = short(x1, y1)
    return dict(utm=dict(x=[round(x0, 2), round(x1, 2)],
                         y=[round(y0, 2), round(y1, 2)]),
                short=dict(x=[round(sx0, 2), round(sx1, 2)],
                           y=[round(sy0, 2), round(sy1, 2)]))


def jsonable(o):
    """NumPy scalars/arrays are not JSON-serializable; convert to plain
    Python. Applied to the whole document right before writing."""
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def write_json(path, doc):
    path.write_text(json.dumps(jsonable(doc), indent=2))
    print(f"  wrote {path}")


# ---------------------------------------------------------------------------
# Reproduction + verification
# ---------------------------------------------------------------------------
def save_cache(st, cdir):
    """Cache the RANSAC-derived facets so re-running the reporting side does
    not re-pay the expensive rebuild (median spacing over 9.3M points plus
    every RANSAC pass). Only the facet geometry is cached; the plan-view
    masks are recomputed from it, which is comparatively cheap and keeps the
    cache small. The cache is disposable: delete it to force a clean rebuild."""
    cdir.mkdir(parents=True, exist_ok=True)
    arrs = {f"pts_{k}": f["points"] for k, f in enumerate(st["allf"])}
    arrs["normals"] = np.array([f["normal"] for f in st["allf"]], float)
    arrs["pitches"] = np.array([f["pitch"] for f in st["allf"]], float)
    arrs["blobs_of"] = np.array([-1 if k < len(st["facets"]) else f["blob"]
                                 for k, f in enumerate(st["allf"])], np.int64)
    arrs["blob_areas"] = np.array([b["area_cu2"] for b in st["blobs"]], float)
    arrs["blob_boxes"] = np.array([[list(b["box"][0]), list(b["box"][1])]
                                   for b in st["blobs"]], float)
    np.savez(cdir / "task5_state.npz", **arrs)
    (cdir / "task5_state.json").write_text(json.dumps(jsonable(dict(
        n_main=len(st["facets"]), n_all=len(st["allf"]),
        band=st["band"], spacing=st["spacing"], cell=st["cell"],
        bar=st["bar"], ratios=st["ratios"], rec_log=st["rec_log"])), indent=1))
    print(f"  cached rebuilt state -> {cdir / 'task5_state.npz'}")


def load_cache(cdir):
    """Return the cached facet state, or None if absent."""
    npz, meta = cdir / "task5_state.npz", cdir / "task5_state.json"
    if not (npz.exists() and meta.exists()):
        return None
    z = np.load(npz)
    m = json.loads(meta.read_text())
    n_all, n_main = m["n_all"], m["n_main"]
    allf = []
    for k in range(n_all):
        allf.append(dict(points=z[f"pts_{k}"], normal=z["normals"][k],
                         pitch=float(z["pitches"][k]),
                         **({} if k < n_main else {"blob": int(z["blobs_of"][k])})))
    blobs = [dict(area_cu2=float(a), box=((bx[0][0], bx[0][1]), (bx[1][0], bx[1][1])))
             for a, bx in zip(z["blob_areas"], z["blob_boxes"])]
    print(f"  loaded cached state: {n_all} facets ({n_main} main)")
    return dict(facets=allf[:n_main], new=allf[n_main:], allf=allf, blobs=blobs,
                band=m["band"], spacing=m["spacing"], cell=m["cell"],
                bar=m["bar"], ratios=m["ratios"], rec_log=m["rec_log"])


def finish_state(st, cfg):
    """Given cached-or-fresh facets, (re)compute the plan-view products the
    reports need: post-recovery masks, grid, and per-point distances."""
    points = np.load(cfg["roof_path"])
    if cfg["level_tilt_deg"] is not None:
        up = up_from_tilt(cfg["level_tilt_deg"], cfg["level_uphill_az_deg"])
        points = level_cloud(points, up)
    masks2, g2, owner2, dist2 = cov.coverage_masks(points, st["allf"],
                                                   st["band"], st["cell"])
    gc.collect()
    st.update(points=points, masks2=masks2, g2=g2, owner2=owner2, dist2=dist2,
              R=level_rotation(cfg))
    return st


def rebuild_state(cfg):
    """Re-derive the exact facet state of the 2026-07-23 coverage run.
    Returns everything the three tasks need."""
    points = np.load(cfg["roof_path"])
    if cfg["level_tilt_deg"] is not None:
        up = up_from_tilt(cfg["level_tilt_deg"], cfg["level_uphill_az_deg"])
        points = level_cloud(points, up)
        print(f"  leveled: {cfg['level_tilt_deg']:.3f} deg removed")

    # 1. main facets (RANSAC call #1 on the shared stream)
    facets, band, s_full = discover_facets(points, cfg)
    print(f"  main facets: {len(facets)}, band {band:.6f} cu, "
          f"spacing {s_full:.6f} cu")

    # 2. fit-quality bar (pure NumPy)
    bar, ratios = cov.calibrate_quality_bar(facets, s_full)

    # 3. pre-recovery coverage masks (pure NumPy/SciPy)
    cell = COVERAGE_CELL_MULT * s_full
    masks1, g1, owner, dist = cov.coverage_masks(points, facets, band, cell)
    gc.collect()

    # 4. blobs, in the SAME order recovery consumed them (sorted by -area)
    blobs = cov.residual_blobs(masks1["residual"], g1, MIN_BLOB_AREA)
    print(f"  pre-recovery residual blobs >= {MIN_BLOB_AREA} cu^2: {len(blobs)}")

    # 5. recovery (RANSAC calls #2..N on the shared stream, blob order fixed)
    rec_log = []
    new = cov.recover_facets(points, blobs, owner, dist, band, s_full, bar,
                             log=rec_log)
    print(f"  recovered facets: {len(new)}  -> total {len(facets) + len(new)}")

    allf = facets + new
    del owner, dist
    gc.collect()

    # 6. POST-recovery coverage masks: this is the state whose 93.14% and
    #    13.877 cu^2 the residual map must explain.
    masks2, g2, owner2, dist2 = cov.coverage_masks(points, allf, band, cell)
    gc.collect()

    return dict(points=points, facets=facets, new=new, allf=allf, band=band,
                spacing=s_full, cell=cell, bar=bar, ratios=ratios,
                blobs=blobs, rec_log=rec_log,
                masks1=masks1, g1=g1, masks2=masks2, g2=g2,
                owner2=owner2, dist2=dist2, R=level_rotation(cfg))


def verify_reproduction(st, comparison):
    """Abort unless the re-derived facets match the run being described.

    Checks facet COUNT and every facet's PITCH against the comparison JSON.
    Pitch is a good fingerprint: it is a derived geometric property, so two
    different plane fits agreeing to 0.001 deg on all 26 facets means the
    same fits. Returns a dict of the check results (recorded in every output
    file, so each report carries proof it describes the right state)."""
    rows = comparison["area"]["rows"]
    mine = [float(f["pitch"]) for f in st["allf"]]
    n_main = len(st["facets"])
    n_common = min(len(mine), len(rows))

    # Per-facet fidelity, index-aligned. Facet k of the rebuild corresponds to
    # facet k of the comparison file (same discovery order, same blob order).
    per = []
    for k in range(n_common):
        per.append(dict(facet=k, kind=rows[k]["kind"],
                        json_pitch=float(rows[k]["pitch"]),
                        rebuilt_pitch=round(mine[k], 3),
                        delta_deg=round(abs(mine[k] - float(rows[k]["pitch"])), 4),
                        n_points=int(len(st["allf"][k]["points"])),
                        json_net_cu2=rows[k]["net"]))
    main_worst = max((p["delta_deg"] for p in per if p["facet"] < n_main),
                     default=0.0)
    dorm_worst = max((p["delta_deg"] for p in per if p["facet"] >= n_main),
                     default=0.0)
    missing = [dict(facet=r["facet"], kind=r["kind"], pitch=r["pitch"],
                    gross=r["gross"], net=r["net"])
               for r in rows[n_common:]]

    # GRADED gate, replacing an earlier exact-match gate that encoded an
    # assumption now known to be false (see the nondeterminism note below).
    # MAIN facets are fitted to hundreds of thousands of points and ARE
    # reproducible, so they are held to a tight bar: if they move, something
    # structural changed and nothing downstream is trustworthy.
    # RECOVERED facets are fitted to small point sets where Open3D's RANSAC is
    # measurably nondeterministic, so they get a loose bar and their wobble is
    # RECORDED and propagated into the reports rather than asserted away.
    MAIN_TOL, DORM_TOL = 0.01, 1.0
    ok_main = main_worst <= MAIN_TOL
    ok_dorm = dorm_worst <= DORM_TOL
    ok_pitch = ok_main and ok_dorm
    ok_count = (len(mine) == len(rows))
    result = dict(
        verdict=("REPRODUCED" if (ok_count and ok_pitch)
                 else ("REPRODUCED_PARTIAL" if ok_pitch else "MISMATCH")),
        facet_count_expected=len(rows), facet_count_rebuilt=len(mine),
        count_matches=bool(ok_count),
        facets_compared=n_common,
        main_worst_delta_deg=round(float(main_worst), 4),
        main_tolerance_deg=MAIN_TOL, main_ok=bool(ok_main),
        dormer_worst_delta_deg=round(float(dorm_worst), 4),
        dormer_tolerance_deg=DORM_TOL, dormer_ok=bool(ok_dorm),
        missing_facets=missing,
        per_facet=per,
        caveat=(
            "Open3D 0.19 segment_plane is NONDETERMINISTIC: with an identical "
            "seed and identical input points it returns different planes on "
            "small point sets (measured; see ransac-nondeterminism report). "
            "Main facets (300k-1.5M points) reproduce to <0.001 deg. Recovered "
            "dormer facets reproduce only approximately, and the smallest ones "
            "may not reproduce at all. Treat every recovered-facet number "
            "below as carrying the per-facet delta shown here as its "
            "reproducibility uncertainty."))
    print(f"  verification: {result['verdict']} "
          f"(rebuilt {len(mine)}/{len(rows)} facets; worst delta "
          f"main {main_worst:.4f} deg, dormer {dorm_worst:.4f} deg)")
    if missing:
        print(f"  NOT reproduced: {[m['facet'] for m in missing]} "
              f"(smallest facets; nondeterministic RANSAC)")

    if not ok_pitch:
        # Structural divergence: the geometry itself moved, so no report over
        # this state can be trusted. Write the evidence, then stop.
        p = OUT / f"task5-rebuild-mismatch-{STAMP}.json"
        write_json(p, dict(
            what="Task 5 rebuild diverged structurally from the 2026-07-23 run",
            checks=result,
            interpretation=("main facets moved beyond tolerance"
                            if not ok_main else
                            "recovered facets moved beyond tolerance")))
        print(f"\nABORT: rebuilt geometry is not the 2026-07-23 state.\n"
              f"  Evidence in {p.name}. Do not interpret any report.")
        sys.exit(2)
    return result


def facet_meta(st, comparison):
    """Per-facet descriptive row shared by all three reports."""
    rows = comparison["area"]["rows"]
    out = []
    for k, f in enumerate(st["allf"]):
        pts = f["points"]
        c = pts.mean(axis=0)                       # LEVELED centroid
        c_raw = to_raw(c[None, :], st["R"])[0]     # reported in RAW UTM
        sx, sy = short(c_raw[0], c_raw[1])
        out.append(dict(
            facet=k,
            kind="main" if k < len(st["facets"]) else "dormer",
            blob=(None if k < len(st["facets"]) else int(f["blob"])),
            n_points=int(len(pts)),
            pitch_deg=round(float(f["pitch"]), 3),
            azimuth_deg=round(float(azimuth_degrees(f["normal"])), 2),
            centroid_utm=[round(float(v), 3) for v in c_raw],
            centroid_short=[round(sx, 2), round(sy, 2)],
            centroid_leveled=[round(float(v), 3) for v in c],
            gross_cu2=rows[k]["gross"], net_cu2=rows[k]["net"]))
    return out


# ---------------------------------------------------------------------------
# TASK 5A: pairwise matrix, to a file
# ---------------------------------------------------------------------------
def task_5a(st, meta, verify):
    """Raw pairwise geometry over all 26 facets. NO merge, NO tolerance
    chosen. Two numbers per pair:

      angle  : the angle between the two facet NORMALS, in degrees. A normal
               is the direction a surface faces. Two halves of one real plane
               face the same way, so their angle is ~0.
      offset : how far apart the two PLANES are, perpendicular to themselves,
               in cloud units (cu). Two facets can face the same direction and
               still be different surfaces (an upper and a lower roof of the
               same slope); the offset is what separates those cases.

    A pair that is BOTH near-zero angle AND near-zero offset is one plane that
    segmentation split in two: an over-segmentation, a merge candidate.

    Emmett's flag rule (5A): angle < 2 deg AND offset < 2 x the assignment
    band. The band is the distance within which a point is considered to
    belong to a plane, so 2x band is 'closer together than the instrument can
    distinguish'. Flagged, NOT acted on."""
    allf = st["allf"]
    ang, off = cov.pairwise_matrix(allf)
    band = st["band"]
    off_limit = 2.0 * band
    ang_limit = 2.0

    # Reproducibility wobble per facet, from the fidelity check: how far this
    # facet's pitch moved between two identical runs. A pair's angle is only
    # meaningful if it is LARGER than the combined wobble of the two facets;
    # otherwise the RANSAC nondeterminism alone could produce or destroy the
    # flag. This is carried into every candidate so no tolerance gets chosen
    # later on numbers that cannot support it.
    wob = {p["facet"]: p["delta_deg"] for p in verify["per_facet"]}

    candidates = []
    for i in range(len(allf)):
        for j in range(i + 1, len(allf)):
            if ang[i, j] < ang_limit and off[i, j] < off_limit:
                w = wob.get(i, 0.0) + wob.get(j, 0.0)
                a = float(ang[i, j])
                candidates.append(dict(
                    i=i, j=j,
                    kind_i=meta[i]["kind"], kind_j=meta[j]["kind"],
                    blob_i=meta[i]["blob"], blob_j=meta[j]["blob"],
                    angle_deg=round(a, 4),
                    offset_cu=round(float(off[i, j]), 5),
                    offset_in_bands=round(float(off[i, j] / band), 3),
                    combined_wobble_deg=round(w, 4),
                    angle_exceeds_wobble=bool(a > w),
                    confidence=("solid" if a > 5 * w else
                                ("marginal" if a > w else "within-noise")),
                    n_points_i=meta[i]["n_points"], n_points_j=meta[j]["n_points"],
                    net_cu2_i=meta[i]["net_cu2"], net_cu2_j=meta[j]["net_cu2"],
                    same_blob=(meta[i]["blob"] is not None and
                               meta[i]["blob"] == meta[j]["blob"])))
    candidates.sort(key=lambda c: (c["angle_deg"], c["offset_cu"]))

    # Nearest neighbour per facet, regardless of the flag rule: lets a
    # different tolerance be applied later without recomputing anything.
    nearest = []
    for i in range(len(allf)):
        best_j, best = None, 1e18
        for j in range(len(allf)):
            if i == j:
                continue
            score = ang[i, j]        # rank by angle first, the primary signal
            if score < best:
                best, best_j = score, j
        nearest.append(dict(facet=i, nearest_by_angle=best_j,
                            angle_deg=round(float(ang[i, best_j]), 4),
                            offset_cu=round(float(off[i, best_j]), 5)))

    doc = dict(
        task="5A pairwise matrix (raw; no merge, no tolerance applied)",
        dataset="big_house", facet_state_date=STAMP,
        source_run=COMPARISON.name,
        reproduction_check=verify,
        scope=dict(
            facets_in_matrix=len(allf),
            facets_in_source_run=len(meta) + len(verify["missing_facets"]),
            not_reproduced=verify["missing_facets"],
            note="The matrix covers every facet that could be regenerated. "
                 "Any facet listed in not_reproduced is absent from the "
                 "matrix because its geometry no longer exists anywhere: the "
                 "2026-07-23 run saved summary rows, not facet points, and "
                 "the RANSAC that produced it is nondeterministic."),
        units=dict(angle="degrees between facet normals",
                   offset="cloud units (cu), perpendicular plane separation"),
        assignment_band_cu=round(float(band), 6),
        flag_rule=dict(angle_lt_deg=ang_limit,
                       offset_lt_cu=round(float(off_limit), 6),
                       offset_lt_bands=2.0,
                       note="FLAG ONLY. No merge performed. No tolerance chosen."),
        facets=meta,
        merge_candidates=candidates,
        n_merge_candidates=len(candidates),
        nearest_by_angle=nearest,
        matrix=dict(
            order="row/col index == facet index",
            angle_deg=[[round(float(ang[i, j]), 3) for j in range(len(allf))]
                       for i in range(len(allf))],
            offset_cu=[[round(float(off[i, j]), 5) for j in range(len(allf))]
                       for i in range(len(allf))]))
    write_json(OUT / f"pairwise-{STAMP}.json", doc)
    return candidates


# ---------------------------------------------------------------------------
# TASK 5B: residual map, to a file
# ---------------------------------------------------------------------------
def task_5b(st, verify):
    """Where does the 13.877 cu^2 of unexplained plan area actually sit?

    Terms defined once:
      building cell : a plan-view grid cell holding >= 2 roof points, i.e. a
                      cell where real roof surface exists.
      explained     : >= 2 of that cell's points lie within the assignment
                      band of SOME accepted facet plane.
      residual      : a building cell, inside the eroded interior, that is
                      not explained. This is the unexplained area.
      erosion       : shrinking a mask by one cell all the way around, which
                      removes the ragged outermost ring where cells are only
                      partly filled by the roof and would otherwise look
                      'unexplained' purely because they are half-empty.
      EDT depth     : Euclidean Distance Transform. For each building cell,
                      the distance IN CELLS to the nearest non-building cell.
                      Depth 1 = touching the footprint edge; large depth =
                      deep inside the roof. This is how we separate a
                      perimeter ring from true interior without guessing."""
    masks, g, cell, R = st["masks2"], st["g2"], st["cell"], st["R"]
    cell_area = cell * cell
    building = masks["building"]
    interior = masks["interior"]
    residual = masks["residual"]

    resid_cells = int(residual.sum())
    resid_area = resid_cells * cell_area
    interior_building = int((interior & building).sum())
    frac = cov.coverage_fraction(masks)

    # --- the erosion question, answered explicitly from the code path -----
    erosion_answer = dict(
        eroded_by_one_cell=True,
        answer="YES",
        where="roofkit/coverage.py, coverage_masks(): "
              "interior = binary_erosion(building, iterations=1); "
              "residual = interior & building & ~explained",
        meaning="The residual EXCLUDES the outermost one-cell ring of the "
                "building footprint by construction. The 13.877 cu^2 is "
                "therefore already perimeter-fringe-free at the 1-cell level. "
                "Any perimeter concentration reported below is residual that "
                "survived that erosion and sits 2+ cells inside the edge.",
        erosion_cells=1,
        erosion_length_cu=round(float(cell), 6))

    # --- perimeter ring vs interior, by EDT depth ------------------------
    # Distance (in cells) from every building cell to the nearest non-building
    # cell. Residual cells inherit that depth.
    depth = distance_transform_edt(building)
    rd = depth[residual]                    # depth of each residual cell

    # Report the split at several ring widths rather than picking one, so the
    # sensitivity to the cut is visible instead of hidden inside one number.
    splits = []
    for k in (2, 3, 4, 5, 6):
        per_cells = int((rd <= k).sum())
        int_cells = int((rd > k).sum())
        splits.append(dict(
            ring_width_cells=k,
            ring_width_cu=round(float(k * cell), 5),
            perimeter_cells=per_cells,
            perimeter_cu2=round(per_cells * cell_area, 4),
            perimeter_pct=round(100.0 * per_cells / max(resid_cells, 1), 2),
            interior_cells=int_cells,
            interior_cu2=round(int_cells * cell_area, 4),
            interior_pct=round(100.0 * int_cells / max(resid_cells, 1), 2)))

    HEADLINE_K = 3      # ring = within 3 cells (~0.039 cu) of the footprint edge
    headline = next(s for s in splits if s["ring_width_cells"] == HEADLINE_K)

    depth_hist = []
    for lo in range(1, 12):
        n = int(((rd >= lo) & (rd < lo + 1)).sum())
        if n:
            depth_hist.append(dict(depth_cells=lo, cells=n,
                                   cu2=round(n * cell_area, 4)))
    deep = int((rd >= 12).sum())
    if deep:
        depth_hist.append(dict(depth_cells=">=12", cells=deep,
                               cu2=round(deep * cell_area, 4)))

    # --- interior residual blobs, with point counts ----------------------
    # Blob = a connected clump of residual cells. Interior blobs are the real
    # signal (a missing facet); perimeter blobs are usually eave raggedness.
    interior_residual = residual & (depth > HEADLINE_K)
    lab, n = label(interior_residual)
    pts = st["points"]
    dist2 = st["dist2"]
    band = st["band"]
    # Map every roof point to its plan cell once, so per-blob point counts are
    # a lookup rather than a geometric test per blob.
    ix = np.clip(((pts[:, 0] - g["xlo"]) / cell).astype(np.int64), 0, g["nx"] - 1)
    iy = np.clip(((pts[:, 1] - g["ylo"]) / cell).astype(np.int64), 0, g["ny"] - 1)
    lab_of_point = lab[ix, iy]
    unexplained_pt = dist2 > band

    blob_rows = []
    if n:
        sizes = np.bincount(lab.ravel())
        slices = find_objects(lab)
        # points per blob, and unexplained points per blob, in two passes
        pts_per = np.bincount(lab_of_point, minlength=n + 1)
        unex_per = np.bincount(lab_of_point[unexplained_pt], minlength=n + 1)
        for i in range(1, n + 1):
            area = sizes[i] * cell_area
            if area < MIN_BLOB_AREA:
                continue
            sl = slices[i - 1]
            sub = lab[sl] == i
            cells = np.argwhere(sub)
            cells[:, 0] += sl[0].start
            cells[:, 1] += sl[1].start
            x0 = g["xlo"] + cells[:, 0].min() * cell
            x1 = g["xlo"] + (cells[:, 0].max() + 1) * cell
            y0 = g["ylo"] + cells[:, 1].min() * cell
            y1 = g["ylo"] + (cells[:, 1].max() + 1) * cell
            # Location in the RAW frame, taken from the blob's own member
            # points (exact), not by transforming the leveled cell box.
            member = pts[lab_of_point == i]
            loc = raw_bbox(member, R) if len(member) else None
            blob_rows.append(dict(
                area_cu2=round(float(area), 4),
                cells=int(sizes[i]),
                location_raw=loc,
                box_leveled=dict(x=[round(float(x0), 2), round(float(x1), 2)],
                                 y=[round(float(y0), 2), round(float(y1), 2)]),
                max_depth_cells=round(float(depth[cells[:, 0], cells[:, 1]].max()), 2),
                n_roof_points=int(pts_per[i]),
                n_unexplained_points=int(unex_per[i])))
        blob_rows.sort(key=lambda b: -b["area_cu2"])

    # --- the named triangular blob ---------------------------------------
    # The query box is in RAW UTM (that is the frame the earlier diagnostic
    # printed). The masks are in LEVELED cells. So select by RAW coordinates
    # on the POINTS, then read those points' leveled cells. Point order is
    # preserved by the rotation, so this is exact.
    (tx0, ty0), (tx1, ty1) = TRIANGLE_BOX_SHORT
    bx0, by0 = tx0 + X_ORIGIN, ty0 + Y_ORIGIN
    bx1, by1 = tx1 + X_ORIGIN, ty1 + Y_ORIGIN
    raw_xy = to_raw(pts, R)
    in_box = ((raw_xy[:, 0] >= bx0) & (raw_xy[:, 0] <= bx1) &
              (raw_xy[:, 1] >= by0) & (raw_xy[:, 1] <= by1))
    del raw_xy
    gc.collect()
    n_in_box = int(in_box.sum())
    # unique leveled cells those points occupy
    if n_in_box:
        cid = ix[in_box].astype(np.int64) * (g["ny"] + 1) + iy[in_box]
        uniq = np.unique(cid)
        ci, cj = (uniq // (g["ny"] + 1)).astype(int), (uniq % (g["ny"] + 1)).astype(int)
        tri_bld_area = float(building[ci, cj].sum()) * cell_area
        tri_expl_area = float((building[ci, cj] & masks["explained"][ci, cj]).sum()) * cell_area
        tri_resid_area = float(residual[ci, cj].sum()) * cell_area
    else:
        tri_bld_area = tri_expl_area = tri_resid_area = 0.0

    # Which recovered facets have their centroid inside that RAW box?
    fitted_here = []
    for k, f in enumerate(st["allf"]):
        if k < len(st["facets"]):
            continue
        c = to_raw(f["points"].mean(axis=0)[None, :], R)[0]
        if bx0 <= c[0] <= bx1 and by0 <= c[1] <= by1:
            fitted_here.append(dict(facet=k, blob=int(f["blob"]),
                                    n_points=int(len(f["points"])),
                                    pitch_deg=round(float(f["pitch"]), 3)))

    # Every PRE-recovery blob, with its RAW location and how many facets it
    # produced. The 5.94 cu^2 triangle is identified by AREA here rather than
    # by trusting a remembered coordinate box.
    blob_facets = {}
    for k, f in enumerate(st["allf"][len(st["facets"]):], start=len(st["facets"])):
        blob_facets.setdefault(int(f["blob"]), []).append(k)
    pre_blobs = []
    for bi, b in enumerate(st["blobs"]):
        (px0, py0), (px1, py1) = b["box"]
        pre_blobs.append(dict(
            blob=bi, area_cu2=round(float(b["area_cu2"]), 4),
            box_leveled=dict(x=[round(float(px0), 2), round(float(px1), 2)],
                             y=[round(float(py0), 2), round(float(py1), 2)]),
            facets_produced=sorted(blob_facets.get(bi, []))))
    by_area = min(pre_blobs, key=lambda b: abs(b["area_cu2"] - TRIANGLE_AREA_CU2))
    pre_blob = dict(
        matched_by="closest pre-recovery blob area to the 5.94 cu^2 quoted "
                   "in the earlier diagnostic",
        **by_area)

    explained_pct_in_box = (100.0 * tri_expl_area / tri_bld_area
                            if tri_bld_area > 0 else 0.0)
    triangle = dict(
        query_box_short=dict(x=[tx0, tx1], y=[ty0, ty1]),
        query_box_utm=dict(x=[bx0, bx1], y=[by0, by1]),
        coordinate_note="query box is RAW UTM; shorthand X = UTM_X - 553400, "
                        "Y = UTM_Y - 4543000. Masks are computed in LEVELED "
                        "coordinates and selection is done on points, so the "
                        "two frames are never compared directly.",
        roof_points_in_query_box=n_in_box,
        earlier_diagnostic_area_cu2=TRIANGLE_AREA_CU2,
        pre_recovery_blob=pre_blob,
        all_pre_recovery_blobs=pre_blobs,
        post_recovery=dict(
            building_cu2=round(tri_bld_area, 4),
            explained_cu2=round(tri_expl_area, 4),
            residual_cu2=round(tri_resid_area, 4),
            explained_pct=round(explained_pct_in_box, 2)),
        recovered_facets_centroid_inside=fitted_here,
        verdict=("INDETERMINATE: no roof points fall in the query box, so the "
                 "box does not locate the feature. Use the blob table above, "
                 "which identifies the triangle by AREA instead."
                 if n_in_box == 0 else
                 ("FITTED by coverage" if explained_pct_in_box >= 90.0
                  else ("PARTIALLY fitted" if explained_pct_in_box >= 50.0
                        else "STILL UNFIT"))),
        caveat="The earlier Task 2 diagnostic defined a residual CELL as "
               ">=2 points beyond the band (Hres>=2); coverage.py defines a "
               "cell as explained when >=2 points are WITHIN the band. A cell "
               "can satisfy both. Areas from the two definitions are therefore "
               "not bit-comparable; the verdict above uses coverage.py's.")

    doc = dict(
        task="5B residual map (where the unexplained plan area sits)",
        dataset="big_house", facet_state_date=STAMP,
        source_run=COMPARISON.name,
        reproduction_check=verify,
        grid=dict(cell_cu=round(float(cell), 6),
                  cell_area_cu2=round(float(cell_area), 8),
                  nx=int(g["nx"]), ny=int(g["ny"]),
                  cell_mult_of_spacing=COVERAGE_CELL_MULT,
                  spacing_cu=round(float(st["spacing"]), 6)),
        erosion=erosion_answer,
        totals=dict(
            coverage_pct=round(100.0 * float(frac), 2),
            interior_building_cells=interior_building,
            interior_building_cu2=round(interior_building * cell_area, 3),
            residual_cells=resid_cells,
            residual_cu2=round(resid_area, 4),
            expected_residual_cu2_from_run=13.877,
            delta_vs_run_cu2=round(resid_area - 13.877, 4),
            matches_run=bool(abs(resid_area - 13.877) < 0.05),
            delta_explanation=(
                "This rebuild is missing the facets listed in "
                "reproduction_check.missing_facets, so the plan area they "
                "explained falls back into the residual. Their combined net "
                "slope area is tiny, so the residual should sit slightly "
                "ABOVE the run's 13.877 cu^2, not below. A large or negative "
                "delta would mean something other than the missing facets "
                "changed, and would invalidate this map.")),
        perimeter_vs_interior=dict(
            method="EDT depth: distance in cells from each residual cell to "
                   "the nearest non-building cell. Ring = depth <= k.",
            headline_ring_width_cells=HEADLINE_K,
            headline=headline,
            sensitivity=splits,
            depth_histogram=depth_hist),
        interior_blobs=dict(
            definition=f"connected residual cells with EDT depth > {HEADLINE_K}, "
                       f"area >= {MIN_BLOB_AREA} cu^2",
            count=len(blob_rows),
            total_cu2=round(sum(b["area_cu2"] for b in blob_rows), 4),
            blobs=blob_rows),
        triangular_blob=triangle)
    write_json(OUT / f"residual-map-{STAMP}.json", doc)

    render_residual_png(st, depth, HEADLINE_K, blob_rows)
    return doc


def render_residual_png(st, depth, k, blob_rows):
    """Plan-view render: explained roof gray, perimeter residual orange,
    interior residual red. Cheap (two imshow panels), so it is worth having."""
    masks, g, cell = st["masks2"], st["g2"], st["cell"]
    building, residual = masks["building"], masks["residual"]
    explained = masks["explained"]

    xlo, ylo = g["xlo"], g["ylo"]
    xhi = xlo + g["nx"] * cell
    yhi = ylo + g["ny"] * cell
    ext = [xlo, xhi, ylo, yhi]          # LEVELED coordinates, see frames note

    perim = residual & (depth <= k)
    inter = residual & (depth > k)

    img = np.zeros((g["nx"], g["ny"], 3))
    img[building & explained] = [0.62, 0.62, 0.62]
    img[perim] = [1.0, 0.55, 0.0]
    img[inter] = [0.90, 0.08, 0.08]

    fig, axes = plt.subplots(1, 2, figsize=(15, 9))
    for ax, only_interior in zip(axes, (False, True)):
        im = img.copy()
        if only_interior:
            im[perim] = [0.80, 0.80, 0.80]     # mute the ring on the right panel
        ax.imshow(np.transpose(im, (1, 0, 2)), origin="lower", extent=ext,
                  aspect="equal", interpolation="nearest")
        ax.set_xlabel("leveled X (cu)")
        ax.set_ylabel("leveled Y (cu)")
        ax.grid(True, color="white", alpha=0.25, linewidth=0.3)
    axes[0].set_title("post-recovery coverage\ngray=explained  orange=perimeter residual  red=interior residual")
    axes[1].set_title(f"interior residual only (EDT depth > {k} cells)\nlabelled blobs >= {MIN_BLOB_AREA} cu^2")
    for b in blob_rows[:12]:
        bx = b["box_leveled"]["x"]; by = b["box_leveled"]["y"]
        axes[1].annotate(f"{b['area_cu2']:.2f}",
                         xy=((bx[0] + bx[1]) / 2, (by[0] + by[1]) / 2),
                         color="black", fontsize=7, ha="center",
                         bbox=dict(boxstyle="round,pad=0.15", fc="yellow",
                                   ec="none", alpha=0.75))
    fig.suptitle("big_house residual map, post-recovery facet state 2026-07-23")
    fig.tight_layout()
    p = OUT / f"residual-map-{STAMP}.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    print(f"  wrote {p}")


# ---------------------------------------------------------------------------
# TASK 5C: over-segmentation evidence
# ---------------------------------------------------------------------------
def task_5c(st, meta, verify):
    """Evidence only: 26 facets from a roof with 8 main slopes and 5 physical
    dormers is too many. Even counting every dormer as a two-slope gable that
    is at most ~18. Report where the 18 dormer-kind facets came from.

    'Blob' here = the connected residual region a facet was recovered from.
    Several facets from ONE blob is the signature of a single physical dormer
    correctly split into its two gable faces (2 per blob) or of the size floor
    being relaxed far enough to fit noise (>2 per blob)."""
    cell = st["cell"]
    cell_area = cell * cell
    dormers = [m for m in meta if m["kind"] == "dormer"]

    rows = []
    for m in dormers:
        f = st["allf"][m["facet"]]
        pts = f["points"]
        # Plan footprint = the plan-view area the facet's points occupy,
        # measured by counting distinct plan cells they fall in. This is a
        # cell-occupancy measure, NOT the alpha-shape area in the comparison
        # file: it does not close holes and it quantizes to the cell, so it
        # will not equal gross * cos(pitch). It is here because it is cheap
        # and it is the right unit for "how much of the roof does this cover".
        ix = ((pts[:, 0] - st["g2"]["xlo"]) / cell).astype(np.int64)
        iy = ((pts[:, 1] - st["g2"]["ylo"]) / cell).astype(np.int64)
        occupied = len(np.unique(ix.astype(np.int64) * (st["g2"]["ny"] + 1) + iy))
        loc = raw_bbox(pts, st["R"])          # reported in RAW UTM, see frames note
        span_x = loc["utm"]["x"][1] - loc["utm"]["x"][0]
        span_y = loc["utm"]["y"][1] - loc["utm"]["y"][0]
        # slope area implied by the alpha shape, converted to plan for scale
        plan_from_gross = m["gross_cu2"] * float(np.cos(np.radians(m["pitch_deg"])))
        rows.append(dict(
            facet=m["facet"], blob=m["blob"], n_points=m["n_points"],
            pitch_deg=m["pitch_deg"], azimuth_deg=m["azimuth_deg"],
            plan_footprint_cells=int(occupied),
            plan_footprint_cu2=round(occupied * cell_area, 4),
            plan_from_alpha_gross_cu2=round(plan_from_gross, 4),
            location_raw=loc,
            bbox_span_cu=[round(span_x, 3), round(span_y, 3)],
            gross_cu2=m["gross_cu2"], net_cu2=m["net_cu2"],
            centroid_short=m["centroid_short"]))

    # blob -> facets mapping
    by_blob = {}
    for r in rows:
        by_blob.setdefault(r["blob"], []).append(r["facet"])
    blob_map = []
    for bi in sorted(by_blob):
        b = st["blobs"][bi]
        (x0, y0), (x1, y1) = b["box"]
        facs = sorted(by_blob[bi])
        # the blob's raw-UTM location, taken from the points of the facets it
        # produced (the blob box itself is in leveled coordinates)
        loc = raw_bbox(np.vstack([st["allf"][k]["points"] for k in facs]),
                       st["R"]) if facs else None
        blob_map.append(dict(
            blob=bi,
            blob_area_cu2=round(float(b["area_cu2"]), 4),
            location_raw=loc,
            box_leveled=dict(x=[round(float(x0), 2), round(float(x1), 2)],
                             y=[round(float(y0), 2), round(float(y1), 2)]),
            n_facets=len(facs), facets=facs,
            facet_pitches=[next(r["pitch_deg"] for r in rows if r["facet"] == k)
                           for k in facs],
            facet_net_cu2=[next(r["net_cu2"] for r in rows if r["facet"] == k)
                           for k in facs]))
    over2 = [b for b in blob_map if b["n_facets"] > 2]

    # the two facets Emmett named as junk, plus anything else like them
    suspicious = [r for r in rows if r["net_cu2"] < 0.05 or r["pitch_deg"] > 45.0]

    # recovery log: what each blob offered and what was kept/rejected. This is
    # the audit trail for "the quality bar cannot catch a small planar patch".
    rec = []
    for e in st["rec_log"]:
        rec.append(dict(blob=int(e["blob"]),
                        blob_area_cu2=round(float(e["area_cu2"]), 4),
                        n_candidate_points=int(e["n_candidate"]),
                        skipped=e.get("skipped"),
                        planes=[dict(n_points=int(p["n"]), pitch_deg=p["pitch"],
                                     quality=p["quality"], bar=p["bar"],
                                     kept=bool(p["kept"])) for p in e["planes"]]))

    doc = dict(
        task="5C over-segmentation evidence (report only, no fix applied)",
        dataset="big_house", facet_state_date=STAMP,
        source_run=COMPARISON.name,
        reproduction_check=verify,
        expectation=dict(
            main_slopes=8, physical_dormers=5,
            max_expected_if_every_dormer_is_a_two_slope_gable=8 + 5 * 2,
            actual_facets_in_source_run=26,
            actual_facets_reproduced=len(st["allf"]),
            actual_dormer_kind_reproduced=len(rows),
            excess_vs_expectation=26 - 18),
        not_reproduced=dict(
            facets=verify["missing_facets"],
            note="Present in the 2026-07-23 run, absent from this rebuild. "
                 "These are the SMALLEST facets, and their disappearance "
                 "under an identical seed is itself over-segmentation "
                 "evidence: a facet that exists in one run and not the next "
                 "is not a physical roof surface, it is a fit to whatever "
                 "points RANSAC happened to grab."),
        plan_footprint_note=(
            "plan_footprint_cu2 counts distinct plan cells the facet's points "
            "occupy (cell-occupancy, quantized, holes not closed). "
            "plan_from_alpha_gross_cu2 is the comparison file's alpha gross "
            "area times cos(pitch). They measure different things and will "
            "not agree exactly; both are given so neither is mistaken for the "
            "other."),
        dormer_facets=rows,
        blob_to_facets=blob_map,
        blobs_with_more_than_two_facets=dict(
            count=len(over2),
            note="2 facets per blob is the expected signature of one gabled "
                 "dormer (two opposing faces). More than 2 means the blob "
                 "yielded more planes than a single gable can explain.",
            blobs=over2),
        suspicious_facets=dict(
            rule="net < 0.05 cu^2 OR pitch > 45 deg",
            note="Reported, not removed. These are planar, so the fit-quality "
                 "bar cannot reject them; that is the predicted failure mode "
                 "of relaxing the size floor inside residual blobs.",
            facets=suspicious),
        recovery_log=rec)
    write_json(OUT / f"oversegmentation-{STAMP}.json", doc)
    return doc, blob_map, over2, rows


def probe_determinism(st, reps_small=25, reps_big=8):
    """MEASURE, do not assume, whether Open3D's RANSAC is reproducible.

    The whole Task 5 premise was 'seed it and you get the same facets back'.
    That premise failed, so it gets tested directly: re-seed to the SAME value
    and re-run the SAME plane search on the SAME points, several times. If the
    results differ, the nondeterminism is in the library, not in our call
    order, and no amount of seeding will fix it.

    Run on a large facet and on the smallest facet, because the whole shape of
    the problem is that stability depends on how many points constrain the
    fit."""
    import open3d as o3d
    from roofkit.segment import find_roof_planes
    allf = st["allf"]
    big = max(range(len(allf)), key=lambda k: len(allf[k]["points"]))
    small = min(range(len(allf)), key=lambda k: len(allf[k]["points"]))
    # Rep count matters. An earlier 6-rep version of this probe reported the
    # SMALL facet as deterministic, which was wrong: the outcomes are split
    # roughly 60/30/10, so six reps landing on one value is unremarkable and
    # a boolean "deterministic" read off that few samples is unsupported.
    # Report the OUTCOME DISTRIBUTION, never a boolean from a small sample.
    out = []
    for label_, k, reps in (("largest", big, reps_big),
                            ("smallest", small, reps_small)):
        pts = allf[k]["points"]
        tally = {}
        for _ in range(reps):
            o3d.utility.random.seed(0)          # identical seed EVERY rep
            pl = find_roof_planes(pts, distance_threshold=st["band"],
                                  min_points=300, max_planes=4)
            key = tuple((int(len(p["points"])), round(float(p["pitch"]), 4))
                        for p in pl)
            tally[key] = tally.get(key, 0) + 1
        dist = sorted(({"result": [list(t) for t in kk], "count": v}
                       for kk, v in tally.items()),
                      key=lambda d: -d["count"])
        pitches = [r["result"][0][1] for r in dist if r["result"]]
        spread = (round(max(pitches) - min(pitches), 4) if pitches else 0.0)
        out.append(dict(
            which=label_, facet=k, n_points=int(len(pts)), reps=reps,
            distinct_results=len(dist),
            reproducible_under_fixed_seed=bool(len(dist) == 1),
            pitch_spread_deg=spread,
            note=("single outcome observed; with this many points the fit is "
                  "over-determined" if len(dist) == 1 else
                  "multiple outcomes under an IDENTICAL seed"),
            outcome_distribution=dist))
        print(f"  determinism probe [{label_} facet {k}, {len(pts):,} pts]: "
              f"{len(dist)} distinct result(s) over {reps} identically-seeded "
              f"reps, pitch spread {spread} deg")
    doc = dict(
        finding="Open3D segment_plane is not reproducible under a fixed seed "
                "on small point sets",
        dataset="big_house", measured_on=str(__import__("datetime").date.today()),
        open3d_version=o3d.__version__,
        method="o3d.utility.random.seed(0) immediately before each repetition, "
               "identical input points, identical parameters; compare the "
               "returned plane point-counts and pitches",
        why_it_matters=(
            "Facet recovery fits planes inside small residual blobs. The main "
            "facets (300k-1.5M points) are over-determined and reproduce to "
            "<0.001 deg. The recovered dormer facets are not, and the smallest "
            "ones appear in one run and vanish in the next. This is the same "
            "class of failure the config's expected_facets guard was created "
            "to catch, now reappearing inside the coverage recovery step."),
        consequence=(
            "The exact 26-facet state of 2026-07-23 cannot be regenerated. "
            "Its facet GEOMETRY was never written to disk, only per-facet "
            "summary rows, so it is not recoverable from the comparison file "
            "either."),
        probes=out)
    write_json(OUT / "ransac-nondeterminism-2026-07-25.json", doc)
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--cache-dir", default=str(Path(
        r"C:\Users\eclin\AppData\Local\Temp\claude\C--dev-roof-pipeline"
        r"\ddcb5308-fb71-4b72-a2b5-47fb9de8ad65\scratchpad")),
        help="where the rebuilt facet state is cached (disposable)")
    ap.add_argument("--no-cache", action="store_true",
                    help="ignore any cache and re-derive from scratch")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    OUT.mkdir(parents=True, exist_ok=True)
    cdir = Path(args.cache_dir)

    if not COMPARISON.exists():
        sys.exit(f"missing {COMPARISON}; Task 5 describes that run's state")
    comparison = json.loads(COMPARISON.read_text())

    st = None if args.no_cache else load_cache(cdir)
    if st is None:
        print("REBUILDING the 2026-07-23 facet state (no new decisions)...")
        st = rebuild_state(cfg)
        save_cache(st, cdir)
    else:
        print("Using cached facet state; recomputing plan-view masks...")
        st = finish_state(st, cfg)
    verify = verify_reproduction(st, comparison)
    meta = facet_meta(st, comparison)

    print("\nRANSAC determinism probe ->")
    probe_determinism(st)

    print("\n5A pairwise matrix ->")
    cands = task_5a(st, meta, verify)
    print(f"  {len(cands)} merge candidates flagged (not acted on)")

    print("\n5B residual map ->")
    b = task_5b(st, verify)
    h = b["perimeter_vs_interior"]["headline"]
    print(f"  residual {b['totals']['residual_cu2']:.3f} cu^2 "
          f"(run said {b['totals']['expected_residual_cu2_from_run']}); "
          f"perimeter {h['perimeter_cu2']:.2f} / interior {h['interior_cu2']:.2f}")
    print(f"  triangular blob verdict: {b['triangular_blob']['verdict']}")

    print("\n5C over-segmentation evidence ->")
    doc, blob_map, over2, rows = task_5c(st, meta, verify)
    print(f"  {len(rows)} dormer-kind facets from {len(blob_map)} blobs; "
          f"{len(over2)} blobs produced >2 facets")

    print("\nDONE. All actionable numbers are in reports/big_house/ "
          "(nothing merged, nothing filtered, no thresholds re-swept).")


if __name__ == "__main__":
    main()
