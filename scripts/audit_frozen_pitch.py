# DID M1a CONTAMINATION ACTUALLY MOVE THE FROZEN PITCH VALIDATION?
#
#   .venv/Scripts/python.exe scripts/audit_frozen_pitch.py C:/odm/datasets/big_house
#
# Writes reports/big_house/frozen-pitch-audit-<date>.json   (standing rule R2)
#
# SIDE ARTIFACT ONLY. Reads two committed artifacts and does arithmetic. Fits
# nothing, re-runs nothing, adopts nothing. The 2026-07-18 freeze is not
# restated, reopened or corrected: it is what it is, and this asks only what it
# WOULD have been.
#
# ---------------------------------------------------------------------------
# THE QUESTION AND WHY IT DECIDES SCOPE, NOT JUST ACCURACY
#
# The 2026-07-18 pitch validation (mean bias 1.83 deg, max |error| 2.19 deg,
# PASS at 3 deg, FAIL at 2 deg) ran through the same `discover_facets` path the
# M1a sweep just showed carries disconnected fragments on all 8 main facets. So
# every frozen pitch number was computed on contaminated membership. The
# pre-registration flagged this as something to CHECK rather than assume:
#
#   "Whatever pitch delta M1a removal produces is also a measure of how much
#    the frozen pitch numbers were computed on contaminated membership."
#
# If removing the contamination moves pitch by a negligible amount, then M1a
# does not matter for the primary deliverable, and the case for fixing it
# before freezing bungalow and cove_house is weak. That is a SCOPE decision
# about where the remaining time goes, not an accuracy claim.
#
# WHY THE PITCH SIDE IS UNAFFECTED BY THE RASTER PHASE FINDING
# (decisions/2026-07-28-raster-phase-is-an-unswept-parameter.md and the
# production phase audit): pitch comes from a fitted plane normal via
# tilt_degrees. It never passes through a plan raster. The phase defect reaches
# coverage, the footprint and blob selection; it does not reach pitch.
#
# ---------------------------------------------------------------------------
# THE ARITHMETIC, STATED BECAUSE IT IS THE WHOLE METHOD
#
#   frozen_error = |pipeline_pitch - truth_mean|          as scored 2026-07-18
#   new_pitch    = pipeline_pitch + delta_from_the_sweep  per facet, per setting
#   new_error    = |new_pitch - truth_mean|
#
# The delta is taken from the M1a sweep's per-facet pitch_delta_deg, which is
# measured against a baseline that assertion A0 proved reproduces
# canonical-2026-07-26-r2 exactly. Two settings are reported:
#
#   LOOSEST     scale 5.0, fraction 0.0001. Removes 3,134 points in total, the
#               least destructive point in the grid.
#   CANONICAL   scale 2.5, fraction 1.0. The canonical coverage cell and the
#               pre-registration's own "main body" definition.
#
# Both, not one, because a single setting cannot distinguish "the fix does
# nothing" from "this particular setting does nothing".
#
# INDEPENDENT ASSERTIONS (standing rule 2026-07-27-silent-failure-standing-rule):
#   - the frozen errors recomputed here from pipeline_deg and truth_mean_deg
#     reproduce the error_deg the 2026-07-18 file recorded. If the arithmetic
#     cannot reproduce the committed scoring, it cannot be trusted to project
#     it forward.
#   - the recomputed max |error| and the pass/fail flags reproduce
#     pitch_summary exactly.
#   - the facet count in the sweep matches the facet count in the freeze.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SETTINGS = [dict(name="LOOSEST", scale=5.0, frac=0.0001),
            dict(name="CANONICAL", scale=2.5, frac=1.0)]
