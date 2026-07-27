# Task 7B: WHERE DID THE COVERAGE NUMBER GO?
#
#   .venv/Scripts/python.exe -u scripts/probe_attribution.py C:/odm/datasets/big_house
#
# Writes reports/big_house/attribution-<date>.json   (standing rule R2)
#
# ---------------------------------------------------------------------------
# WHY A DECOMPOSITION AND NOT JUST A BEFORE AND AFTER
#
# Three separate changes land in the same run, and all three move coverage:
#
#   a  min_pitch 10 -> 5, which ADMITS low-slope facets that were being deleted
#   b  cell-based blob selection, which REMOVES a duplicate facet
#   c  hole filling, which changes the DENOMINATOR
#
# Reported as one before-and-after, the number moves and nobody can say why, and
# a future reader cannot tell a real improvement from a base change. So each is
# switched on in turn and the delta attributed, the same discipline as the Task 4
# area decomposition.
#
# THIS IS NOT THE CANONICAL STATE. It writes one report and no state file. The
# final configuration here is the same one canonical_state.py runs, which makes
# the last row a cross-check on the canonical run rather than a duplicate of it.
#
# ORDER MATTERS AND IS NOT COMMUTATIVE. Admitting a facet changes what is
# explained; filling holes changes what is being divided by. The order below is
# stated and fixed: facets first, then the duplicate, then the base. A different
# order would split the same total differently, which is a property of any
# sequential decomposition and is why the order is written down.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                            # noqa: E402
from canonical import leveled_points                              # noqa: E402
from recon_common import discover_facets                          # noqa: E402
from roofkit.stats import median_nn_spacing                       # noqa: E402
from roofkit.measure import facet_area, is_low_slope, rise_over_12  # noqa: E402
from roofkit.segment import assert_single_ownership               # noqa: E402
from roofkit import coverage as cov                               # noqa: E402

REPO = Path(__file__).resolve().parents[1]
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
MIN_AREA_POINTS_EQUIV = 3704

# The four configurations, in the order they are applied.
CONFIGS = [
    dict(key="baseline", min_pitch=10.0, selection="box", fill_holes=False,
         label="baseline: the 2026-07-26 canonical state as published"),
    dict(key="a_min_pitch_5", min_pitch=5.0, selection="box", fill_holes=False,
         label="a: + min_pitch 5 (admits low-slope facets)"),
    dict(key="b_cell_selection", min_pitch=5.0, selection="cells",
         fill_holes=False,
         label="b: + cell-based blob selection (removes the duplicate facet)"),
    dict(key="c_hole_filling", min_pitch=5.0, selection="cells",
         fill_holes=True,
         label="c: + hole filling (changes the denominator)"),
]


def old_style_coverage(masks, cell):
    """The single number as it was reported before the split, so the four
    configurations are compared on ONE consistent metric. The new split metrics
    are reported separately for the final configuration."""
    a = cell * cell
    interior_testable = masks["interior"] & masks["testable"]
    n_i = int(interior_testable.sum())
    n_r = int(masks["residual"].sum())
    return dict(coverage_pct=round(100.0 * (1.0 - n_r / max(n_i, 1)), 3),
                denominator_cells=n_i, denominator_cu2=round(n_i * a, 3),
                residual_cells=n_r, residual_cu2=round(n_r * a, 4))


