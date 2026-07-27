# What ACTUALLY rejects blob 0's large near-flat plane?
#
#   .venv/Scripts/python.exe -u scripts/probe_blob0_rejection.py C:/odm/datasets/big_house
#
# Writes reports/big_house/blob0-rejection-<date>.json      (standing rule R2)
#
# ---------------------------------------------------------------------------
# A CORRECTION IN PROGRESS
#
# It was reported that min_pitch=5 excludes four well-fitted planes carrying
# 166,015 points and 19.04 cu^2 of gross surface, the largest being a 147,505
# point plane at 3.743 degrees in blob 0. That measurement came from RE-PEELING
# each blob with the pitch window opened to 0-90 and max_planes raised to 6.
#
# The recovery-pitch sweep then contradicted it. Lowering RECOVERY min_pitch all
# the way to 1.0 admits exactly ONE new facet, of 2,623 points and 0.326 cu^2,
# and blob 0's large plane never appears. So min_pitch is NOT what excludes it,
# and the 19.04 cu^2 figure describes planes that a DIFFERENT peeling
# configuration finds, not planes the pipeline is discarding for pitch.
#
# The likely reason is that opening the window changes the peel itself, not just
# what survives it. find_roof_planes runs a reassignment pass at the end: every
# point in every KEPT facet is pooled and handed to its nearest plane. With the
# window opened to 0-90 the near-vertical planes in blob 0 are kept, so they
# join that pool and the near-flat plane's final membership and fitted normal
# both change. A plane measured under one configuration is not the same plane
# under another.
#
# This probe stops guessing and reads the recovery pass's OWN candidate log at
# recovery min_pitch=1.0, which records every plane proposed, its quality, and
# the exact gate that rejected it.
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
from roofkit.measure import facet_area, rise_over_12              # noqa: E402
from roofkit import coverage as cov                               # noqa: E402

REPO = Path(__file__).resolve().parents[1]
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
MIN_AREA_POINTS_EQUIV = 3704
MAIN_MIN_PITCH = 5.0
RECOVERY_MIN_PITCH = 1.0     # low enough that pitch cannot be the reason


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    out = REPO / "reports" / Path(args.dataset).name

    points = leveled_points(cfg)
    spacing = median_nn_spacing(points)
    facets, band, s_full = discover_facets(points, cfg, probability=1.0,
                                           spacing=spacing,
                                           min_pitch=MAIN_MIN_PITCH)
    bar, _ = cov.calibrate_quality_bar(facets, s_full)

    d = []
    for f in facets:
        pts = np.asarray(f["points"], float)
        s_f = float(np.median(cov._nn(pts)))
        d.append(len(pts) * spacing ** 2 /
                 max(float(facet_area(pts, f["normal"],
                                      cfg["alpha_mult"] * s_f)), 1e-12))
    density = float(np.median(d))
    min_points = int(round(MIN_AREA_POINTS_EQUIV * density))
    min_area = MIN_AREA_POINTS_EQUIV * spacing ** 2

    cell = COVERAGE_CELL_MULT * s_full
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)

    log = []
    new = cov.recover_facets(points, blobs, None, dist, band, s_full, bar,
                             alpha_mult=cfg["alpha_mult"], probability=1.0,
                             min_pitch=RECOVERY_MIN_PITCH,
                             min_points_hard=min_points, min_area_hard=min_area,
                             log=log, grid=g)
    print(f"  recovery at min_pitch={RECOVERY_MIN_PITCH}: {len(new)} facets, "
          f"quality bar {bar:.3f}, point floor {min_points}, "
          f"area floor {min_area:.5f} cu^2\n")

    rows = []
    for e in log:
        if not e["planes"] and not e.get("peels"):
            continue
        keep = [p for p in e["planes"] if p["kept"]]
        rej = [p for p in e["planes"] if not p["kept"]]
        if not rej and not (e["area_cu2"] > 1.0 and not keep):
            continue
        rows.append(dict(blob=e["blob"],
                         plan_area_cu2=round(float(e["area_cu2"]), 4),
                         n_candidate=e["n_candidate"],
                         kept=keep, rejected=rej,
                         peels=e.get("peels", [])))
    rows.sort(key=lambda r: -r["plan_area_cu2"])

    for r in rows[:4]:
        print(f"  blob {r['blob']} ({r['plan_area_cu2']} cu^2 plan, "
              f"{r['n_candidate']:,} unexplained pts)")
        for p in r["peels"]:
            if "n_inliers" in p:
                print(f"      peel {p['peel']}: {p['n_inliers']:>7,} pts  "
                      f"{p['pitch_deg']:>7.3f} deg  kept_by_pitch="
                      f"{p['kept_by_pitch']}")
            else:
                print(f"      peel {p['peel']}: {p['stopped']}")
        for p in r["kept"] + r["rejected"]:
            print(f"      candidate {p['n']:>7,} pts  {p['pitch']:>7.2f} deg  "
                  f"quality {p['quality']:>6.3f} vs bar {p['bar']}  "
                  f"gross {p.get('gross_cu2')}  kept={p['kept']}"
                  + (f"  REJECTED BY: {p['rejected_by']}"
                     if p.get("rejected_by") else ""))
        print()

    doc = dict(
        task="what actually rejects blob 0's large near-flat plane, read from "
             "the recovery pass's own candidate log",
        dataset=Path(args.dataset).name, date=args.stamp,
        correction=(
            "An earlier report claimed min_pitch=5 excludes 166,015 points and "
            "19.04 cu^2 across four planes. That figure came from RE-PEELING "
            "each blob with the pitch window opened to 0-90 and max_planes "
            "raised to 6, which changes the peel itself and not merely what "
            "survives it: find_roof_planes ends with a reassignment pass over "
            "every KEPT plane, so opening the window lets near-vertical planes "
            "into that pool and alters the near-flat plane's membership and "
            "fitted normal. Those planes are not the ones the pipeline is "
            "discarding for pitch. The recovery-pitch sweep is the evidence: "
            "lowering recovery min_pitch to 1.0 admits ONE facet of 2,623 "
            "points, not four totalling 166,015."),
        settings=dict(main_min_pitch=MAIN_MIN_PITCH,
                      recovery_min_pitch=RECOVERY_MIN_PITCH,
                      quality_bar=round(float(bar), 4),
                      point_floor=min_points,
                      area_floor_cu2=round(float(min_area), 6)),
        n_recovered=len(new),
        blobs=rows,
        reading=("At recovery min_pitch=1.0 the pitch window cannot be the "
                 "reason for any rejection. Whatever gate appears in "
                 "'rejected_by' below is the real one."),
    )
    p = out / f"blob0-rejection-{args.stamp}.json"
    p.write_text(json.dumps(doc, indent=2, default=float))
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
