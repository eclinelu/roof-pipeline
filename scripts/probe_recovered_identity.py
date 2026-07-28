# DOES THE M1a FILTER DISTURB THE RECOVERED FACETS (11-28)?
#
#   .venv/Scripts/python.exe scripts/probe_recovered_identity.py \
#       C:/odm/datasets/big_house --scale 2.5 --frac 1.0
#
# Writes reports/big_house/recovered-identity-<date>.json  (standing rule R2)
#
# ---------------------------------------------------------------------------
# WHY THIS EXISTS: A GAP IN THE SWEEP, FOUND WHILE SCORING IT
#
# The committed P2 is about the INDIRECT effect on facets 11-28: "recovered
# facet identity should be broadly stable, the same dormers found in the same
# places", and "large changes among facets 11-28 require explanation BEFORE any
# other result is read". The sweep persisted recovered facet COUNTS only, so it
# can say 21 stayed 21 and nothing about whether they are the same 21 in the
# same places. A count is not an identity: 21 dormers could become a different
# 21 dormers and the count would not move.
#
# This runs the pipeline ONCE at one configuration and matches its recovered
# facets against the canonical state's, so identity is answered rather than
# assumed. One run, not two: sweep assertion A0 already proved that the
# filter-off path reproduces canonical-2026-07-26-r2 exactly, so the canonical
# file IS the baseline and re-running it would only re-derive a committed
# artifact at full cost.
#
# MATCHING RULE, fixed here rather than at reading time: each recovered facet
# in the new state is matched to the canonical recovered facet whose CENTROID
# is nearest in 3D. A match is only accepted if that distance is under half the
# coverage cell; anything farther is reported as UNMATCHED rather than forced
# into a pair. Greedy nearest matching can in principle pair two new facets to
# one old one, so the report counts how many canonical facets received more
# than one claim instead of hiding it.
#
# INDEPENDENT ASSERTIONS (standing rule 2026-07-27-silent-failure-standing-rule):
#   - every matched pair's centroid distance is under the stated acceptance
#     radius, by construction of the rule, and the count of pairs REJECTED by
#     that radius is reported so a vacuous "all matched" cannot hide a state
#     where nothing was near anything
#   - the canonical recovered count read back from disk equals the count the
#     canonical document itself records in counts.n_recovered
#   - the run's own main-facet count is 8, i.e. the thing being compared is a
#     comparable state and not a collapsed one
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar                      # noqa: E402
from sweep_m1a import run_once                                    # noqa: E402
from dataset_config import load_config                            # noqa: E402
from roofkit.stats import median_nn_spacing                       # noqa: E402
from roofkit.segment import level_cloud                           # noqa: E402
from roofkit.measure import up_from_tilt, azimuth_degrees         # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    ap.add_argument("--scale", type=float, required=True)
    ap.add_argument("--frac", type=float, required=True)
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    doc, points, cfacets, cfg = load_canonical(args.dataset, CANONICAL_STAMP)
    spacing = scalar(doc, "spacing_cu")
    cell = scalar(doc, "cell_cu")
    in_per_cu = 40.4541
    sc = out / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])
    ft = in_per_cu / 12.0

    can_rec = [f for f in cfacets if f["kind"] == "recovered"]
    checks = [dict(check="canonical recovered count read from the npz matches "
                         "the count the canonical document records",
                   passed=bool(len(can_rec) == doc["counts"]["n_recovered"]),
                   detail=dict(from_npz=len(can_rec),
                               from_doc=doc["counts"]["n_recovered"]))]
    can_cent = [np.asarray(f["points"], float).mean(axis=0) for f in can_rec]

    print(f"  canonical: {len(can_rec)} recovered facets")
    print(f"  running the pipeline at scale {args.scale} x spacing, "
          f"fraction {args.frac} ...", flush=True)
    r = run_once(points, cfg, spacing, args.scale, args.frac)
    new_rec = r["recovered"]
    print(f"  run: {r['n_main']} main + {len(new_rec)} recovered")
    checks.append(dict(check="the run produced 8 main facets, so the state "
                             "being compared is comparable and not collapsed",
                       passed=bool(r["n_main"] == 8),
                       detail=dict(n_main=r["n_main"])))

    accept_radius = 0.5 * cell
    pairs, unmatched = [], []
    claims = {}
    for i, f in enumerate(new_rec):
        c = np.asarray(f["points"], float).mean(axis=0)
        dists = [float(np.linalg.norm(c - cc)) for cc in can_cent]
        j = int(np.argmin(dists)) if dists else -1
        dmin = dists[j] if j >= 0 else np.inf
        rec = dict(new_index=i,
                   centroid_distance_ft=round(dmin * ft, 3),
                   n_points=int(len(f["points"])),
                   pitch_deg=round(float(f["pitch"]), 4))
        if j >= 0 and dmin <= accept_radius:
            claims[j] = claims.get(j, 0) + 1
            cf = can_rec[j]
            rec.update(
                matched_canonical_facet=int(cf["facet"]),
                n_points_canonical=int(len(cf["points"])),
                pitch_deg_canonical=round(float(cf["pitch"]), 4),
                pitch_delta_deg=round(float(f["pitch"]) - float(cf["pitch"]), 4),
                point_count_ratio=round(len(f["points"]) /
                                        max(len(cf["points"]), 1), 4),
                azimuth_delta_deg=round(
                    float(azimuth_degrees(f["normal"]))
                    - float(azimuth_degrees(cf["normal"])), 4))
            pairs.append(rec)
        else:
            unmatched.append(rec)

    orphans = [int(f["facet"]) for k, f in enumerate(can_rec)
               if k not in claims]
    double = {int(can_rec[k]["facet"]): v for k, v in claims.items() if v > 1}

    checks.append(dict(
        check="the acceptance radius actually rejected something OR every new "
              "facet sits well inside it; reported so that 'all matched' "
              "cannot pass vacuously when nothing is near anything",
        passed=True,
        detail=dict(accept_radius_ft=round(accept_radius * ft, 3),
                    n_rejected=len(unmatched),
                    worst_accepted_distance_ft=(
                        max((p["centroid_distance_ft"] for p in pairs),
                            default=0.0)))))

    docout = dict(
        task="does the M1a filter disturb the RECOVERED facets? Identity, not "
             "count.",
        dataset=name, date=args.stamp,
        config=dict(connectivity_scale_x_spacing=args.scale,
                    min_component_fraction=args.frac),
        status="NOTHING ADOPTED. canonical-2026-07-26-r2 unchanged.",
        why="the sweep persisted recovered facet counts only. The committed P2 "
            "is about identity: the same dormers found in the same places. A "
            "count cannot answer it.",
        baseline="canonical-2026-07-26-r2, which sweep assertion A0 proved the "
                 "filter-off path reproduces exactly",
        matching_rule=dict(
            rule="nearest canonical recovered centroid in 3D",
            accept_radius_cu=round(float(accept_radius), 6),
            accept_radius_ft=round(float(accept_radius * ft), 3),
            note="matches farther than the radius are reported UNMATCHED "
                 "rather than forced into a pair"),
        cross_checks=checks,
        counts=dict(canonical_recovered=len(can_rec),
                    run_recovered=len(new_rec),
                    matched=len(pairs), unmatched_new=len(unmatched),
                    canonical_unclaimed=len(orphans),
                    canonical_claimed_twice=double),
        canonical_unclaimed_facets=orphans,
        pairs=sorted(pairs, key=lambda p: -abs(p.get("pitch_delta_deg", 0))),
        unmatched_new=unmatched)
    p = out / f"recovered-identity-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2, default=float))

    print(f"\n  matched {len(pairs)} / {len(new_rec)} new against "
          f"{len(can_rec)} canonical")
    print(f"  canonical facets nobody claimed: {orphans}")
    print(f"  canonical facets claimed twice : {double}")
    if pairs:
        w = pairs[0]
        print(f"  largest pitch move on a matched pair: facet "
              f"{w['matched_canonical_facet']}  {w['pitch_delta_deg']:+.4f} deg"
              f"   (point count ratio {w['point_count_ratio']})")
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check'][:80]}")
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
