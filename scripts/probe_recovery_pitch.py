# Should RECOVERY carry its own min_pitch, separate from MAIN DISCOVERY?
#
#   .venv/Scripts/python.exe -u scripts/probe_recovery_pitch.py C:/odm/datasets/big_house
#
# Writes reports/big_house/recovery-pitch-sweep-<date>.json  (standing rule R2)
#
# ---------------------------------------------------------------------------
# WHAT THIS IS AND IS NOT
#
# NOT a canonical state, and NOT an adoption. canonical-2026-07-26-r2 stays
# exactly as it is and the published coverage stays 88.40 percent. This writes
# one side diagnostic and nothing else. Adoption of any value gets
# pre-registered on the next site before that site is scored (Emmett,
# 2026-07-26), so choosing a number here would be exactly the wrong move.
#
# THE QUESTION. min_pitch=5 is right for MAIN DISCOVERY: it excludes a 4.04
# degree plane that fails the quality bar and whose plan footprint threads
# across all eight facets, which is a contour-band artifact rather than a
# surface. But main discovery and recovery are separate parameters that merely
# happen to share a value. Inside a residual blob the candidate has already
# passed through the quality bar, the point floor and the area floor, so the
# pitch window is doing much less work there. At 5 it discards four well-fitted
# planes carrying 166,015 points and 19.04 cu^2 of gross surface, all near
# 0.8:12, which reads as flat roof rather than artifact.
#
# WHY A SWEEP AND NOT A SPOT CHECK. A single lower value would show only that
# the number moved. What matters is whether there is a PLATEAU: a range of
# min_pitch over which the answer does not change. A threshold inside a plateau
# is defensible because its exact value cannot have been tuned to the result;
# a threshold on a slope is a fitted parameter wearing a principle's clothes.
# This is the same standard the size floors were held to (bands 15.9x and 9.0x
# wide) and the same standard main discovery's min_pitch only barely meets
# (about 1.8 degrees).
#
# METHOD. MAIN DISCOVERY IS HELD AT EXACTLY 5.0 in every run. Only recovery's
# min_pitch varies. The full pipeline is re-run for each value rather than
# reusing one discovery pass, because Open3D's RANSAC draws from a single global
# stream: reusing a discovery and looping recovery would start each recovery at
# a different point in that stream, and the sweep would be measuring stream
# position as well as pitch. Re-running is slower and is the only way the
# comparison means what it says.
#
# BUILT-IN CROSS-CHECK: the row at recovery min_pitch = 5.0 must reproduce
# canonical-2026-07-26-r2 (29 facets). If it does not, this probe is measuring
# something other than what it claims and every other row is void.
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
from roofkit.measure import facet_area, rise_over_12, is_low_slope  # noqa: E402
from roofkit.segment import assert_single_ownership               # noqa: E402
from roofkit import coverage as cov                               # noqa: E402

REPO = Path(__file__).resolve().parents[1]
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
MIN_AREA_POINTS_EQUIV = 3704

MAIN_MIN_PITCH = 5.0        # HELD EXACTLY, never swept
# Chosen to straddle the four excluded planes (3.574, 3.624, 3.743, 4.010 deg)
# so the sweep can see each one cross the threshold, and to continue well below
# them so a plateau, if there is one, has room to show.
SWEEP = [5.0, 4.5, 4.0, 3.7, 3.5, 3.0, 2.0, 1.0]


def run_one(points, cfg, spacing, rec_min_pitch):
    facets, band, s_full = discover_facets(points, cfg, probability=1.0,
                                           spacing=spacing,
                                           min_pitch=MAIN_MIN_PITCH)
    bar, _ = cov.calibrate_quality_bar(facets, s_full)

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
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    new = cov.recover_facets(points, blobs, None, dist, band, s_full, bar,
                             alpha_mult=cfg["alpha_mult"], probability=1.0,
                             min_pitch=rec_min_pitch,
                             min_points_hard=min_points, min_area_hard=min_area,
                             grid=g)
    allf = facets + new
    assert_single_ownership(allf, where=f"recovery min_pitch={rec_min_pitch}")

    masks_post, _, _, _ = cov.coverage_masks(points, allf, band, cell)
    split = cov.split_coverage(masks_post, cell)

    rec_gross = 0.0
    for f in new:
        pts = np.asarray(f["points"], float)
        s_f = float(np.median(cov._nn(pts)))
        rec_gross += float(facet_area(pts, f["normal"],
                                      cfg["alpha_mult"] * s_f))

    pitches = sorted(round(float(f["pitch"]), 3) for f in new)
    low = [f for f in new if is_low_slope(f["pitch"])]
    return dict(
        recovery_min_pitch=rec_min_pitch,
        main_min_pitch=MAIN_MIN_PITCH,
        derived_min_points=min_points,
        n_main=len(facets), n_recovered=len(new), n_total=len(allf),
        n_low_slope=len(low),
        n_below_5_deg=sum(1 for p in pitches if p < 5.0),
        recovered_gross_cu2=round(rec_gross, 4),
        lowest_recovered_pitch_deg=(pitches[0] if pitches else None),
        recovered_pitches_deg=pitches,
        facet_coverage_pct=split["facet_coverage"]["pct"],
        unexplained_cu2=split["facet_coverage"]["unexplained_cu2"],
        density_testable_pct=split["density_testable_fraction"]["pct"],
        sub5_facets=[dict(pitch_deg=round(float(f["pitch"]), 3),
                          rise_over_12=round(rise_over_12(f["pitch"]), 2),
                          n_points=int(len(f["points"])),
                          quality=round(float(f["quality"]), 3))
                     for f in new if f["pitch"] < 5.0],
    )