PASS_3 = 3.0
PASS_2 = 2.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    frozen = json.loads(
        (out / "comparison-2026-07-18-scored-2026-07-18.json").read_text())
    sweep = json.loads((out / f"m1a-sweep-{args.stamp}.json").read_text())
    fp = frozen["pitch"]
    fsum = frozen["pitch_summary"]

    # ---- assertion: can we reproduce the committed scoring? ---------------
    recomputed = [round(abs(r["pipeline_deg"] - r["truth_mean_deg"]), 2)
                  for r in fp]
    stated = [r["error_deg"] for r in fp]
    repro = all(abs(a - b) < 0.011 for a, b in zip(recomputed, stated))
    max_re = round(max(recomputed), 2)
    checks = [
        dict(check="frozen per-facet errors recomputed from pipeline_deg and "
                   "truth_mean_deg reproduce the committed error_deg",
             passed=bool(repro),
             detail=dict(recomputed=recomputed, committed=stated)),
        dict(check="recomputed max |error| and the pass flags reproduce "
                   "pitch_summary",
             passed=bool(abs(max_re - fsum["max_abs_error_deg"]) < 0.011
                         and (max_re <= PASS_3) == fsum["pass_at_3deg"]
                         and (max_re <= PASS_2) == fsum["pass_at_2deg"]),
             detail=dict(recomputed_max=max_re,
                         committed_max=fsum["max_abs_error_deg"],
                         committed_pass_3=fsum["pass_at_3deg"],
                         committed_pass_2=fsum["pass_at_2deg"])),
    ]

    results = []
    for s in SETTINGS:
        row = next(r for r in sweep["rows"]
                   if r["scale_mult"] == s["scale"]
                   and r["min_component_frac"] == s["frac"])
        deltas = {p["facet"]: p["pitch_delta_deg"] for p in row["per_facet"]}
        checks.append(dict(
            check=f"{s['name']}: the sweep reports a delta for every frozen "
                  f"facet",
            passed=bool(all(r["facet"] in deltas for r in fp)),
            detail=dict(frozen_facets=[r["facet"] for r in fp],
                        sweep_facets=sorted(deltas))))
        per = []
        for r in fp:
            d = deltas.get(r["facet"], 0.0)
            new_pitch = r["pipeline_deg"] + d
            new_err = abs(new_pitch - r["truth_mean_deg"])
            per.append(dict(
                facet=r["facet"],
                truth_mean_deg=r["truth_mean_deg"],
                truth_spread_deg=r["truth_spread_deg"],
                frozen_pitch_deg=r["pipeline_deg"],
                pitch_delta_deg=d,
                new_pitch_deg=round(new_pitch, 4),
                frozen_error_deg=r["error_deg"],
                new_error_deg=round(new_err, 4),
                error_change_deg=round(new_err - r["error_deg"], 4),
                frozen_within_3=r["within_3deg"],
                new_within_3=bool(new_err <= PASS_3),
                frozen_within_2=r["within_2deg"],
                new_within_2=bool(new_err <= PASS_2),
                verdict_flipped_at_3=bool(r["within_3deg"] != (new_err <= PASS_3)),
                verdict_flipped_at_2=bool(r["within_2deg"] != (new_err <= PASS_2))))
        new_max = max(p["new_error_deg"] for p in per)
        results.append(dict(
            setting=s["name"], scale_mult=s["scale"],
            min_component_frac=s["frac"],
            total_points_removed=row["total_points_removed"],
            max_abs_pitch_delta_deg=row["max_abs_pitch_delta_deg"],
            frozen_max_error_deg=fsum["max_abs_error_deg"],
            new_max_error_deg=round(new_max, 4),
            max_error_change_deg=round(new_max - fsum["max_abs_error_deg"], 4),
            frozen_pass_at_3=fsum["pass_at_3deg"],
            new_pass_at_3=bool(new_max <= PASS_3),
            frozen_pass_at_2=fsum["pass_at_2deg"],
            new_pass_at_2=bool(new_max <= PASS_2),
            any_facet_verdict_flipped_at_3=any(p["verdict_flipped_at_3"] for p in per),
            any_facet_verdict_flipped_at_2=any(p["verdict_flipped_at_2"] for p in per),
            largest_error_change_deg=max(abs(p["error_change_deg"]) for p in per),
            per_facet=per))

    # The headroom question: how far would pitch have to move to change the
    # verdict at all? Stated so the deltas can be read against something.
    headroom_3 = round(PASS_3 - fsum["max_abs_error_deg"], 4)
    worst_2 = min(abs(PASS_2 - r["error_deg"]) for r in fp)

    docout = dict(
        task="did M1a contamination actually move the frozen 2026-07-18 pitch "
             "validation?",
        dataset=name, date=args.stamp,
        status="SIDE ARTIFACT ONLY. Arithmetic over two committed artifacts. "
               "The 2026-07-18 freeze is NOT restated, reopened or corrected. "
               "canonical-2026-07-26-r2 unchanged; nothing adopted.",
        why="this decides SCOPE. If removing M1a moves the primary deliverable "
            "negligibly, the case for fixing it before freezing bungalow and "
            "cove_house is weak.",
        pitch_is_not_phase_affected=(
            "pitch comes from a fitted plane normal via tilt_degrees and never "
            "passes through a plan raster, so the 2026-07-28 raster-phase "
            "finding does not reach it. Coverage, the footprint and blob "
            "selection are affected; pitch is not."),
        frozen_summary=fsum,
        headroom=dict(
            margin_to_3deg_pass=headroom_3,
            reading=f"the frozen worst facet sits {headroom_3} deg inside the "
                    f"3 deg threshold, so a pitch shift would have to exceed "
                    f"that to break the PASS",
            closest_facet_to_the_2deg_line=worst_2),
        cross_checks=checks,
        settings=results)
    p = out / f"frozen-pitch-audit-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2, default=float))

    print(f"\n  frozen: max |error| {fsum['max_abs_error_deg']} deg, "
          f"PASS at 3 = {fsum['pass_at_3deg']}, PASS at 2 = "
          f"{fsum['pass_at_2deg']}")
    print(f"  headroom to the 3 deg threshold: {headroom_3} deg\n")
    for res in results:
        print(f"  {res['setting']}  (scale {res['scale_mult']}, frac "
              f"{res['min_component_frac']}, {res['total_points_removed']:,} "
              f"points removed)")
        print(f"  {'f':>2} {'truth':>7} {'frozen':>8} {'delta':>9} "
              f"{'new':>8} {'err':>7} {'newerr':>7} {'change':>8}  flip3 flip2")
        for q in res["per_facet"]:
            print(f"  {q['facet']:>2} {q['truth_mean_deg']:>7.2f} "
                  f"{q['frozen_pitch_deg']:>8.3f} {q['pitch_delta_deg']:>+9.4f} "
                  f"{q['new_pitch_deg']:>8.3f} {q['frozen_error_deg']:>7.2f} "
                  f"{q['new_error_deg']:>7.3f} {q['error_change_deg']:>+8.4f}"
                  f"   {'Y' if q['verdict_flipped_at_3'] else '.':>3}"
                  f"   {'Y' if q['verdict_flipped_at_2'] else '.':>3}")
        print(f"    max |error| {res['frozen_max_error_deg']} -> "
              f"{res['new_max_error_deg']}  (change "
              f"{res['max_error_change_deg']:+.4f})   PASS at 3: "
              f"{res['frozen_pass_at_3']} -> {res['new_pass_at_3']}   "
              f"PASS at 2: {res['frozen_pass_at_2']} -> {res['new_pass_at_2']}\n")
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check'][:82]}")
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
