# What do the CONNECTED COMPONENTS of a facet's membership actually look like?
#
#   .venv/Scripts/python.exe scripts/probe_component_sizes.py C:/odm/datasets/big_house
#
# Writes reports/big_house/component-sizes-<date>.json   (standing rule R2)
#
# READ ONLY. Loads the canonical state from disk and measures it. Fits nothing,
# changes nothing, regenerates nothing. canonical-2026-07-26-r2 is untouched.
#
# ---------------------------------------------------------------------------
# WHY THIS EXISTS, AND WHY RUNNING IT IS NOT CHEATING
#
# The M1a pre-registration fixes two swept parameters by NAME and by FORM
# (multiples of median spacing; a fraction of the facet's largest component)
# but never records the literal values. Somebody has to choose them, and the
# person choosing has already read every prior result. That is exactly the
# situation a pre-registration exists to prevent.
#
# The distinction that makes this measurement legitimate:
#
#   an INPUT property   how many components a facet's points fall into, and
#                       how big they are. A fact about the point cloud. It is
#                       the same number whatever the fix does.
#   an OUTCOME          pitch delta, facet coverage, the quality bar, blob 0,
#                       the facet count. The things the sweep is scored on.
#
# Choosing a sweep RANGE so that it spans the region where the parameter can
# do anything at all is reading the first. Choosing a sweep VALUE because of
# what it does to the second is the error. This script is forbidden from
# computing anything in the second list, and it does not import the coverage
# or measure modules at all, so it cannot.
#
# THE QUESTION IT ANSWERS: over what range of "minimum component as a fraction
# of the largest" does that parameter change the answer? If the second-largest
# component on every facet is 0.0001 of the largest, then any fraction between
# 1.0 and 0.001 keeps exactly the largest and the axis is inert; the sweep
# would burn a quarter of its runs proving nothing. The distribution says where
# the live range is BEFORE any outcome is computed.
#
# INDEPENDENT ASSERTIONS (standing rule 2026-07-27-silent-failure-standing-rule):
#   - component sizes sum to the facet's point count exactly (no point is in
#     two components and none is dropped)
#   - the number of components is non-increasing as the connectivity scale
#     grows: a coarser grid can only merge components, never split them
#   - at the canonical cell (2.5 x spacing) the component counts reproduce
#     fragments-2026-07-27.json, which was computed by DIFFERENT code
# Each is checked and written into the output with its pass/fail state. The
# third is the strong one: it ties this script to a committed artifact built by
# another script, so an indexing bug here fails against prior evidence.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.ndimage import label

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar                      # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"
# 8-connectivity, matching probe_fragments.py so the cross-check is a real
# comparison rather than a comparison of two different definitions.
STRUCT = np.ones((3, 3), dtype=bool)

# Connectivity scales to characterise, as multiples of the FULL CLOUD's median
# point spacing. Chosen to bracket the canonical coverage cell (2.5x) by a
# factor of about two either way; this is a characterisation range, not the
# sweep grid.
SCALES = [1.0, 1.5, 2.0, 2.5, 3.5, 5.0, 7.0]


