# IS THE PUBLISHED COVERAGE NUMBER PHASE-DEPENDENT?
#
#   .venv/Scripts/python.exe scripts/probe_production_phase.py C:/odm/datasets/big_house
#
# Writes reports/big_house/production-phase-<date>.json    (standing rule R2)
#
# SIDE ARTIFACT ONLY. Loads the canonical state, measures it, writes a report.
# Fits nothing, adopts nothing, changes no threshold and no comparison operator.
# canonical-2026-07-26-r2 remains canonical; published facet coverage remains
# 88.40 pct.
#
# ---------------------------------------------------------------------------
# THE QUESTION, AND WHY IT OUTRANKS THE NEXT MECHANISM
#
# The M1a sweep established that raster phase moves the CONNECTIVITY FILTER a
# great deal (decisions/2026-07-28-raster-phase-is-an-unswept-parameter.md).
# That was a property of a fix nobody adopted, so it cost nothing. The open
# question is whether the same nuisance parameter reaches the PRODUCTION
# pipeline, whose coverage number IS published and IS the cross-pass detector.
#
# If 88.40 pct moves with an arbitrary grid alignment then it is not a
# measurement of the segmentation, it is a measurement of the segmentation plus
# an accident, and a pass-to-pass coverage comparison cannot distinguish a real
# improvement from a re-alignment.
#
# ---------------------------------------------------------------------------
# PART A: WHERE EVERY PRODUCTION RASTER ORIGIN COMES FROM (static, read off the
# source; the line numbers are recorded so a reader can check rather than trust)
#
#   plan_grid                coverage.py:41   xlo, ylo = x.min(), y.min() of the
#                                             points handed in. DATA EXTENT.
#   coverage_masks Hall      coverage.py:96   plan_grid(roof, cell) -> that origin
#   coverage_masks Hexp      coverage.py:101  histogram2d anchored at g["xlo"],
#                                             SAME origin, but see Part B
#   footprint (hole fill)    coverage.py:112  binary_fill_holes over that raster.
#                                             INHERITS, no origin of its own.
#   interior (erosion)       coverage.py:113  binary_erosion over that raster.
#                                             INHERITS.
#   residual_blobs           coverage.py:254  labels the same raster. INHERITS.
#   recover_facets cells     coverage.py:370  (roof - g["xlo"]) / g["cell"].
#                                             SAME origin, so candidate
#                                             selection inherits it too.
#   area_accounting          coverage.py:545  xlo = min over FACETS of
#                                             points[:,0].min(). A SECOND,
#                                             DIFFERENT data-extent origin.
#   connected_core (M1a)     segment.py       xy.min() per facet. A THIRD.
#
# So the whole coverage / footprint / residual / recovery chain shares ONE
# data-derived origin, area accounting uses a SECOND, and the M1a filter used a
# THIRD. All three are `min()` of whatever points that stage happens to see.
# None was chosen.
#
# ---------------------------------------------------------------------------
# PART B: A SEPARATE DEFECT FOUND WHILE READING THE ORIGINS, MEASURED NOT
# ASSERTED
#
# plan_grid asks histogram2d for `nx` bins over the range [xlo, xhi]. It does
# NOT ask for bins of width `cell`. Since nx = int(span/cell) + 1, the actual
# bin width is span/nx, which is always SMALLER than cell. Meanwhile Hexp, the
# explained-count histogram, is anchored over [xlo, xlo + nx*cell] and so has
# bins of width EXACTLY cell.
#
# The two histograms that coverage_masks compares cell-for-cell are therefore
# on grids of slightly different pitch, and the mismatch ACCUMULATES with
# distance from the origin. Every area in the report is charged as cell^2,
# which is the pitch of neither grid.
#
# This is measured below rather than asserted, and it is NOT fixed here:
# fixing it would change the published number, and this is a side artifact.
#
# ---------------------------------------------------------------------------
# PART C: THE MEASUREMENT. Shift the production raster's origin by fractions of
# a cell and re-read facet coverage, the three footprints and the
# density-testable fraction at each.
#
# INDEPENDENT ASSERTIONS (standing rule 2026-07-27-silent-failure-standing-rule
# and its 2026-07-28 anti-null extension):
#   - the zero offset reproduces the canonical document's own published
#     coverage and footprint figures. If it does not, this probe is not
#     measuring the production path and nothing below means anything.
#   - ANTI-NULL: at least one offset must change at least one reported
#     quantity. A spread of exactly zero means the probe translated the origin
#     with the points again, which is how the first phase probe produced a
#     flawless measurement of nothing.
#   - an INTEGER cell offset must leave every reported quantity unchanged to
#     within float noise, because it is a relabelling and not a regridding.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar                      # noqa: E402
from roofkit import coverage as cov                               # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"

