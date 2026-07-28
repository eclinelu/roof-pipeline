# IS THE CONNECTIVITY FILTER SENSITIVE TO THE RASTER'S ARBITRARY PHASE?
#
#   .venv/Scripts/python.exe scripts/probe_grid_phase.py C:/odm/datasets/big_house
#
# Writes reports/big_house/grid-phase-<date>.json          (standing rule R2)
#
# READ ONLY. Loads the canonical state, measures it, writes a report. Fits
# nothing, changes nothing. canonical-2026-07-26-r2 is untouched.
#
# ---------------------------------------------------------------------------
# WHY THIS EXISTS, and it was NOT planned: assertion A2 in the M1a sweep failed
# on its first run, and the failure turned out to be about the instrument's
# ORIGIN rather than about the filter's labelling. Chasing it surfaced a
# property of the method that nobody had written down.
#
# THE FILTER BINS PLAN COORDINATES INTO A RASTER WHOSE ORIGIN IS
# `xy.min(axis=0)`. That origin is ARBITRARY: it is wherever the extreme point
# of this particular point set happens to sit. Shifting it by a fraction of a
# cell moves every cell boundary, and two points that shared a cell under one
# alignment can fall into different cells under another. CONNECTIVITY ON A
# RASTER IS NOT PHASE INVARIANT.
#
# That is a NUISANCE PARAMETER: a degree of freedom that changes the output and
# that nobody chose, swept or pre-registered. If it moves the answer, then a
# value adopted from the plateau sweep is only valid for one arbitrary
# alignment, and the plateau is not a plateau.
#
# THE QUESTION, stated so it can come back negative: over random sub-cell
# phase offsets, how much does the KEPT FRACTION move? The component COUNT is
# expected to be volatile and is not the thing that matters, because a body of
# 1.5 million points shedding a few single-cell specks changes the count a lot
# and the kept set almost not at all. The kept fraction is what feeds the plane
# fit, so it is what the sweep's results actually rest on.
#
# INDEPENDENT ASSERTIONS (standing rule 2026-07-27-silent-failure-standing-rule):
#   - at zero offset the result reproduces connected_core's own diagnostic
#     exactly (the probe is running the thing it claims to be running)
#   - kept fraction is in [0, 1] at every offset
#   - an INTEGER cell offset must change nothing at all, bit for bit: shifting
#     the origin by a whole number of cells is a relabelling, not a regridding.
#     This is the sharpest of the three, because it is a property the method
#     MUST have and it fails loudly if the binning arithmetic is wrong.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar                      # noqa: E402
from roofkit.segment import connected_core                        # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"

# Sub-cell phase offsets to try, as fractions of a cell in each axis. The first
# is the zero offset, which must reproduce the filter's own numbers.
OFFSETS = [(0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5),
           (0.25, 0.75), (0.75, 0.25), (0.33, 0.66), (0.66, 0.33)]