def plateaus(rows, key):
    """Runs of consecutive sweep values over which `key` does not change.
    A threshold inside a wide run is defensible; one on a slope is fitted."""
    out, start = [], 0
    for i in range(1, len(rows) + 1):
        if i == len(rows) or rows[i][key] != rows[start][key]:
            if i - start >= 2:
                hi = rows[start]["recovery_min_pitch"]
                lo = rows[i - 1]["recovery_min_pitch"]
                out.append(dict(value=rows[start][key],
                                min_pitch_from=lo, min_pitch_to=hi,
                                width_deg=round(hi - lo, 3),
                                n_sweep_points=i - start))
            start = i
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    out = REPO / "reports" / Path(args.dataset).name

    points = leveled_points(cfg)
    spacing = median_nn_spacing(points)
    print(f"  {len(points):,} points; main discovery HELD at min_pitch="
          f"{MAIN_MIN_PITCH}, recovery swept {SWEEP}\n")

    rows = []
    for v in SWEEP:
        r = run_one(points, cfg, spacing, v)
        rows.append(r)
        print(f"  recovery min_pitch {v:>4.1f}:  {r['n_total']:>3} facets "
              f"({r['n_recovered']} recovered, {r['n_below_5_deg']} below 5 deg)"
              f"   recovered gross {r['recovered_gross_cu2']:>8.3f} cu^2"
              f"   facet coverage {r['facet_coverage_pct']:>6.2f}%"
              f"   lowest {r['lowest_recovered_pitch_deg']}")

    doc = dict(
        task="does RECOVERY need its own min_pitch, separate from main "
             "discovery? A sweep, looking for a plateau.",
        dataset=Path(args.dataset).name, date=args.stamp,
        status="DIAGNOSTIC ONLY. No value is adopted, no canonical state is "
               "written, and canonical-2026-07-26-r2 is unchanged. Published "
               "coverage remains 88.40 percent. Adoption is pre-registered on "
               "the next site before that site is scored.",
        method=dict(
            main_min_pitch_held_at=MAIN_MIN_PITCH,
            swept=SWEEP,
            full_rerun_per_value=("the whole pipeline is re-run for each value "
                                  "rather than reusing one discovery pass, "
                                  "because Open3D's RANSAC draws from a single "
                                  "GLOBAL stream. Reusing a discovery and "
                                  "looping recovery would start each recovery "
                                  "at a different point in that stream, so the "
                                  "sweep would measure stream position as well "
                                  "as pitch."),
            what_a_plateau_argues=("a range over which the answer does not "
                                   "change. A threshold inside one cannot have "
                                   "been tuned to the result. The size floors "
                                   "sit in bands 15.9x and 9.0x wide; main "
                                   "discovery's min_pitch has only about 1.8 "
                                   "degrees, which is already thin.")),
        cross_check=dict(
            expectation="the row at recovery min_pitch = 5.0 must reproduce "
                        "canonical-2026-07-26-r2: 29 facets total, 21 "
                        "recovered.",
            observed_n_total=rows[0]["n_total"],
            observed_n_recovered=rows[0]["n_recovered"],
            passed=bool(rows[0]["n_total"] == 29 and
                        rows[0]["n_recovered"] == 21),
            note="if this fails, the probe is measuring something other than "
                 "what it claims and every other row is void."),
        sweep=rows,
        plateaus=dict(
            by_total_facet_count=plateaus(rows, "n_total"),
            by_facet_coverage=plateaus(rows, "facet_coverage_pct"),
            reading="a wide plateau in BOTH means the exact value does not "
                    "matter inside it. A plateau in count but not coverage "
                    "means the same facets are found with shifting membership, "
                    "which is weaker evidence."),
    )
    p = out / f"recovery-pitch-sweep-{args.stamp}.json"
    p.write_text(json.dumps(doc, indent=2, default=float))

    print(f"\n  cross-check (min_pitch 5.0 reproduces canonical r2): "
          f"{doc['cross_check']['passed']}")
    print("\n  PLATEAUS in total facet count:")
    for pl in doc["plateaus"]["by_total_facet_count"]:
        print(f"    {pl['value']} facets over min_pitch "
              f"{pl['min_pitch_from']} to {pl['min_pitch_to']} "
              f"({pl['width_deg']} deg wide)")
    print("  PLATEAUS in facet coverage:")
    for pl in doc["plateaus"]["by_facet_coverage"]:
        print(f"    {pl['value']}% over min_pitch {pl['min_pitch_from']} to "
              f"{pl['min_pitch_to']} ({pl['width_deg']} deg wide)")
    print(f"\n  wrote {p}")


if __name__ == "__main__":
    main()