# Sub-cell phase offsets, as fractions of a cell in (x, y). The origin is moved
# DOWN and LEFT so the data stays inside the raster. The first entry is the
# zero offset and must reproduce the published numbers.
OFFSETS = [(0.0, 0.0), (0.25, 0.0), (0.5, 0.0), (0.75, 0.0),
           (0.0, 0.5), (0.5, 0.5), (0.33, 0.66), (0.66, 0.33)]
INTEGER_OFFSET = (3.0, 2.0)

ORIGIN_AUDIT = [
    dict(stage="plan_grid", where="roofkit/coverage.py:41",
         origin="x.min(), y.min() of the points handed in",
         kind="DATA EXTENT, not chosen"),
    dict(stage="coverage_masks / testable (Hall)", where="coverage.py:96",
         origin="plan_grid's origin", kind="INHERITS"),
    dict(stage="coverage_masks / explained (Hexp)", where="coverage.py:101",
         origin="g['xlo'], g['ylo']",
         kind="INHERITS the origin but NOT the bin pitch, see part B"),
    dict(stage="footprint, hole filling", where="coverage.py:112",
         origin="binary_fill_holes over the same raster",
         kind="INHERITS, no origin of its own"),
    dict(stage="interior, erosion", where="coverage.py:113",
         origin="binary_erosion over the same raster", kind="INHERITS"),
    dict(stage="residual_blobs", where="coverage.py:254",
         origin="labels the same raster", kind="INHERITS"),
    dict(stage="recover_facets, candidate cell selection",
         where="coverage.py:370",
         origin="(roof - g['xlo']) / g['cell']", kind="INHERITS"),
    dict(stage="area_accounting", where="coverage.py:545",
         origin="min over FACET points of x.min(), y.min()",
         kind="A SECOND, DIFFERENT data-extent origin"),
    dict(stage="connected_core (M1a filter)", where="roofkit/segment.py",
         origin="xy.min() per facet",
         kind="A THIRD data-extent origin; opt-in and not in production"),
]


