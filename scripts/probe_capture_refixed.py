# CAPTURE-QUALITY METRICS, RECOMPUTED ON THE FIXED GRID.
#
#   .venv/Scripts/python.exe scripts/probe_capture_refixed.py C:/odm/datasets/big_house \
#       --bungalow C:/odm/datasets/bungalow
#
# Writes reports/capture-refixed-<date>.json               (standing rule R2)
#
# SIDE ARTIFACT ONLY. No adoption, no regeneration, no facet state written.
# canonical-2026-07-26-r2 stays canonical, 88.40 pct stays quotable,
# canonical-2026-07-28-grid stays UNADOPTED.
#
# ---------------------------------------------------------------------------
# WHY
#
# density-testable fraction is the CAPTURE quality number: how much of the
# footprint holds enough points to be tested at all. It measures the flight, the
# overlap and the reconstruction, and no amount of segmentation work can move
# it. It was last measured on the buggy grid.
#
# The 2026-07-28 grid adoption changed its DENOMINATOR (eroded footprint 352.707
# -> 349.640 cu^2) and its numerator was never reported at all, only the
# percentage. The case for an ultra rerun rests entirely on how bad capture
# actually is, so that number cannot stay unknown.
#
# STATED EXPECTATION, RECORDED BEFORE THE RUN (Emmett): density-testable is a
# SINGLE-grid metric. Unlike facet coverage, which compared two grids that were
# drifting apart at different bin pitches, nothing here is differenced against a
# second raster. So it should move MODESTLY, not swing like coverage's 5.93
# points. **If it moves more than about 2 points, stop and explain why before
# reporting anything else.**
#
# ---------------------------------------------------------------------------
# THE REQUIRED ASSERTION (silent-failure standing rule, and the obvious failure
# mode named in advance)
#
# The obvious way this goes silently wrong is reading the OLD grid config, or
# the OLD artifact, and returning 82.29 pct, which would look entirely correct.
# So, explicitly:
#
#   A1  the eroded footprint this run computes equals 349.640 cu^2 and NOT
#       352.707 cu^2
#   A2  the old 82.29 pct is NOT reproducible from the new path: running the
#       adopted config must give something else
#   A3  and, as the anti-null companion, the OLD path must still reproduce
#       82.29, so that A2 is a statement about the config and not about a
#       broken script
#
# A2 without A3 would pass if the script were simply broken. Both are reported.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_fill_holes, binary_erosion, label

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar                       # noqa: E402
from dataset_config import load_config                             # noqa: E402
from roofkit.io import load_xyz                                    # noqa: E402
from roofkit.stats import median_nn_spacing                        # noqa: E402
from roofkit import coverage as cov                                # noqa: E402

REPO = Path(__file__).resolve().parents[1]
GRID_STAMP = "2026-07-28-grid"
OLD_ERODED = 352.707
NEW_ERODED = 349.640
OLD_DT_PCT = 82.29
COVERAGE_CELL_MULT = 2.5
MIN_PTS = 2


def cell_metrics(H, region, cell):
    """Every capture number, computed over a REGION of the plan grid.

    region : bool mask selecting the cells to report on. Passing the whole
             footprint gives the site figure; passing blob 0's cells gives the
             tree-occluded case on its own.
    """
    a = cell * cell
    occupied = (H >= 1) & region
    testable = (H >= MIN_PTS) & region
    n_r = int(region.sum())
    n_o = int(occupied.sum())
    n_t = int(testable.sum())
    occ = H[occupied]
    return dict(
        region_cells=n_r, region_cu2=round(n_r * a, 3),
        occupied_cells=n_o, occupied_cu2=round(n_o * a, 3),
        # NUMERATOR AND DENOMINATOR, not just the percentage.
        testable_cells=n_t, testable_cu2=round(n_t * a, 3),
        untestable_cells=n_r - n_t, untestable_cu2=round((n_r - n_t) * a, 3),
        density_testable_pct=round(100.0 * n_t / max(n_r, 1), 2),
        cells_with_1_point=int(((H == 1) & region).sum()),
        cells_with_0_points=int(((H == 0) & region).sum()),
        points_per_occupied_cell=(dict(
            mean=round(float(occ.mean()), 3),
            median=float(np.median(occ)),
            p10=float(np.percentile(occ, 10)),
            p25=float(np.percentile(occ, 25)),
            p90=float(np.percentile(occ, 90))) if n_o else None))


