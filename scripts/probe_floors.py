# Task 6 step 4: re-measure the size-floor bands, and put MIN_POINTS into a
# transferable form.
#
#   .venv/Scripts/python.exe -u scripts/probe_floors.py C:/odm/datasets/big_house
#
# Writes reports/big_house/floors-<date>.json      (standing rule R2)
#
# ---------------------------------------------------------------------------
# WHY THIS CANNOT BE MEASURED ON THE CANONICAL STATE
#
# The canonical state was built WITH the floors applied, so by construction it
# contains nothing below them. Measuring "is there an empty band around the
# floor?" on that state would be circular: the band is empty because the floor
# emptied it.
#
# So this probe re-runs the full pipeline UNFLOORED (no min_points_hard, no
# min_area_hard, only the small stability floor of 300 that has always been
# there) and measures the size distribution that the pipeline produces when
# nothing is filtered. That is the same kind of state the 2026-07-23 run was,
# which is what the original band claim was measured on.
#
# WHAT AN "EMPTY BAND" ARGUES. A threshold sitting in a gap in the data is a
# threshold whose exact value does not matter: move it anywhere inside the gap
# and not one facet changes side. That is much stronger than a threshold tuned
# to a number, because it cannot have been fitted to the answer. If the gap has
# closed, the honest report is that it closed, NOT a new floor chosen to
# recreate one.
#
# ONE HONEST LIMITATION, stated up front: lowering the floor does not merely
# ADD small facets to the canonical list. The floor is pushed into RANSAC as its
# min_points, and a peeled plane removes its points from the cloud before the
# next peel, so a lower floor produces a genuinely different decomposition, not
# a superset. The unfloored list is therefore its own state and is compared as
# a distribution, never facet-by-facet against the canonical one.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                           # noqa: E402
from recon_common import discover_facets                         # noqa: E402
from roofkit.stats import median_nn_spacing                      # noqa: E402
from roofkit.segment import level_cloud                          # noqa: E402
from roofkit.measure import up_from_tilt, facet_area             # noqa: E402
from roofkit import coverage as cov                              # noqa: E402

COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15

# The floors as currently adopted.
MIN_POINTS = 2000
MIN_AREA_POINTS_EQUIV = 3704          # MIN_AREA_CU2 = this x spacing^2

# The bands claimed on 2026-07-23, quoted for comparison. That state can never
# be recomputed, so these can only be quoted.
OLD_CLAIM = dict(
    source="2026-07-23 facet state (superseded)",
    point_band="smallest accepted facet 664 points, next 10,614: the 2000 "
               "floor sat in an empty band",
    area_band="smallest accepted facet 0.019 cu^2, next 0.378 cu^2: the 0.10 "
              "floor sat in an empty band",
    caveat="the area figures quoted were NET areas, while the gate that "
           "actually runs at recovery time tests GROSS alpha area. This probe "
           "measures the gate's own quantity.")

REPO = Path(__file__).resolve().parents[1]


