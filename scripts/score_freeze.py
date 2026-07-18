# Score a frozen pre-registration against field ground truth (Phase 1).
#
#   python scripts/score_freeze.py reports/big_house/preregistered-2026-07-15.json \
#       reports/big_house/ground-truth-2026-07-15.json
#
# Protocol (decision 2026-07-14): the freeze was committed BEFORE any of
# these numbers entered a computation, this script only READS both inputs,
# and the comparison lands in a NEW dated file next to the freeze. Nothing
# here feeds back into the pipeline.
#
# What is scored, and what honestly cannot be:
#   PITCH  : direct validation. Per facet, pipeline pitch vs the mean of
#            three inclinometer readings. Truth uncertainty = the spread of
#            the three readings; pipeline floor = the frozen leveling floor.
#   SCALE  : the tape on the frozen primary span sets the multiplier; the
#            frozen fallback span's tape reading is an INDEPENDENT check of
#            that multiplier. Linear disagreement there bounds the scale
#            error, and area error is ~2x linear (area goes as scale^2).
#   AREA   : converted, NOT validated. No measured area exists for this
#            property (recorded in the ground-truth file), so the strongest
#            honest claim is "scale confirmed by an independent length".
import argparse
import datetime
import json
from pathlib import Path

IN_PER_M = 39.3701          # the cloud is georeferenced in meters, so
                            # in/cu vs this ratio measures GPS scale error
PITCH_TARGET_DEG = 3.0      # hypothesis band: 2-3 deg; scored at the outer
PITCH_TIGHT_DEG = 2.0       # bound, reported against the inner one too
AREA_TARGET = 0.05          # hypothesis: ~5% area
# 5% on area is (1+e)^2 - 1 = 0.05 on the linear scale, so the linear
# budget the cross-check must meet is sqrt(1.05) - 1:
LINEAR_BUDGET = 1.05 ** 0.5 - 1.0