def hole_stats(occupied):
    filled = binary_fill_holes(occupied)
    holes = filled & ~occupied
    lab, n = label(holes)
    sizes = np.bincount(lab.ravel())[1:] if n else np.array([])
    return dict(enclosed_holes=int(n),
                enclosed_hole_cells=int(sizes.sum()) if n else 0,
                median_hole_cells=(int(np.median(sizes)) if n else 0),
                largest_hole_cells=(int(sizes.max()) if n else 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--bungalow", default=None)
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    out = REPO / "reports"

    # ---------------- big_house, isolated roof, adopted config -------------
    doc, points, facets, cfg = load_canonical(args.dataset, GRID_STAMP)
    band = scalar(doc, "band_cu")
    cell = scalar(doc, "cell_cu")
    print(f"  big_house: {len(points):,} pts, cell {cell:.6f} cu, "
          f"{len(facets)} facets from canonical-{GRID_STAMP}")

    masks, g, owner, dist = cov.coverage_masks(points, facets, band, cell)
    foot3 = cov.footprint_three_ways(masks, cell)
    Hall, _ = cov.plan_grid(points, cell)

    # THE ASSERTIONS ------------------------------------------------------
    checks = []
    checks.append(dict(
        id="A1",
        check=f"the eroded footprint this run computes equals {NEW_ERODED} "
              f"cu^2 and NOT {OLD_ERODED}",
        passed=bool(abs(foot3["eroded_cu2"] - NEW_ERODED) < 0.01
                    and abs(foot3["eroded_cu2"] - OLD_ERODED) > 1.0),
        detail=dict(computed=foot3["eroded_cu2"], expected_new=NEW_ERODED,
                    old_value=OLD_ERODED)))

    split_new = cov.split_coverage(masks, cell)
    dt_new = split_new["density_testable_fraction"]["pct"]
    masks_old, _, _, _ = cov.coverage_masks(points, facets, band, cell,
                                            anchor="extent", exact_pitch=False)
    dt_old = cov.split_coverage(masks_old, cell)["density_testable_fraction"]["pct"]
    checks.append(dict(
        id="A2",
        check=f"the old {OLD_DT_PCT} pct is NOT reproducible from the NEW path",
        passed=bool(abs(dt_new - OLD_DT_PCT) > 0.01),
        detail=dict(new_path_pct=dt_new, old_published_pct=OLD_DT_PCT)))
    checks.append(dict(
        id="A3",
        check=f"ANTI-NULL companion: the OLD path still DOES reproduce "
              f"{OLD_DT_PCT} pct, so A2 is a statement about the config and "
              f"not about a broken script",
        passed=bool(abs(dt_old - OLD_DT_PCT) < 0.011),
        detail=dict(old_path_pct=dt_old, old_published_pct=OLD_DT_PCT)))

    move = dt_new - OLD_DT_PCT
    checks.append(dict(
        id="A4",
        check="STATED EXPECTATION: density-testable is a single-grid metric "
              "and should move modestly, under about 2 points. Moving more is "
              "a stop-and-explain.",
        passed=bool(abs(move) <= 2.0),
        detail=dict(old_pct=OLD_DT_PCT, new_pct=dt_new,
                    move_points=round(move, 3))))

    # ---------------- the split: blob 0 vs the rest -----------------------
    interior = masks["interior"]
    foot_region = interior & masks["footprint"]
    blobs = cov.residual_blobs(masks["residual"], g, 0.15)
    b0 = np.zeros_like(foot_region)
    if blobs:
        c0 = blobs[0]["cells"]
        b0[c0[:, 0], c0[:, 1]] = True
    b0_region = b0 & foot_region
    rest_region = foot_region & ~b0

    bh = dict(
        whole_roof=cell_metrics(Hall, foot_region, cell),
        blob0_only=cell_metrics(Hall, b0_region, cell),
        roof_excluding_blob0=cell_metrics(Hall, rest_region, cell),
        holes_whole_roof=hole_stats(Hall >= MIN_PTS),
        footprint_three_ways=foot3,
        blob0_area_cu2=(round(float(blobs[0]["area_cu2"]), 4) if blobs else None),
        n_blobs=len(blobs))

    print(f"    eroded footprint {foot3['eroded_cu2']} cu^2 "
          f"(old {OLD_ERODED})")
    print(f"    density-testable {dt_new} pct  (old published {OLD_DT_PCT}, "
          f"move {move:+.2f} points)")
    if abs(move) > 2.0:
        print("\n  *** MOVE EXCEEDS 2 POINTS. Stopping per the stated "
              "expectation. Nothing else is reported. ***")
        (out / f"capture-refixed-{args.stamp}.json").write_text(json.dumps(
            dict(status="STOPPED: density-testable moved more than 2 points",
                 cross_checks=checks, big_house=bh), indent=2, default=float))
        return

    # ---------------- bungalow, raw cloud, same config --------------------
    bung = None
    if args.bungalow:
        bcfg = load_config(args.bungalow)
        cloud = Path(bcfg["cloud_path"])
        print(f"  bungalow: reading {cloud.name} (crop-free, raw) ...",
              flush=True)
        bpts = load_xyz(str(cloud))
        bs = median_nn_spacing(bpts)
        bcell = COVERAGE_CELL_MULT * bs
        BH, bg = cov.plan_grid(bpts, bcell)
        boccupied = BH >= 1
        bfoot = binary_fill_holes(boccupied)
        bung = dict(
            subject="bungalow (raw cloud, crop-free, adopted grid)",
            n_points=int(len(bpts)),
            spacing_cu=round(float(bs), 6), cell_cu=round(float(bcell), 6),
            grid=dict(nx=int(bg["nx"]), ny=int(bg["ny"])),
            metrics=cell_metrics(BH, bfoot, bcell),
            holes=hole_stats(boccupied))
        # the same measurement on the OLD grid, so the comparison is like for
        # like rather than new-versus-remembered
        BHo, _ = cov.plan_grid(bpts, bcell, anchor="extent", exact_pitch=False)
        bfo = binary_fill_holes(BHo >= 1)
        bung["old_grid_metrics"] = cell_metrics(BHo, bfo, bcell)
        del bpts
        print(f"    density-testable {bung['metrics']['density_testable_pct']} "
              f"pct (old grid {bung['old_grid_metrics']['density_testable_pct']}, "
              f"published 67.09)")

    # big_house RAW cloud too, since the site-to-site comparison was raw vs raw
    bh_raw = None
    cloud = Path(cfg["cloud_path"])
    if cloud.exists():
        print(f"  big_house: reading {cloud.name} (raw, for the raw-vs-raw "
              f"comparison) ...", flush=True)
        rpts = load_xyz(str(cloud))
        rs = median_nn_spacing(rpts)
        rcell = COVERAGE_CELL_MULT * rs
        RH, rg = cov.plan_grid(rpts, rcell)
        rfoot = binary_fill_holes(RH >= 1)
        RHo, _ = cov.plan_grid(rpts, rcell, anchor="extent", exact_pitch=False)
        rfo = binary_fill_holes(RHo >= 1)
        bh_raw = dict(
            subject="big_house (raw cloud, crop-free, adopted grid)",
            n_points=int(len(rpts)),
            spacing_cu=round(float(rs), 6), cell_cu=round(float(rcell), 6),
            grid=dict(nx=int(rg["nx"]), ny=int(rg["ny"])),
            metrics=cell_metrics(RH, rfoot, rcell),
            old_grid_metrics=cell_metrics(RHo, rfo, rcell),
            holes=hole_stats(RH >= 1))
        del rpts
        print(f"    density-testable "
              f"{bh_raw['metrics']['density_testable_pct']} pct "
              f"(old grid {bh_raw['old_grid_metrics']['density_testable_pct']}, "
              f"published 60.68)")

    docout = dict(
        task="capture-quality metrics recomputed on the ADOPTED grid "
             "(lattice origin + exact_pitch)",
        date=args.stamp,
        status="SIDE ARTIFACT ONLY. No adoption, no regeneration. "
               "canonical-2026-07-26-r2 stays canonical, 88.40 pct stays "
               "quotable, canonical-2026-07-28-grid stays UNADOPTED.",
        why="density-testable is the CAPTURE metric and the case for an ultra "
            "rerun rests on it. It was last measured on the buggy grid, its "
            "denominator changed with the fix, and its numerator was never "
            "reported.",
        stated_expectation="density-testable is a SINGLE-grid metric, unlike "
                           "facet coverage which differenced two drifting "
                           "grids, so it should move modestly. Recorded before "
                           "the run; a move over 2 points was a stop-and-"
                           "explain.",
        config=dict(anchor="lattice", exact_pitch=True,
                    cell_mult=COVERAGE_CELL_MULT, min_pts=MIN_PTS,
                    source_state=f"canonical-{GRID_STAMP}"),
        cross_checks=checks,
        big_house_roof=bh,
        big_house_raw=bh_raw,
        bungalow_raw=bung,
        prior_published=dict(bungalow_raw_pct=67.09, big_house_raw_pct=60.68,
                             big_house_roof_dt_pct=OLD_DT_PCT,
                             big_house_one_point_cells=249745,
                             big_house_enclosed_holes=111154,
                             big_house_enclosed_hole_cells=370079))
    p = out / f"capture-refixed-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2, default=float))

    w, b0m, rst = bh["whole_roof"], bh["blob0_only"], bh["roof_excluding_blob0"]
    print(f"\n  BIG_HOUSE ROOF, adopted grid")
    print(f"    density-testable  {w['testable_cu2']} / {w['region_cu2']} cu^2 "
          f"= {w['density_testable_pct']} pct")
    print(f"    one-point cells   {w['cells_with_1_point']:,}   "
          f"(was 249,745)")
    print(f"    enclosed holes    {bh['holes_whole_roof']['enclosed_holes']:,} "
          f"in {bh['holes_whole_roof']['enclosed_hole_cells']:,} cells   "
          f"(was 111,154 / 370,079)")
    print(f"    p10 pts/occ cell  {w['points_per_occupied_cell']['p10']}   "
          f"(was 1.0)")
    print(f"\n    BLOB 0 ONLY   {b0m['testable_cu2']} / {b0m['region_cu2']} "
          f"cu^2 = {b0m['density_testable_pct']} pct, "
          f"one-point cells {b0m['cells_with_1_point']:,}, p10 "
          f"{b0m['points_per_occupied_cell']['p10'] if b0m['points_per_occupied_cell'] else None}")
    print(f"    EXCLUDING B0  {rst['testable_cu2']} / {rst['region_cu2']} "
          f"cu^2 = {rst['density_testable_pct']} pct, "
          f"one-point cells {rst['cells_with_1_point']:,}, p10 "
          f"{rst['points_per_occupied_cell']['p10']}")
    print()
    for c in checks:
        print(f"  {c['id']} {'PASS' if c['passed'] else 'FAIL'}: {c['check'][:82]}")
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