def gaps(values, floor, label):
    """Sort the values and find the interval containing `floor`. Returns the
    neighbours on each side and the gap width, so 'the floor sits in an empty
    band' becomes a number instead of an impression."""
    v = np.sort(np.asarray(values, float))
    below = v[v < floor]
    above = v[v >= floor]
    lo = float(below[-1]) if len(below) else None
    hi = float(above[0]) if len(above) else None
    row = dict(quantity=label, floor=float(floor),
               n_below_floor=int(len(below)), n_above_floor=int(len(above)),
               nearest_below=lo, nearest_above=hi)
    if lo is not None and hi is not None:
        row["gap_width"] = round(hi - lo, 6)
        row["gap_ratio_hi_over_lo"] = (round(hi / lo, 2) if lo > 0 else None)
        # How far the floor could move without changing a single decision,
        # as a fraction of the floor itself. Large = the value is not tuned.
        row["floor_may_move_down_to"] = round(lo, 6)
        row["floor_may_move_up_to"] = round(hi, 6)
        row["slack_pct_down"] = round(100.0 * (floor - lo) / floor, 1)
        row["slack_pct_up"] = round(100.0 * (hi - floor) / floor, 1)
        row["in_empty_band"] = True
    else:
        row["in_empty_band"] = False
        row["note"] = ("no facet on one side of the floor, so there is no "
                       "band to sit inside; the floor is at the edge of the "
                       "distribution, not in a gap")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    out = REPO / "reports" / Path(args.dataset).name
    out.mkdir(parents=True, exist_ok=True)

    points = np.load(cfg["roof_path"])
    if cfg["level_tilt_deg"] is not None:
        points = level_cloud(points, up_from_tilt(cfg["level_tilt_deg"],
                                                  cfg["level_uphill_az_deg"]))
    spacing = median_nn_spacing(points)
    min_area = MIN_AREA_POINTS_EQUIV * spacing ** 2
    print(f"  spacing {spacing:.6f} cu   min_area floor {min_area:.5f} cu^2")

    # --- the UNFLOORED run -------------------------------------------------
    facets, band, s_full = discover_facets(points, cfg, probability=1.0,
                                           spacing=spacing)
    bar, _ = cov.calibrate_quality_bar(facets, s_full)
    cell = COVERAGE_CELL_MULT * s_full
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    log = []
    new = cov.recover_facets(points, blobs, None, dist, band, s_full, bar,
                             alpha_mult=cfg["alpha_mult"], probability=1.0,
                             min_points_hard=None, min_area_hard=None,
                             log=log)
    print(f"  UNFLOORED: {len(facets)} main + {len(new)} recovered = "
          f"{len(facets) + len(new)}   (canonical floored run: 8 + 17 = 25)")

    # Gross alpha area for every recovered facet, computed the same way the
    # area floor computes it at recovery time (the facet's OWN local spacing,
    # not the whole cloud's), so the numbers are directly comparable to the gate.
    rows = []
    for k, f in enumerate(new, start=len(facets)):
        pts = np.asarray(f["points"], float)
        s_f = float(np.median(cov._nn(pts)))
        gross = float(facet_area(pts, f["normal"], cfg["alpha_mult"] * s_f))
        rows.append(dict(facet=k, blob=int(f["blob"]), n_points=int(len(pts)),
                         pitch_deg=round(float(f["pitch"]), 3),
                         gross_cu2=round(gross, 5),
                         quality=round(float(f["quality"]), 4),
                         points_per_spacing2=round(len(pts) * spacing ** 2 / max(gross, 1e-12), 3),
                         passes_point_floor=bool(len(pts) >= MIN_POINTS),
                         passes_area_floor=bool(gross >= min_area)))
    rows.sort(key=lambda r: r["n_points"])

    ns = [r["n_points"] for r in rows]
    gs = [r["gross_cu2"] for r in rows]
    band_pts = gaps(ns, MIN_POINTS, "recovered-facet point count")
    band_area = gaps(gs, min_area, "recovered-facet gross alpha area (cu^2)")

    # --- do the two floors ever disagree? ---------------------------------
    # If every facet the point floor rejects is also rejected by the area
    # floor, the point floor never binds and is redundant on this cloud. That
    # is measurable, and it is the cleanest resolution to "2000 is a per-site
    # constant in disguise": a floor that never decides anything should not be
    # carried as if it did.
    only_point = [r["facet"] for r in rows
                  if not r["passes_point_floor"] and r["passes_area_floor"]]
    only_area = [r["facet"] for r in rows
                 if r["passes_point_floor"] and not r["passes_area_floor"]]
    both = [r["facet"] for r in rows
            if not r["passes_point_floor"] and not r["passes_area_floor"]]

    # --- the transferable form --------------------------------------------
    # Point DENSITY, measured from the cloud: how many points a facet carries
    # per unit of its own surface area, in units of 1/spacing^2. If this is
    # near 1 the two floors are measuring the same thing in different units,
    # because a facet's point count is then just its area divided by spacing^2.
    dens = [r["points_per_spacing2"] for r in rows]

    # The SAME density measured on the MAIN facets. This is the version that
    # could actually drive the floor at runtime: main facets are found before
    # recovery runs, so their density is available at the moment the recovery
    # floor has to be chosen. Measuring it on the recovered facets, as above,
    # would be circular (the floor decides which recovered facets exist).
    main_rows = []
    for k, f in enumerate(facets):
        pts = np.asarray(f["points"], float)
        s_f = float(np.median(cov._nn(pts)))
        gross = float(facet_area(pts, f["normal"], cfg["alpha_mult"] * s_f))
        main_rows.append(dict(facet=k, n_points=int(len(pts)),
                              gross_cu2=round(gross, 5),
                              points_per_spacing2=round(
                                  len(pts) * spacing ** 2 / max(gross, 1e-12), 3)))
    main_dens = [r["points_per_spacing2"] for r in main_rows]

    density = dict(
        definition="n_points x spacing^2 / gross_area: points per spacing^2 of "
                   "facet surface. Dimensionless. Near 1.0 means one point per "
                   "spacing-square, which is what median nearest-neighbour "
                   "spacing means by construction. Below 1.0 means the alpha "
                   "surface spans area the points do not densely fill (bridged "
                   "gaps, trimmed clutter), which is normal.",
        recovered=dict(median=round(float(np.median(dens)), 3),
                       min=round(float(np.min(dens)), 3),
                       max=round(float(np.max(dens)), 3), n=len(dens)),
        main=dict(median=round(float(np.median(main_dens)), 3),
                  min=round(float(np.min(main_dens)), 3),
                  max=round(float(np.max(main_dens)), 3), n=len(main_dens),
                  per_facet=main_rows),
        which_to_use="main: it is measurable before recovery runs, so it can "
                     "set the recovery floor without circularity")

    equiv_points = MIN_AREA_POINTS_EQUIV * density["main"]["median"]
    equiv_points_recovered = MIN_AREA_POINTS_EQUIV * density["recovered"]["median"]
    doc = dict(
        task="Task 6 step 4: re-measure the size-floor bands on the current "
             "pipeline, and restate MIN_POINTS in transferable form",
        dataset=Path(args.dataset).name, date=args.stamp,
        method=dict(
            what="full pipeline at probability=1.0 with NO hard floors "
                 "(min_points_hard=None, min_area_hard=None), so the size "
                 "distribution is the one the pipeline produces unfiltered",
            why="the canonical state was built WITH the floors, so it contains "
                "nothing below them by construction; measuring the band there "
                "would be circular",
            limitation="a lower floor is not a superset: the floor is pushed "
                       "into RANSAC as min_points, and a peeled plane removes "
                       "its points before the next peel, so the unfloored run "
                       "is a different decomposition. It is compared as a "
                       "DISTRIBUTION, never facet-by-facet."),
        scalars=dict(spacing_cu=round(float(spacing), 6),
                     band_cu=round(float(band), 6),
                     min_points_floor=MIN_POINTS,
                     min_area_floor_cu2=round(float(min_area), 6),
                     min_area_form=f"{MIN_AREA_POINTS_EQUIV} x spacing^2"),
        unfloored_counts=dict(n_main=len(facets), n_recovered=len(new),
                              n_total=len(facets) + len(new),
                              canonical_floored_total=25),
        recovered_facets=rows,
        bands=dict(points=band_pts, area=band_area),
        old_claim=OLD_CLAIM,
        floor_interaction=dict(
            rejected_by_point_floor_only=only_point,
            rejected_by_area_floor_only=only_area,
            rejected_by_both=both,
            point_floor_ever_decisive=bool(only_point),
            reading=("If rejected_by_point_floor_only is empty, the point "
                     "floor never rejects anything the area floor does not "
                     "already reject on this cloud, so it is not doing "
                     "independent work here.")),
        density=density,
        transferable_form=dict(
            proposal=("MIN_POINTS = MIN_AREA_POINTS_EQUIV x d, where d is the "
                      "run's OWN measured surface point density (points per "
                      "spacing^2 of facet surface), taken as the median over "
                      "the main facets. Both inputs come from the cloud; "
                      "nothing is a raw constant."),
            derivation=(
                "A facet of gross area A holds about A x d / spacing^2 points, "
                "where d is measured from this run's main facets. The area "
                f"floor is MIN_AREA = {MIN_AREA_POINTS_EQUIV} x spacing^2, so "
                f"the point count it implies is {MIN_AREA_POINTS_EQUIV} x d. On "
                f"big_house d = {density['main']['median']}, giving "
                f"{equiv_points:.0f} points."),
            implied_point_floor_from_main_density=round(float(equiv_points), 0),
            implied_point_floor_from_recovered_density=round(
                float(equiv_points_recovered), 0),
            current_raw_floor=MIN_POINTS,
            ratio_current_over_implied=round(
                MIN_POINTS / max(equiv_points, 1e-9), 3),
            why_raw_2000_is_not_transferable=(
                "Point density depends on flight altitude and image overlap. "
                "2000 points covers one physical patch on big_house and a "
                "different one on a cloud flown differently, so a raw 2000 is a "
                "per-site constant wearing a scale-free costume. Every other "
                "length threshold in this pipeline is already expressed as a "
                "multiple of measured point spacing for exactly this reason."),
            does_it_make_the_floor_redundant=(
                "Algebraically the transferable form IS the area floor "
                "restated, so on a cloud of uniform density the two gates "
                "agree by construction and only one is doing work. They come "
                "apart where density varies BETWEEN facets: a sparse, "
                "spread-out sliver can span enough alpha area to clear the "
                "area floor while holding too few points for a stable plane "
                "fit. The measured per-facet density spread on this cloud is "
                f"{density['recovered']['min']} to "
                f"{density['recovered']['max']}, a factor of "
                f"{round(density['recovered']['max'] / max(density['recovered']['min'], 1e-9), 1)}, "
                "so that window is real here even though no facet landed in "
                "it. Keeping both is cheap; dropping the point floor on one "
                "cloud's evidence is not warranted."),
        ),
        recovered_facet_counts_sorted=ns,
        recovered_facet_gross_sorted=sorted(gs),
    )
    p = out / f"floors-{args.stamp}.json"
    p.write_text(json.dumps(doc, indent=2, default=float))

    print(f"\n  POINT band around floor {MIN_POINTS}:")
    print(f"    nearest below {band_pts['nearest_below']}, nearest above "
          f"{band_pts['nearest_above']}, in_empty_band="
          f"{band_pts['in_empty_band']}")
    print(f"  AREA band around floor {min_area:.5f} cu^2:")
    print(f"    nearest below {band_area['nearest_below']}, nearest above "
          f"{band_area['nearest_above']}, in_empty_band="
          f"{band_area['in_empty_band']}")
    print(f"\n  density (points per spacing^2 of surface):")
    print(f"    main facets      median {density['main']['median']}  "
          f"range {density['main']['min']}-{density['main']['max']}")
    print(f"    recovered facets median {density['recovered']['median']}  "
          f"range {density['recovered']['min']}-{density['recovered']['max']}")
    print(f"  transferable point floor = {MIN_AREA_POINTS_EQUIV} x d(main) = "
          f"{equiv_points:.0f} points   (currently adopted raw: {MIN_POINTS}, "
          f"ratio {MIN_POINTS / equiv_points:.3f})")
    print(f"  point floor decisive on its own: "
          f"{bool(only_point)}  (rejected by point floor only: {only_point})")
    print(f"\n  wrote {p}")


if __name__ == "__main__":
    main()