# Dormer contamination flags, from the freeze context (2026-07-15): which
# per-facet numbers deserve extra suspicion. 4 and 5 near-clean, 2 heaviest.
DORMER_FLAG = {0: "suspect", 1: "suspect", 2: "suspect (heaviest)",
               3: "suspect", 4: "near-clean", 5: "near-clean",
               6: "suspect", 7: "suspect"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("freeze")
    ap.add_argument("truth")
    ap.add_argument("--baseline", default=None,
                    help="a previously scored comparison JSON to embed as "
                         "context: its total, the delta, and whether its "
                         "widened uncertainty interval would have contained "
                         "THIS run's total (the case for diagnosing instead "
                         "of widening, stated with numbers)")
    args = ap.parse_args()
    freeze_path, truth_path = Path(args.freeze), Path(args.truth)
    fz = json.loads(freeze_path.read_text())
    gt = json.loads(truth_path.read_text())

    # --- Scale: multiplier from the frozen primary span and its tape ------
    primary = fz["scale_candidate_primary"]
    assert primary["cand_id"] == gt["scale_primary"]["cand_id"], \
        "tape and freeze disagree about which span is primary"
    in_per_cu = gt["scale_primary"]["tape_in"] / primary["span"]
    ft_per_cu = in_per_cu / 12.0
    # The freeze's bias field is reported VERBATIM, not converted into an
    # erosion claim: its meaning depends on the freeze (run 1: one-sided
    # erosion bound; run 2: radius-probe end sensitivity whose
    # decomposition lives in the freeze context). The empirical bound on
    # scale error is the cross-check below, always.
    bias_cu = primary["bias"]

    # --- Independent cross-check on the frozen fallback span --------------
    fb = fz["scale_candidate_fallback"]
    assert fb["cand_id"] == gt["scale_crosscheck"]["cand_id"], \
        "tape and freeze disagree about which span is the cross-check"
    pred_in = fb["span"] * in_per_cu
    tape_in = gt["scale_crosscheck"]["tape_in"]
    tape_alt = gt["scale_crosscheck"]["tape_in_with_gutter"]
    dis = pred_in / tape_in - 1.0          # signed: negative = predicted short
    dis_alt = pred_in / tape_alt - 1.0
    crosscheck_pass = abs(dis) <= LINEAR_BUDGET

    # GPS plausibility: a georeferenced cloud SHOULD be ~1 m per cloud unit,
    # so in_per_cu vs 39.37 measures the GPS-derived scale error directly.
    gps_err = in_per_cu / IN_PER_M - 1.0

    # A labeled ALTERNATIVE scaling from the fallback tape: reported for
    # contrast because two independent consistency checks (below) both point
    # at the primary as the outlier. Adopting it would be a documented
    # deviation from the frozen protocol and is Emmett's call, not this
    # script's: every headline number uses the frozen primary.
    alt_in_per_cu = tape_in / fb["span"]
    alt_gps_err = alt_in_per_cu / IN_PER_M - 1.0

    # --- Areas: converted with the frozen-primary multiplier --------------
    ft2_per_cu2 = ft_per_cu ** 2
    facet_areas = [{"facet": f["facet"],
                    "area_cu2": f["area_cu2"],
                    "area_ft2": round(f["area_cu2"] * ft2_per_cu2, 1),
                    "dormer": DORMER_FLAG[f["facet"]]}
                   for f in fz["facets"]]
    total_ft2 = round(fz["total_area_cu2"] * ft2_per_cu2, 1)
    alt_total_ft2 = round(fz["total_area_cu2"] * (alt_in_per_cu / 12) ** 2, 1)

    # --- Pitch: direct per-facet validation -------------------------------
    comp = set(gt["interpretation"]["complement_facets"])
    floor = 0.20  # frozen leveling floor, deg (decision 2026-07-13)
    pitch_rows = []
    for f in fz["facets"]:
        k = f["facet"]
        raw = gt["inclinometer_deg"][str(k)]
        used = [90 - r for r in raw] if k in comp else list(raw)
        mean = sum(used) / len(used)
        spread = max(used) - min(used)
        err = f["pitch_deg"] - mean
        pitch_rows.append({
            "facet": k, "pipeline_deg": f["pitch_deg"],
            "truth_raw_deg": raw,
            "truth_used_deg": used,
            "converted_90_minus": k in comp,
            "truth_mean_deg": round(mean, 2),
            "truth_spread_deg": spread,
            "error_deg": round(err, 2),
            "within_3deg": abs(err) <= PITCH_TARGET_DEG,
            "within_2deg": abs(err) <= PITCH_TIGHT_DEG,
            "dormer": DORMER_FLAG[k]})
    errs = [r["error_deg"] for r in pitch_rows]
    pitch_bias = sum(errs) / len(errs)
    pitch_pass = all(r["within_3deg"] for r in pitch_rows)

    report = {
        "protocol": "comparison in a NEW file; the freeze and the "
                    "ground-truth record are read-only inputs",
        "date": datetime.date.today().isoformat(),
        "dataset": fz["dataset"],
        "inputs": {"freeze": freeze_path.name, "truth": truth_path.name},
        "scale": {
            "primary_cand_id": primary["cand_id"],
            "primary_span_cu": primary["span"],
            "primary_tape_in": gt["scale_primary"]["tape_in"],
            "in_per_cu": round(in_per_cu, 4),
            "ft_per_cu": round(ft_per_cu, 5),
            "recorded_end_sensitivity_cu": bias_cu,
            "end_sensitivity_note": "verbatim from the freeze; its "
                                    "interpretation is defined by that "
                                    "freeze's context field",
            "gps_scale_error_pct": round(100 * gps_err, 2),
        },
        "scale_crosscheck": {
            "fallback_cand_id": fb["cand_id"],
            "fallback_span_cu": fb["span"],
            "predicted_in": round(pred_in, 1),
            "tape_in": tape_in,
            "disagreement_pct": round(100 * dis, 2),
            "tape_in_with_gutter": tape_alt,
            "disagreement_pct_with_gutter": round(100 * dis_alt, 2),
            "linear_budget_pct": round(100 * LINEAR_BUDGET, 2),
            "pass": crosscheck_pass,
            "implied_area_uncertainty_pct": round(100 * (
                (1 + abs(dis)) ** 2 - 1), 1),
        },
        "alternative_scaling_NOT_adopted": {
            "note": "scale from the fallback tape instead of the frozen "
                    "primary; shown because it reconciles with GPS while "
                    "the primary does not; adopting it is a documented "
                    "deviation decision for Emmett, not made here",
            "in_per_cu": round(alt_in_per_cu, 4),
            "gps_scale_error_pct": round(100 * alt_gps_err, 2),
            "total_area_ft2": alt_total_ft2,
        },
        "areas": facet_areas,
        "total_area_ft2": total_ft2,
        "total_area_caveat": (
            f"the total inherits the dormer contamination, not just the "
            f"facets: {sum(1 for v in DORMER_FLAG.values() if 'suspect' in v)}"
            f" of {len(DORMER_FLAG)} facets are dormer-suspect, ~8 dormers "
            f"are unmodeled with their points absorbed into host facets, and "
            f"the resulting bias on the total is unquantified and not "
            f"correctable by a flat allowance (decision 2026-07-15)"),
        "area_claim": "scale confirmed by an independent length (weaker "
                      "claim); NO measured area exists for this property, "
                      "so area itself is NOT validated against ground truth",
        "pitch": pitch_rows,
        "pitch_summary": {
            "mean_bias_deg": round(pitch_bias, 2),
            "max_abs_error_deg": max(abs(e) for e in errs),
            "pipeline_floor_deg": floor,
            "pass_at_3deg": pitch_pass,
            "pass_at_2deg": all(r["within_2deg"] for r in pitch_rows),
        },
    }

    if args.baseline:
        base = json.loads(Path(args.baseline).read_text())
        b_total = base["total_area_ft2"]
        b_unc = base["scale_crosscheck"]["implied_area_uncertainty_pct"]
        delta = 100.0 * (total_ft2 / b_total - 1.0)
        contained = abs(delta) <= b_unc
        report["baseline_context"] = {
            "file": Path(args.baseline).name,
            "total_area_ft2": b_total,
            "this_run_vs_baseline_pct": round(delta, 1),
            "baseline_implied_area_uncertainty_pct": b_unc,
            "baseline_interval_contains_this_total": contained,
            "note": ("the baseline's widened uncertainty interval "
                     + ("would have contained" if contained else
                        "would NOT have contained")
                     + " this run's total: widening instead of diagnosing "
                       "would have "
                     + ("been sufficient" if contained else
                        "quoted an interval that misses the corrected "
                        "value"))}

    frozen_date = freeze_path.stem.replace("preregistered-", "")
    out = (freeze_path.parent
           / f"comparison-{frozen_date}-scored-{report['date']}.json")
    out.write_text(json.dumps(report, indent=2))

    # --- Human-readable summary -------------------------------------------
    print(f"scale: {in_per_cu:.3f} in/cu from {primary['cand_id']} "
          f"({gt['scale_primary']['tape_in']:.0f} in / "
          f"{primary['span']:.3f} cu); GPS scale error "
          f"{100 * gps_err:+.2f}%")
    print(f"cross-check {fb['cand_id']}: predicted {pred_in:.1f} in, "
          f"taped {tape_in:.0f} in -> {100 * dis:+.2f}% "
          f"(budget +/-{100 * LINEAR_BUDGET:.2f}%) "
          f"{'PASS' if crosscheck_pass else 'FAIL'}")
    print(f"  with gutter ({tape_alt:.0f} in): {100 * dis_alt:+.2f}%")
    print(f"total area {total_ft2:,.1f} ft2 (alternative scaling would "
          f"give {alt_total_ft2:,.1f} ft2)")
    print(f"total caveat: {report['total_area_caveat']}")
    if args.baseline:
        bc = report["baseline_context"]
        print(f"baseline {bc['file']}: {bc['total_area_ft2']:,.1f} ft2, "
              f"this run {bc['this_run_vs_baseline_pct']:+.1f}%; "
              f"{bc['note']}")
    print()
    print("facet  pipeline  truth(mean)  err    spread  dormer")
    for r in pitch_rows:
        conv = " (90-x)" if r["converted_90_minus"] else ""
        print(f"  {r['facet']}    {r['pipeline_deg']:7.2f}  "
              f"{r['truth_mean_deg']:8.2f}{conv:7s} "
              f"{r['error_deg']:+5.2f}  {r['truth_spread_deg']:4.1f}    "
              f"{r['dormer']}")
    print(f"\npitch: mean bias {pitch_bias:+.2f} deg, max |err| "
          f"{max(abs(e) for e in errs):.2f} deg, "
          f"pass at 3 deg: {pitch_pass}, "
          f"pass at 2 deg: {report['pitch_summary']['pass_at_2deg']}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
