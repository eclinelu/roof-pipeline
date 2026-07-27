# CAPTURE QUALITY, measurable BEFORE the pipeline runs on a cloud.
#
#   .venv/Scripts/python.exe -u scripts/probe_capture.py C:/odm/datasets/bungalow \
#       C:/odm/datasets/big_house
#
# Writes reports/capture-<date>.json                       (standing rule R2)
#
# ---------------------------------------------------------------------------
# WHY THIS RUNS BEFORE THE PIPELINE, NOT AFTER
#
# big_house's plan-view mask turned out to be riddled with holes: 111,154
# enclosed gaps, most of them a single cell, because a cell needs 2 points to be
# testable and 249,745 cells inside the roof held exactly 1. That is a CAPTURE
# shortfall, not a segmentation failure. It is worst on the southern half, where
# image overlap was lower.
#
# big_house cannot be re-flown; the drone is no longer available, so for that
# site the shortfall is permanent. bungalow was flown by the same operator with
# the same habits. If bungalow shares the problem, that has to be known BEFORE a
# result is frozen on it, not discovered afterwards when the freeze is the thing
# being explained away. (Emmett, 2026-07-26.)
#
# WHY IT NEEDS NO CROP BOX. bungalow has no roofkit.json yet, so there is no
# building outline and no roof.npy. This metric does not need one: it asks what
# fraction of the OCCUPIED plan area holds enough points to test, which is a
# property of the capture and can be measured on the raw cloud.
#
# WHAT IS AND IS NOT COMPARABLE. A raw cloud contains ground, vegetation and
# walls as well as roof, and their densities differ, so a raw-cloud figure is
# NOT comparable to a roof-only figure. It is comparable to another raw-cloud
# figure measured the same way, which is what the site-to-site question needs.
# Both are reported for big_house, so its raw number anchors bungalow's and its
# roof number stays the one we actually understand.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_fill_holes, label

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                            # noqa: E402
from roofkit.io import load_xyz                                   # noqa: E402
from roofkit.stats import median_nn_spacing                       # noqa: E402
from roofkit import coverage as cov                               # noqa: E402

REPO = Path(__file__).resolve().parents[1]
COVERAGE_CELL_MULT = 2.5
MIN_PTS = 2


def measure(points, label_str, spacing=None):
    """The density-testable fraction of one point set, on the pipeline's own
    grid rule (cell = 2.5 x median nearest-neighbour spacing).

    occupied : cells holding at least 1 point.
    testable : cells holding at least MIN_PTS. Only these can be tested.
    footprint: occupied with enclosed holes filled, i.e. the area a closed
               surface would cover.
    """
    s = median_nn_spacing(points) if spacing is None else float(spacing)
    cell = COVERAGE_CELL_MULT * s
    H, g = cov.plan_grid(points, cell)
    occupied = H >= 1
    testable = H >= MIN_PTS
    footprint = binary_fill_holes(occupied)
    holes = footprint & ~occupied
    a = cell * cell

    n_f = int(footprint.sum())
    n_o = int(occupied.sum())
    n_t = int(testable.sum())
    one_pt = int(((H == 1) & footprint).sum())
    zero_pt = int(((H == 0) & footprint).sum())

    lab, n_holes = label(holes)
    hole_sizes = np.bincount(lab.ravel())[1:] if n_holes else np.array([])

    occ = H[occupied]
    return dict(
        subject=label_str,
        n_points=int(len(points)),
        spacing_cu=round(s, 6), cell_cu=round(cell, 6),
        grid=dict(nx=int(g["nx"]), ny=int(g["ny"])),
        footprint_cells=n_f, footprint_cu2=round(n_f * a, 3),
        occupied_cells=n_o, testable_cells=n_t,
        # THE HEADLINE: how much of the footprint can be tested at all.
        density_testable_pct=round(100.0 * n_t / max(n_f, 1), 2),
        untestable_cells=n_f - n_t,
        untestable_cu2=round((n_f - n_t) * a, 3),
        cells_with_1_point=one_pt, cells_with_0_points=zero_pt,
        enclosed_holes=int(n_holes),
        enclosed_hole_cells=int(hole_sizes.sum()) if n_holes else 0,
        median_hole_cells=(int(np.median(hole_sizes)) if n_holes else 0),
        points_per_occupied_cell=dict(
            mean=round(float(occ.mean()), 2),
            median=float(np.median(occ)),
            p10=float(np.percentile(occ, 10)),
            p25=float(np.percentile(occ, 25)),
            p90=float(np.percentile(occ, 90))),
        reading=("points_per_occupied_cell p10 is the number that matters: the "
                 "cell size is 2.5 x spacing, so a UNIFORM cloud would put "
                 "several points in every occupied cell. A p10 of 1 means the "
                 "sparsest tenth of the surface cannot be tested at all."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("datasets", nargs="+")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()

    rows = []
    for d in args.datasets:
        cfg = load_config(d)
        name = Path(d).name

        # The RAW georeferenced cloud, which is all a fresh dataset has.
        cloud = Path(cfg["cloud_path"])
        if cloud.exists():
            print(f"  {name}: reading {cloud.name} ...")
            pts = load_xyz(str(cloud))
            r = measure(pts, f"{name} (raw cloud)")
            rows.append(r)
            print(f"    {r['n_points']:,} pts  spacing {r['spacing_cu']}  "
                  f"density-testable {r['density_testable_pct']}%  "
                  f"(cells with 1 pt: {r['cells_with_1_point']:,})")
            del pts
        else:
            print(f"  {name}: no georeferenced cloud at {cloud}")

        # The isolated roof, where one exists. Only comparable to another
        # isolated roof, never to a raw cloud.
        roof = Path(cfg["roof_path"])
        if roof.exists():
            pts = np.load(roof)
            r = measure(pts, f"{name} (isolated roof)")
            rows.append(r)
            print(f"    roof: {r['n_points']:,} pts  "
                  f"density-testable {r['density_testable_pct']}%  "
                  f"(cells with 1 pt: {r['cells_with_1_point']:,})")
            del pts

    doc = dict(
        task="capture quality: density-testable fraction, measured BEFORE the "
             "pipeline runs",
        date=args.stamp,
        why="big_house's mask is riddled with single-point cells, which is a "
            "capture shortfall and is permanent for that site because it "
            "cannot be re-flown. bungalow was flown by the same operator, so "
            "the same question has to be asked before anything is frozen on it.",
        comparability="raw-cloud figures are comparable only to other raw-cloud "
                      "figures: a raw cloud mixes ground, vegetation and walls "
                      "with the roof and their densities differ. Roof-only "
                      "figures are comparable to other roof-only figures.",
        method=dict(
            cell="2.5 x median nearest-neighbour spacing, the pipeline's own "
                 "grid rule, so the number means the same thing here as in the "
                 "coverage report",
            testable=f"a cell holding at least {MIN_PTS} points",
            footprint="occupied cells with enclosed holes filled"),
        measurements=rows,
    )
    p = REPO / "reports" / f"capture-{args.stamp}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, default=float))

    print("\n  SUMMARY")
    print(f"    {'subject':<34}{'points':>12}{'testable':>10}{'1-pt cells':>13}"
          f"{'p10 pts/cell':>14}")
    for r in rows:
        print(f"    {r['subject']:<34}{r['n_points']:>12,}"
              f"{r['density_testable_pct']:>9.2f}%{r['cells_with_1_point']:>13,}"
              f"{r['points_per_occupied_cell']['p10']:>14.1f}")
    print(f"\n  wrote {p}")


if __name__ == "__main__":
    main()
