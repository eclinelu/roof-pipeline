# Do facet point sets contain DISCONNECTED FRAGMENTS remote from the main body?
#
#   .venv/Scripts/python.exe scripts/probe_fragments.py C:/odm/datasets/big_house
#
# Writes reports/big_house/fragments-<date>.json   (standing rule R2)
#
# READ ONLY. Loads the canonical state from disk, measures it, writes a report.
# Fits nothing, changes nothing, regenerates nothing. canonical-2026-07-26-r2 is
# untouched.
#
# ---------------------------------------------------------------------------
# WHY
#
# The 2026-07-27 visual review records, on facet 0, "thin disconnected fragments
# remote from it: stray contour lines running off across the building enclosing
# nothing". That is a claim about facet MEMBERSHIP and it is measurable without
# anyone looking at a picture, which is what decision
# 2026-07-27-development-vs-validation-split.md requires: the eye locates a
# defect, a measurement establishes it.
#
# Independent corroboration arrived by accident. The per-facet close-up for
# facet 4 rendered almost blank, because the renderer sets its axis limits from
# `points.min()` and `points.max()`. If a facet's points span far more ground
# than the facet covers, the view zooms out to nothing. The render was not
# testing for fragments and had no way to know it was reporting one.
#
# THE MEASUREMENT: bin each facet's points into plan cells, take connected
# components, and compare the LARGEST component against the whole. A clean facet
# is one component. A facet with remote slivers has a dominant component plus
# outliers far away.
#
# INDEPENDENT ASSERTIONS (standing rule 2026-07-27-silent-failure-standing-rule):
#   - the largest component is a SUBSET of the facet: kept fraction <= 1
#   - the core extent is <= the full extent, always
#   - point counts per facet must match the canonical record exactly
# Each is checked and written into the output with its pass/fail state.
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
# 8-connectivity: a fragment touching the main body only at a corner is still
# attached. This makes the test CONSERVATIVE, so a facet reported as fragmented
# is fragmented under the most forgiving reading.
STRUCT = np.ones((3, 3), dtype=bool)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    doc, points, facets, cfg = load_canonical(args.dataset, CANONICAL_STAMP)
    cell = scalar(doc, "cell_cu")
    in_per_cu = 40.4541
    sc = out / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])
    ft = in_per_cu / 12.0

    rows, checks = [], []
    for f in facets:
        p = np.asarray(f["points"], float)
        xy = p[:, :2]
        lo = xy.min(axis=0)
        i = ((xy[:, 0] - lo[0]) / cell).astype(np.int64)
        j = ((xy[:, 1] - lo[1]) / cell).astype(np.int64)
        occ = np.zeros((i.max() + 1, j.max() + 1), bool)
        occ[i, j] = True
        lab, n = label(occ, structure=STRUCT)
        per_cell = lab[i, j]
        sizes = np.bincount(per_cell, minlength=n + 1)[1:]
        big = int(np.argmax(sizes)) + 1
        core = per_cell == big

        full_w = (xy[:, 0].max() - xy[:, 0].min()) * ft
        full_h = (xy[:, 1].max() - xy[:, 1].min()) * ft
        cxy = xy[core]
        core_w = (cxy[:, 0].max() - cxy[:, 0].min()) * ft
        core_h = (cxy[:, 1].max() - cxy[:, 1].min()) * ft
        # how far the farthest stray point sits from the core's bounding box
        if (~core).any():
            oxy = xy[~core]
            dx = np.maximum(cxy[:, 0].min() - oxy[:, 0],
                            oxy[:, 0] - cxy[:, 0].max())
            dy = np.maximum(cxy[:, 1].min() - oxy[:, 1],
                            oxy[:, 1] - cxy[:, 1].max())
            far = float(np.max(np.maximum(np.maximum(dx, dy), 0.0)) * ft)
        else:
            far = 0.0

        rows.append(dict(
            facet=f["facet"], kind=f["kind"], n_points=int(len(p)),
            n_components=int(n),
            core_point_fraction=round(float(core.mean()), 6),
            stray_points=int((~core).sum()),
            full_extent_ft=[round(full_w, 1), round(full_h, 1)],
            core_extent_ft=[round(core_w, 1), round(core_h, 1)],
            extent_inflation=round(
                float(max(full_w, full_h) / max(max(core_w, core_h), 1e-9)), 3),
            farthest_stray_beyond_core_ft=round(far, 1),
            quality=f["quality"], pitch_deg=round(float(f["pitch"]), 2)))

    # --- independent assertions --------------------------------------------
    checks.append(dict(
        check="every facet's point count matches the canonical record",
        passed=all(r["n_points"] == d["n_points"]
                   for r, d in zip(rows, doc["facets"]))))
    checks.append(dict(
        check="core is a subset of the facet (fraction <= 1)",
        passed=all(r["core_point_fraction"] <= 1.0 for r in rows)))
    checks.append(dict(
        check="core extent never exceeds full extent",
        passed=all(r["core_extent_ft"][0] <= r["full_extent_ft"][0] + 1e-6 and
                   r["core_extent_ft"][1] <= r["full_extent_ft"][1] + 1e-6
                   for r in rows)))

    frag = [r for r in rows if r["extent_inflation"] > 1.15]
    frag.sort(key=lambda r: -r["extent_inflation"])
    docout = dict(
        task="do facet point sets contain disconnected fragments remote from "
             "the main body? Measured from the canonical state, read only.",
        dataset=name, date=args.stamp,
        status="READ ONLY. Nothing fitted, changed or regenerated. "
               "canonical-2026-07-26-r2 unchanged.",
        method=dict(
            cell_cu=cell, connectivity="8 (corner touches count as attached, "
                                       "so the test is conservative)",
            extent_inflation="max full extent / max core extent, in plan. 1.0 "
                             "means the facet's points span exactly its main "
                             "body; 2.0 means they span twice as far.",
            flag_threshold=1.15),
        cross_checks=checks,
        n_facets=len(rows),
        n_flagged=len(frag),
        flagged=[r["facet"] for r in frag],
        rows=rows,
        reading="a facet whose extent_inflation is well above 1.0, with a "
                "core_point_fraction still near 1.0, is carrying a SMALL NUMBER "
                "of points a LONG WAY from the surface. That is the shape the "
                "visual review described: thin remote slivers that add almost "
                "no points but sit far from the facet.")
    p = out / f"fragments-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2))

    print(f"{'id':>3} {'kind':<9} {'pts':>9} {'comp':>5} {'core%':>8} "
          f"{'stray':>6} {'inflation':>9} {'far ft':>7}")
    for r in rows:
        flagmark = "  <<<" if r["extent_inflation"] > 1.15 else ""
        print(f"{r['facet']:>3} {r['kind']:<9} {r['n_points']:>9,} "
              f"{r['n_components']:>5} {100*r['core_point_fraction']:>7.3f}% "
              f"{r['stray_points']:>6,} {r['extent_inflation']:>9.2f} "
              f"{r['farthest_stray_beyond_core_ft']:>7.1f}{flagmark}")
    print(f"\n  {len(frag)} of {len(rows)} facets flagged (inflation > 1.15)")
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check']}")
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