def measure(points, facets, band, cell, origin, exact_pitch=False):
    masks, g, _, _ = cov.coverage_masks(points, facets, band, cell,
                                        origin=origin,
                                        exact_pitch=exact_pitch,
                                        # this probe's whole subject is the
                                        # pre-fix phase behaviour, so it opts
                                        # past the 2026-07-30 guard by design
                                        allow_superseded=True)
    split = cov.split_coverage(masks, cell)
    foot = cov.footprint_three_ways(masks, cell)
    return dict(
        facet_coverage_pct=split["facet_coverage"]["pct"],
        explained_cu2=split["facet_coverage"]["explained_cu2"],
        testable_cu2=split["facet_coverage"]["testable_cu2"],
        density_testable_pct=split["density_testable_fraction"]["pct"],
        footprint_raw_cu2=foot["raw_cu2"],
        footprint_filled_cu2=foot["filled_cu2"],
        footprint_eroded_cu2=foot["eroded_cu2"],
        nx=int(g["nx"]), ny=int(g["ny"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    doc, points, facets, cfg = load_canonical(args.dataset, CANONICAL_STAMP)
    band = scalar(doc, "band_cu")
    cell = scalar(doc, "cell_cu")
    spacing = scalar(doc, "spacing_cu")
    x, y = points[:, 0], points[:, 1]
    base_origin = np.array([x.min(), y.min()])

    # ---- PART B, measured -------------------------------------------------
    xhi, yhi = x.max(), y.max()
    nx0 = int((xhi - base_origin[0]) / cell) + 1
    ny0 = int((yhi - base_origin[1]) / cell) + 1
    bw_x = (xhi - base_origin[0]) / nx0
    bw_y = (yhi - base_origin[1]) / ny0
    drift_x_cells = nx0 * (cell - bw_x) / cell
    drift_y_cells = ny0 * (cell - bw_y) / cell
    part_b = dict(
        issue="plan_grid asks histogram2d for nx bins over [xlo, xhi]; it does "
              "not ask for bins of width `cell`. Hexp is anchored over "
              "[xlo, xlo + nx*cell] and DOES have bins of width cell. The two "
              "histograms coverage_masks compares cell-for-cell are on grids "
              "of different pitch, and the mismatch accumulates with distance "
              "from the origin.",
        cell_cu=round(float(cell), 10),
        hall_bin_width_x=round(float(bw_x), 10),
        hall_bin_width_y=round(float(bw_y), 10),
        hexp_bin_width=round(float(cell), 10),
        hall_bin_pct_of_cell=[round(100 * bw_x / cell, 4),
                              round(100 * bw_y / cell, 4)],
        cumulative_drift_cells=[round(float(drift_x_cells), 4),
                                round(float(drift_y_cells), 4)],
        cumulative_drift_reading="how far apart the two grids are, in CELLS, "
                                 "at the far corner of the building. Half a "
                                 "cell or more means testable and explained "
                                 "are being compared across a shift of half a "
                                 "cell there.",
        area_charged_per_cell_cu2=round(float(cell * cell), 10),
        actual_hall_cell_area_cu2=round(float(bw_x * bw_y), 10),
        area_overstatement_pct=round(
            100 * (cell * cell / (bw_x * bw_y) - 1), 4),
        status="MEASURED, NOT FIXED. Fixing it would change the published "
               "number and this is a side artifact.")
    print("  PART B: plan_grid bin pitch")
    print(f"    Hall bins are {part_b['hall_bin_pct_of_cell'][0]:.4f}% / "
          f"{part_b['hall_bin_pct_of_cell'][1]:.4f}% of cell; Hexp bins are 100%")
    print(f"    cumulative drift at the far corner: "
          f"{drift_x_cells:.3f} x {drift_y_cells:.3f} CELLS")
    print(f"    areas charged as cell^2 overstate the Hall cell by "
          f"{part_b['area_overstatement_pct']:.4f}%\n")

    # ---- PART C, the phase sweep -----------------------------------------
    rows = []
    for (ox, oy) in OFFSETS:
        org = base_origin - np.array([ox * cell, oy * cell])
        m = measure(points, facets, band, cell, org)
        m["offset_cells"] = [ox, oy]
        rows.append(m)
        print(f"    offset ({ox:>4.2f}, {oy:>4.2f})   coverage "
              f"{m['facet_coverage_pct']:>6.2f}%   density-testable "
              f"{m['density_testable_pct']:>6.2f}%   footprint raw "
              f"{m['footprint_raw_cu2']:>9.3f}  filled "
              f"{m['footprint_filled_cu2']:>9.3f}  eroded "
              f"{m['footprint_eroded_cu2']:>9.3f}", flush=True)

    org_i = base_origin - np.array([INTEGER_OFFSET[0] * cell,
                                    INTEGER_OFFSET[1] * cell])
    m_int = measure(points, facets, band, cell, org_i)
    m_int["offset_cells"] = list(INTEGER_OFFSET)

    # ---- PART D: WOULD FIXING THE BIN PITCH REMOVE THE PHASE SENSITIVITY? --
    # The obvious hypothesis after Part B is that the spread in Part C is
    # really the pitch defect wearing a phase costume. It is CHEAP TO TEST and
    # expensive to assume, so it is tested: the same sweep, same function, one
    # flag flipped, nothing else changed.
    print("\n  PART D: same sweep with exact_pitch=True (counterfactual)")
    rows_fixed = []
    for (ox, oy) in OFFSETS:
        org = base_origin - np.array([ox * cell, oy * cell])
        m = measure(points, facets, band, cell, org, exact_pitch=True)
        m["offset_cells"] = [ox, oy]
        rows_fixed.append(m)
        print(f"    offset ({ox:>4.2f}, {oy:>4.2f})   coverage "
              f"{m['facet_coverage_pct']:>6.2f}%   density-testable "
              f"{m['density_testable_pct']:>6.2f}%", flush=True)

    # ---- assertions -------------------------------------------------------
    zero = rows[0]
    pub_cov = doc["coverage"]["facet_coverage"]["pct"]
    pub_raw = doc["footprint"]["raw_cu2"]
    a_repro = (abs(zero["facet_coverage_pct"] - pub_cov) < 0.005 and
               abs(zero["footprint_raw_cu2"] - pub_raw) < 1e-3)
    keys = ["facet_coverage_pct", "density_testable_pct", "footprint_raw_cu2",
            "footprint_filled_cu2", "footprint_eroded_cu2"]
    moved = any(r[k] != zero[k] for r in rows[1:] for k in keys)
    int_same = all(abs(m_int[k] - zero[k]) <= 1e-6 * max(1.0, abs(zero[k]))
                   for k in keys)

    checks = [
        dict(check="the ZERO offset reproduces the canonical document's own "
                   "published facet coverage and raw footprint. If not, this "
                   "probe is not measuring the production path.",
             passed=bool(a_repro),
             detail=dict(published_coverage_pct=pub_cov,
                         measured_coverage_pct=zero["facet_coverage_pct"],
                         published_raw_cu2=pub_raw,
                         measured_raw_cu2=zero["footprint_raw_cu2"])),
        dict(check="ANTI-NULL: at least one sub-cell offset changes at least "
                   "one reported quantity. A spread of exactly zero means the "
                   "probe translated the origin with the points again.",
             passed=bool(moved)),
        dict(check="an INTEGER cell offset leaves every quantity unchanged to "
                   "float noise, because it is a relabelling and not a "
                   "regridding",
             passed=bool(int_same),
             detail={k: [zero[k], m_int[k]] for k in keys}),
    ]

    spread = {k: dict(min=min(r[k] for r in rows), max=max(r[k] for r in rows),
                      spread=round(max(r[k] for r in rows)
                                   - min(r[k] for r in rows), 6))
              for k in keys}
    spread_fixed = {k: dict(min=min(r[k] for r in rows_fixed),
                            max=max(r[k] for r in rows_fixed),
                            spread=round(max(r[k] for r in rows_fixed)
                                         - min(r[k] for r in rows_fixed), 6))
                    for k in keys}
    part_d = dict(
        question="is the Part C spread really the Part B pitch defect wearing "
                 "a phase costume?",
        method="the identical sweep with exact_pitch=True, one flag, nothing "
               "else changed",
        spread_as_is=spread["facet_coverage_pct"]["spread"],
        spread_with_exact_pitch=spread_fixed["facet_coverage_pct"]["spread"],
        rows=rows_fixed, spread=spread_fixed)

    docout = dict(
        task="is the PRODUCTION coverage/footprint chain sensitive to the "
             "arbitrary phase of its raster?",
        dataset=name, date=args.stamp,
        status="SIDE ARTIFACT ONLY. Nothing adopted, nothing fitted, no "
               "threshold or comparison changed. canonical-2026-07-26-r2 "
               "remains canonical; published facet coverage remains 88.40 pct.",
        why="if the published number moves with an arbitrary grid alignment "
            "then coverage cannot function as a cross-pass detector, because a "
            "pass-to-pass change could be a re-alignment rather than a real "
            "improvement.",
        scalars=dict(cell_cu=round(float(cell), 10),
                     spacing_cu=round(float(spacing), 10),
                     band_cu=round(float(band), 10),
                     n_facets=len(facets)),
        part_a_origin_audit=ORIGIN_AUDIT,
        part_b_bin_pitch_defect=part_b,
        part_c=dict(offsets_as_fraction_of_cell=OFFSETS,
                    integer_offset=list(INTEGER_OFFSET),
                    rows=rows, integer_offset_row=m_int,
                    spread=spread),
        part_d_counterfactual=part_d,
        cross_checks=checks)
    p = out / f"production-phase-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2, default=float))

    print("\n  SPREAD OVER PHASE          as-is (production)      with exact_pitch")
    for k in keys:
        s, sf = spread[k], spread_fixed[k]
        print(f"    {k:<26} {s['spread']:>10.4f}            {sf['spread']:>10.4f}")
    print()
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check'][:88]}")
    print(f"\n  wrote {p}")


if __name__ == "__main__":
    main()