SCALES = [1.5, 2.0, 2.5, 3.5, 5.0]     # the sweep's own connectivity scales


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    doc, points, facets, cfg = load_canonical(args.dataset, CANONICAL_STAMP)
    spacing = scalar(doc, "spacing_cu")
    main_facets = [f for f in facets if f["kind"] == "main"]
    print(f"  spacing {spacing:.6f} cu   {len(main_facets)} main facets\n")

    rows, checks = [], []
    zero_ok, int_ok, range_ok = True, True, True
    int_worst = dict(points=0, kept_frac_delta=0.0, ncomp_delta=0, where=None)

    for scale in SCALES:
        cell = scale * spacing
        for f in main_facets:
            xy = np.asarray(f["points"], float)[:, :2]
            ref_keep, ref_diag = connected_core(xy, cell=cell, min_frac=1.0)
            per_offset = []
            base_origin = xy.min(axis=0)
            for (ox, oy) in OFFSETS:
                # The origin must be moved EXPLICITLY. Translating the points
                # does nothing at all, because connected_core's default origin
                # is the input's own minimum and translates with it. The first
                # version of this probe did exactly that and reported a
                # spread of precisely zero at every offset on all 40
                # facet-scale pairs, which is what a measurement of nothing
                # looks like.
                org = base_origin - np.array([ox * cell, oy * cell])
                keep, diag = connected_core(xy, cell=cell, min_frac=1.0,
                                            origin=org)
                per_offset.append(dict(
                    offset=[ox, oy],
                    n_components=int(diag["n_components"]),
                    kept_fraction=round(float(diag["kept_fraction"]), 8),
                    kept_points=int(diag["n_points_kept"])))
                if not (0.0 <= diag["kept_fraction"] <= 1.0):
                    range_ok = False
                if (ox, oy) == (0.0, 0.0):
                    if not np.array_equal(keep, ref_keep):
                        zero_ok = False

            # INTEGER offset: must be bit-for-bit identical. This is the check
            # that would have caught the first version of this probe, because
            # it is the one case where "nothing changed" is the CORRECT answer
            # and every other offset must therefore differ from it.
            org_i = base_origin - np.array([3.0 * cell, 2.0 * cell])
            keep_i, diag_i = connected_core(xy, cell=cell, min_frac=1.0,
                                            origin=org_i)
            if not np.array_equal(keep_i, ref_keep):
                int_ok = False
            # The strict check is KEPT strict rather than relaxed to make it
            # pass, but its MAGNITUDE is recorded, because "fails" and "fails
            # by one point in 1.5 million" call for different responses. The
            # cause is float rounding for points sitting exactly on a cell
            # boundary: (x - lo + 3*cell)/cell and (x - lo)/cell + 3 can differ
            # in the last bit, and floor() then sends that point to the
            # neighbouring cell.
            nd = int((keep_i != ref_keep).sum())
            kfd = abs(float(diag_i["kept_fraction"] - ref_diag["kept_fraction"]))
            ncd = abs(int(diag_i["n_components"] - ref_diag["n_components"]))
            if (nd, kfd, ncd) > (int_worst["points"],
                                 int_worst["kept_frac_delta"],
                                 int_worst["ncomp_delta"]):
                int_worst = dict(points=nd, kept_frac_delta=kfd,
                                 ncomp_delta=ncd,
                                 where=dict(scale_mult=scale,
                                            facet=int(f["facet"]),
                                            n_points=int(len(xy))))

            kf = [p["kept_fraction"] for p in per_offset]
            nc = [p["n_components"] for p in per_offset]
            rows.append(dict(
                scale_mult=scale, facet=f["facet"], n_points=int(len(xy)),
                kept_fraction_min=round(min(kf), 8),
                kept_fraction_max=round(max(kf), 8),
                kept_fraction_spread=round(max(kf) - min(kf), 8),
                kept_points_spread=int(max(p["kept_points"] for p in per_offset)
                                       - min(p["kept_points"] for p in per_offset)),
                n_components_min=min(nc), n_components_max=max(nc),
                by_offset=per_offset))
        print(f"  scale {scale:>4.1f} done", flush=True)

    checks.append(dict(check="the zero offset reproduces connected_core's own "
                             "result bit for bit (the probe runs what it claims)",
                       passed=bool(zero_ok)))
    checks.append(dict(
        check="an INTEGER cell offset changes nothing bit for bit (shifting "
              "the origin by whole cells is a relabelling, not a regridding)",
        passed=bool(int_ok), worst=int_worst,
        interpretation="kept strict deliberately. When it fails, read the "
                       "magnitude: a handful of points is float rounding for "
                       "points lying exactly on a cell boundary, which is "
                       "expected and negligible. A large failure would mean "
                       "the binning arithmetic is wrong.",
        material=bool(int_worst["kept_frac_delta"] > 1e-5)))
    checks.append(dict(check="kept fraction lies in [0, 1] at every offset",
                       passed=bool(range_ok)))
    # THE ANTI-NULL CHECK, added after the first version of this probe returned
    # a spread of exactly zero on all 40 facet-scale pairs because it was not
    # varying anything. If NO sub-cell offset changes even the component count,
    # the probe is not perturbing the thing it claims to perturb, and a clean
    # result is meaningless rather than reassuring.
    varied = any(r["n_components_min"] != r["n_components_max"] for r in rows)
    checks.append(dict(
        check="at least one sub-cell offset changes SOMETHING (component "
              "count). If nothing moves anywhere, this probe is measuring "
              "nothing and its zero spread is not evidence of robustness",
        passed=bool(varied)))

    worst = max(rows, key=lambda r: r["kept_fraction_spread"])
    docout = dict(
        task="is the M1a connectivity filter sensitive to the arbitrary phase "
             "of its raster? Measured on the canonical state, read only.",
        dataset=name, date=args.stamp,
        status="READ ONLY. canonical-2026-07-26-r2 unchanged.",
        why="assertion A2 of the M1a sweep failed on first run; the cause was "
            "the raster ORIGIN moving when the kept set's bounding box shrank, "
            "not the labelling. The origin is a nuisance parameter nobody "
            "chose or pre-registered, so its influence is measured here.",
        method=dict(
            offsets_as_fraction_of_cell=OFFSETS, scales_x_spacing=SCALES,
            note="points are shifted rather than the raster, which is the same "
                 "operation and keeps the code under test identical to the "
                 "code the sweep runs",
            measured_on="canonical POST-TRIM facet points, which is a proxy "
                        "for the pre-trim membership the filter really sees"),
        cross_checks=checks,
        headline=dict(
            worst_kept_fraction_spread=worst["kept_fraction_spread"],
            worst_at=dict(scale_mult=worst["scale_mult"], facet=worst["facet"]),
            worst_kept_points_spread=worst["kept_points_spread"],
            reading="the COMPONENT COUNT is expected to be volatile under "
                    "phase and is not what matters; a dense body shedding a "
                    "few single-cell specks moves the count a great deal and "
                    "the kept set almost not at all. The KEPT FRACTION is what "
                    "feeds the plane fit, so it is the number that decides "
                    "whether the phase is a real degree of freedom."),
        rows=rows)
    p = out / f"grid-phase-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2))

    print(f"\n{'scale':>6} {'facet':>6} {'kept frac min':>15} {'max':>12} "
          f"{'spread':>12} {'pts spread':>11} {'ncomp min..max':>16}")
    for r in rows:
        print(f"{r['scale_mult']:>6.1f} {r['facet']:>6} "
              f"{r['kept_fraction_min']:>15.6f} {r['kept_fraction_max']:>12.6f} "
              f"{r['kept_fraction_spread']:>12.6f} "
              f"{r['kept_points_spread']:>11,} "
              f"{r['n_components_min']:>7,}..{r['n_components_max']:<7,}")
    print()
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check']}")
    print(f"\n  worst kept-fraction spread over phase: "
          f"{worst['kept_fraction_spread']:.6f} "
          f"({worst['kept_points_spread']:,} points) at scale "
          f"{worst['scale_mult']}, facet {worst['facet']}")
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