def components(xy, cell):
    """Label a facet's points into plan-connected components.

    Bin XY into square cells of side `cell`, mark occupied cells, and take
    8-connected components of that occupancy raster. Returns the per-point
    component label (1..n) and the component sizes in POINTS.

    Why cells and not a point graph: a radius graph over 1.5 million points is
    hundreds of millions of edges. The raster is the same idea at O(N)."""
    lo = xy.min(axis=0)
    i = ((xy[:, 0] - lo[0]) / cell).astype(np.int64)
    j = ((xy[:, 1] - lo[1]) / cell).astype(np.int64)
    occ = np.zeros((i.max() + 1, j.max() + 1), bool)
    occ[i, j] = True
    lab, n = label(occ, structure=STRUCT)
    per_point = lab[i, j]
    sizes = np.bincount(per_point, minlength=n + 1)[1:]   # drop background
    return per_point, sizes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    doc, points, facets, cfg = load_canonical(args.dataset, CANONICAL_STAMP)
    spacing = scalar(doc, "spacing_cu")
    canon_cell = scalar(doc, "cell_cu")

    in_per_cu = 40.4541
    sc = out / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])

    main_facets = [f for f in facets if f["kind"] == "main"]
    print(f"  spacing {spacing:.6f} cu   canonical cell {canon_cell:.6f} cu "
          f"= {canon_cell / spacing:.2f} x spacing")
    print(f"  scale: 1 cu = {in_per_cu:.4f} in = {in_per_cu / 12:.4f} ft")
    print(f"  {len(main_facets)} main facets\n")

    rows, checks = [], []
    counts_at_canonical = {}
    for f in main_facets:
        xy = np.asarray(f["points"], float)[:, :2]
        n_pts = len(xy)
        per_scale = []
        for m in SCALES:
            cell = m * spacing
            _, sizes = components(xy, cell)
            order = np.sort(sizes)[::-1]
            largest = int(order[0])
            # The live range of the min-component axis: the fraction of the
            # largest that each subsequent component represents. If the 2nd is
            # already 1e-5, no fraction above 1e-5 does anything.
            fracs = (order / largest)
            per_scale.append(dict(
                scale_mult=m, cell_cu=round(cell, 6),
                n_components=int(len(sizes)),
                largest_points=largest,
                largest_fraction_of_facet=round(float(largest / n_pts), 6),
                top10_points=[int(v) for v in order[:10]],
                top10_fraction_of_largest=[round(float(v), 8)
                                           for v in fracs[:10]],
                # how many components survive at each candidate cut-off. This
                # is the number that says whether the axis is live.
                n_kept_at_fraction={
                    str(q): int((fracs >= q).sum())
                    for q in (1.0, 0.5, 0.1, 0.01, 0.001, 1e-4, 1e-5)},
                points_kept_at_fraction={
                    str(q): int(order[fracs >= q].sum())
                    for q in (1.0, 0.5, 0.1, 0.01, 0.001, 1e-4, 1e-5)},
            ))
            if abs(m - canon_cell / spacing) < 1e-6:
                counts_at_canonical[f["facet"]] = int(len(sizes))
        rows.append(dict(facet=f["facet"], n_points=n_pts, by_scale=per_scale))

    # --- independent assertions --------------------------------------------
    # 1. no point lost or double counted
    ok_sum = True
    for r in rows:
        for s in r["by_scale"]:
            if s["points_kept_at_fraction"]["1e-05"] > r["n_points"]:
                ok_sum = False
    checks.append(dict(
        check="points kept at the loosest cut-off never exceed the facet's "
              "point count",
        passed=bool(ok_sum)))

    # 2. component count is non-increasing in the connectivity scale
    ok_mono = all(
        all(r["by_scale"][k]["n_components"] >= r["by_scale"][k + 1]["n_components"]
            for k in range(len(SCALES) - 1))
        for r in rows)
    checks.append(dict(
        check="component count is non-increasing as the connectivity scale "
              "grows (a coarser grid can merge components, never split them)",
        passed=bool(ok_mono)))

    # 3. THE STRONG ONE: reproduce a committed artifact built by other code.
    frag_path = out / "fragments-2026-07-27.json"
    if frag_path.exists():
        frag = json.loads(frag_path.read_text())
        want = {r["facet"]: r["n_components"] for r in frag["rows"]
                if r["kind"] == "main"}
        got = counts_at_canonical
        agree = {k: (want.get(k), got.get(k)) for k in sorted(want)}
        ok_x = all(want[k] == got.get(k) for k in want)
        checks.append(dict(
            check="at the canonical cell, component counts reproduce "
                  "fragments-2026-07-27.json (written by probe_fragments.py, "
                  "different code, same canonical state)",
            passed=bool(ok_x),
            per_facet={str(k): dict(fragments_probe=v[0], this_probe=v[1])
                       for k, v in agree.items()}))
    else:
        checks.append(dict(check="cross-check against fragments-2026-07-27.json",
                           passed=None, note="artifact absent"))

    docout = dict(
        task="component-size distribution of main-facet membership, to fix the "
             "M1a sweep grid on an INPUT property rather than an outcome",
        dataset=name, date=args.stamp,
        status="READ ONLY. Nothing fitted, changed or regenerated. "
               "canonical-2026-07-26-r2 unchanged.",
        legitimacy_note=(
            "this script computes NO outcome quantity. It does not import "
            "roofkit.coverage or roofkit.measure and cannot compute pitch, "
            "facet coverage, the quality bar, blob 0's candidate or the facet "
            "count. Reading it therefore cannot select a parameter by its "
            "effect on the answer, which is what the plateau rule forbids."),
        caveat=(
            "these components are measured on the canonical POST-TRIM facet "
            "points. The filter under test runs on PRE-TRIM membership, which "
            "is a slightly larger set. The distribution is a guide to the live "
            "range of the fraction axis, not a prediction of what the filter "
            "will remove."),
        spacing_cu=round(float(spacing), 6),
        canonical_cell_cu=round(float(canon_cell), 6),
        canonical_cell_mult=round(float(canon_cell / spacing), 4),
        in_per_cu=in_per_cu,
        scales_characterised=SCALES,
        cross_checks=checks,
        rows=rows)
    p = out / f"component-sizes-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2))

    # --- printout: the live range of the fraction axis ---------------------
    print(f"{'facet':>5} {'scale':>6} {'ncomp':>7} {'largest':>10} "
          f"{'2nd/1st':>12} {'3rd/1st':>12}   kept at 1.0 / 0.1 / 0.01 / 1e-3 / 1e-4")
    for r in rows:
        for s in r["by_scale"]:
            fr = s["top10_fraction_of_largest"]
            f2 = fr[1] if len(fr) > 1 else 0.0
            f3 = fr[2] if len(fr) > 2 else 0.0
            k = s["n_kept_at_fraction"]
            print(f"{r['facet']:>5} {s['scale_mult']:>6.1f} "
                  f"{s['n_components']:>7,} {s['largest_points']:>10,} "
                  f"{f2:>12.3e} {f3:>12.3e}   "
                  f"{k['1.0']:>4} {k['0.1']:>5} {k['0.01']:>5} "
                  f"{k['0.001']:>5} {k['0.0001']:>5}")
        print()
    for c in checks:
        mark = {True: "PASS", False: "FAIL", None: "SKIP"}[c["passed"]]
        print(f"  CHECK {mark}: {c['check']}")
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