def run_config(points, cfg, spacing, c):
    """One full pipeline at one configuration. Returns the facets and the
    coverage numbers, and never writes state."""
    facets, band, s_full = discover_facets(points, cfg, probability=1.0,
                                           spacing=spacing,
                                           min_pitch=c["min_pitch"])
    bar, _ = cov.calibrate_quality_bar(facets, s_full)

    # The point floor is DERIVED per run, so it is recomputed here too and
    # recorded: it can differ between configurations because the main facet set
    # can differ, and a silently different floor would confound the attribution.
    d = []
    for f in facets:
        pts = np.asarray(f["points"], float)
        s_f = float(np.median(cov._nn(pts)))
        gross = float(facet_area(pts, f["normal"], cfg["alpha_mult"] * s_f))
        d.append(len(pts) * spacing ** 2 / max(gross, 1e-12))
    density = float(np.median(d))
    min_points = int(round(MIN_AREA_POINTS_EQUIV * density))
    min_area = MIN_AREA_POINTS_EQUIV * spacing ** 2

    cell = COVERAGE_CELL_MULT * s_full
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell,
                                           fill_holes=c["fill_holes"])
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    new = cov.recover_facets(points, blobs, None, dist, band, s_full, bar,
                             alpha_mult=cfg["alpha_mult"], probability=1.0,
                             min_pitch=c["min_pitch"],
                             min_points_hard=min_points, min_area_hard=min_area,
                             selection=c["selection"], grid=g)
    allf = facets + new

    # Duplicate ownership: MEASURED here rather than asserted, because the
    # baseline configuration is expected to fail and the run must continue.
    idx = [np.asarray(f["idx"], np.int64) for f in allf if "idx" in f]
    allc = np.concatenate(idx) if idx else np.array([], np.int64)
    dup = int(len(allc) - len(np.unique(allc))) if len(allc) else 0

    masks_post, g2, _, _ = cov.coverage_masks(points, allf, band, cell,
                                              fill_holes=c["fill_holes"])
    low = [f for f in allf if is_low_slope(f["pitch"])]
    return dict(
        key=c["key"], label=c["label"],
        settings=dict(min_pitch=c["min_pitch"], selection=c["selection"],
                      fill_holes=c["fill_holes"]),
        derived_min_points=min_points,
        measured_density_d=round(density, 4),
        counts=dict(n_main=len(facets), n_recovered=len(new),
                    n_total=len(allf), n_blobs=len(blobs),
                    n_low_slope=len(low)),
        low_slope_facets=[dict(pitch_deg=round(float(f["pitch"]), 3),
                               rise_over_12=round(rise_over_12(f["pitch"]), 2),
                               n_points=int(len(f["points"])))
                          for f in low],
        duplicated_point_entries=dup,
        coverage=old_style_coverage(masks_post, cell),
        split_coverage=cov.split_coverage(masks_post, cell),
        footprint=cov.footprint_three_ways(masks_post, cell),
    ), allf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    out = REPO / "reports" / Path(args.dataset).name

    points = leveled_points(cfg)
    spacing = median_nn_spacing(points)
    print(f"  {len(points):,} points, spacing {spacing:.6f} cu\n")

    rows, final_facets = [], None
    for c in CONFIGS:
        r, allf = run_config(points, cfg, spacing, c)
        rows.append(r)
        final_facets = allf
        cvg = r["coverage"]
        print(f"  {r['label']}")
        print(f"    {r['counts']['n_main']} main + {r['counts']['n_recovered']} "
              f"recovered = {r['counts']['n_total']}   "
              f"low-slope {r['counts']['n_low_slope']}   "
              f"duplicated points {r['duplicated_point_entries']:,}   "
              f"floor {r['derived_min_points']}")
        print(f"    coverage {cvg['coverage_pct']:.3f}%  "
              f"(residual {cvg['residual_cu2']} of {cvg['denominator_cu2']} cu^2)\n")

    # The decomposition.
    deltas = []
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        deltas.append(dict(
            step=cur["key"], label=cur["label"],
            coverage_before_pct=prev["coverage"]["coverage_pct"],
            coverage_after_pct=cur["coverage"]["coverage_pct"],
            delta_pct_points=round(cur["coverage"]["coverage_pct"] -
                                   prev["coverage"]["coverage_pct"], 3),
            residual_delta_cu2=round(cur["coverage"]["residual_cu2"] -
                                     prev["coverage"]["residual_cu2"], 4),
            denominator_delta_cu2=round(cur["coverage"]["denominator_cu2"] -
                                        prev["coverage"]["denominator_cu2"], 3),
            facet_count_delta=cur["counts"]["n_total"] - prev["counts"]["n_total"],
            duplicated_points_delta=(cur["duplicated_point_entries"] -
                                     prev["duplicated_point_entries"])))

    total = round(rows[-1]["coverage"]["coverage_pct"] -
                  rows[0]["coverage"]["coverage_pct"], 3)
    doc = dict(
        task="Task 7B: attribution of the coverage change to its three causes",
        dataset=Path(args.dataset).name, date=args.stamp,
        why="three changes land in the same run and all three move coverage. "
            "Reported as one before-and-after, the number moves and nobody can "
            "say why.",
        order_note="the decomposition is SEQUENTIAL and not commutative: "
                   "admitting a facet changes what is explained, filling holes "
                   "changes what is divided by. The order is facets, then the "
                   "duplicate, then the base, and a different order would split "
                   "the same total differently.",
        metric="one consistent metric across all four rows: the OLD single "
               "coverage number, residual over interior-and-testable. The new "
               "split metrics are reported per row as well, but only the final "
               "row's are meaningful as headline numbers.",
        configurations=rows,
        decomposition=deltas,
        total_change_pct_points=total,
        cross_check=("the final configuration is the same one canonical_state.py "
                     "runs, so its numbers must match the canonical file. If "
                     "they do not, one of the two is wrong."),
    )
    (out / f"attribution-{args.stamp}.json").write_text(
        json.dumps(doc, indent=2, default=float))

    print("  DECOMPOSITION")
    for d in deltas:
        print(f"    {d['step']:<18} {d['coverage_before_pct']:>7.3f} -> "
              f"{d['coverage_after_pct']:>7.3f}  "
              f"delta {d['delta_pct_points']:>+7.3f} pts   "
              f"facets {d['facet_count_delta']:>+2d}   "
              f"denominator {d['denominator_delta_cu2']:>+9.3f} cu^2")
    print(f"    {'TOTAL':<18} {rows[0]['coverage']['coverage_pct']:>7.3f} -> "
          f"{rows[-1]['coverage']['coverage_pct']:>7.3f}  "
          f"delta {total:>+7.3f} pts")
    print(f"\n  wrote {out / f'attribution-{args.stamp}.json'}")


if __name__ == "__main__":
    main()
