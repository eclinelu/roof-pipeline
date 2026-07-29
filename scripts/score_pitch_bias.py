# SCORE THE PITCH-BIAS PRE-REGISTRATION (5b and 10).
#
#   .venv/Scripts/python.exe scripts/score_pitch_bias.py C:/odm/datasets/big_house
#
# Writes reports/big_house/pitch-bias-score-<date>.json    (standing rule R2)
#
# READ ONLY. Arithmetic over committed artifacts. Nothing adopted, no
# correction applied to any pitch on any facet at any site.
#
# Pre-registration: decisions/2026-07-29-preregistration-pitch-bias-mechanism.md
# committed and pushed at 7a64185 BEFORE 5b was run.
#
# ---------------------------------------------------------------------------
# THE TWO SHAPES, AS PRE-REGISTERED
#
#   SHINGLE STEP (or any procedural bias)  CONSTANT offset in degrees.
#   VERTICAL SCALE STRETCH                 offset grows with pitch, ~ sin.cos,
#                                          peaking at 45 deg and zero at flat.
#
#   shallow/steep offset ratio:  1.00 under constant, 0.70 under stretch
#
#   SCORING BANDS, FIXED BEFORE THE NUMBER WAS COMPUTED:
#     0.60 to 0.82  -> consistent with SCALE STRETCH
#     0.90 to 1.10  -> consistent with CONSTANT OFFSET
#     anything else -> NEITHER SHAPE FITS, reported as such
#
# INDEPENDENT ASSERTIONS:
#   - the recomputed per-facet offsets reproduce the committed error_deg
#   - the two clusters are actually separated in pitch, or the ratio is
#     meaningless. ANTI-NULL: if every facet had the same pitch the ratio would
#     be 1.00 by construction and would prove nothing.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SHALLOW_MAX = 26.0        # the gap between the two clusters is 21 to 31 deg
STRETCH_BAND = (0.60, 0.82)
CONSTANT_BAND = (0.90, 1.10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    frozen = json.loads(
        (out / "comparison-2026-07-18-scored-2026-07-18.json").read_text())
    fp = frozen["pitch"]
    spec = json.loads((out / f"facet-residuals-{args.stamp}.json").read_text())

    rows = []
    for r in fp:
        off = r["pipeline_deg"] - r["truth_mean_deg"]
        rows.append(dict(facet=r["facet"], truth_deg=r["truth_mean_deg"],
                         pipeline_deg=r["pipeline_deg"],
                         offset_deg=round(off, 4),
                         committed_error_deg=r["error_deg"],
                         cluster=("shallow" if r["truth_mean_deg"] < SHALLOW_MAX
                                  else "steep")))
    checks = [dict(
        check="recomputed offsets reproduce the committed error_deg",
        passed=all(abs(abs(x["offset_deg"]) - x["committed_error_deg"]) < 0.011
                   for x in rows))]

    sh = [x for x in rows if x["cluster"] == "shallow"]
    st = [x for x in rows if x["cluster"] == "steep"]
    sh_p = float(np.mean([x["truth_deg"] for x in sh]))
    st_p = float(np.mean([x["truth_deg"] for x in st]))
    checks.append(dict(
        check="ANTI-NULL: the two clusters are genuinely separated in pitch. "
              "If they were not, the ratio would be 1.00 by construction and "
              "would prove nothing.",
        passed=bool(st_p - sh_p > 8.0),
        detail=dict(shallow_mean_pitch=round(sh_p, 2),
                    steep_mean_pitch=round(st_p, 2),
                    separation_deg=round(st_p - sh_p, 2))))

    sh_o = float(np.mean([x["offset_deg"] for x in sh]))
    st_o = float(np.mean([x["offset_deg"] for x in st]))
    ratio = sh_o / st_o
    # what each hypothesis predicts for THESE two cluster pitches
    pred_stretch = float((np.sin(np.radians(sh_p)) * np.cos(np.radians(sh_p)))
                         / (np.sin(np.radians(st_p)) * np.cos(np.radians(st_p))))

    if STRETCH_BAND[0] <= ratio <= STRETCH_BAND[1]:
        verdict = "CONSISTENT WITH SCALE STRETCH"
    elif CONSTANT_BAND[0] <= ratio <= CONSTANT_BAND[1]:
        verdict = "CONSISTENT WITH CONSTANT OFFSET"
    else:
        verdict = "NEITHER SHAPE FITS"

    # scatter after removing a constant, reported as a MEASUREMENT ONLY
    allo = np.array([x["offset_deg"] for x in rows])
    resid = allo - allo.mean()

    # --- prediction 10-3, amplitude -------------------------------------
    amps = [s["approx_amplitude_in"] for s in spec["spectrum"]["rows"]]
    excess = [s["excess_db"] for s in spec["spectrum"]["rows"]]
    angles = [s["wavevector_angle_from_slope_deg"]
              for s in spec["spectrum"]["rows"]]

    doc = dict(
        task="score the pitch-bias pre-registration: 5b shape discriminator "
             "and 10 stripe predictions",
        dataset=name, date=args.stamp,
        status="SCORING ONLY. Nothing adopted. NO CORRECTION APPLIED to any "
               "pitch, on any facet, at any site.",
        preregistration="decisions/2026-07-29-preregistration-pitch-bias-mechanism.md "
                        "(pushed at 7a64185 before 5b ran)",
        scorecard={
            "10-1 stripes visible in the residual images":
                "FAILED. No stripes at 48 x 48 in windows with 0.25 in cells, "
                "a resolution that would show a 5 in course. The dominant "
                "structure is large-scale (10-40 in) and often diagonal.",
            "10-2 spectral peak in the 4-7 in band":
                "AMBIGUOUS, and weaker than it first looked. See below.",
            "10-3 stripe amplitude 0.12 to 0.24 in":
                "FAILED. Measured 0.014 to 0.034 in, 5 to 17 times smaller "
                "than a 3-6 mm butt would produce.",
            "5b shape discriminator": verdict},
        five_b=dict(
            shallow_cluster=dict(facets=[x["facet"] for x in sh],
                                 mean_truth_pitch_deg=round(sh_p, 3),
                                 mean_offset_deg=round(sh_o, 4),
                                 offsets=[x["offset_deg"] for x in sh]),
            steep_cluster=dict(facets=[x["facet"] for x in st],
                               mean_truth_pitch_deg=round(st_p, 3),
                               mean_offset_deg=round(st_o, 4),
                               offsets=[x["offset_deg"] for x in st]),
            observed_ratio=round(ratio, 4),
            predicted_ratio_constant=1.0,
            predicted_ratio_stretch=round(pred_stretch, 4),
            scoring_bands=dict(stretch=list(STRETCH_BAND),
                               constant=list(CONSTANT_BAND)),
            verdict=verdict,
            scatter_after_removing_a_constant=dict(
                note="MEASUREMENT ONLY. No correction is adopted.",
                mean_offset_deg=round(float(allo.mean()), 4),
                residual_sd_deg=round(float(resid.std(ddof=1)), 4),
                residual_range_deg=[round(float(resid.min()), 4),
                                    round(float(resid.max()), 4)],
                per_facet={str(x["facet"]): round(float(v), 4)
                           for x, v in zip(rows, resid)}),
            power_caveat="the within-cluster spread is LARGE relative to the "
                         "difference the test is trying to detect: the steep "
                         "cluster's own offsets run 1.067 to 2.087 deg, a "
                         "spread of 1.02 deg, while the two hypotheses differ "
                         "by only 0.30 in the ratio. With four facets per "
                         "cluster this test has little power, and that is a "
                         "property of the data, not of the scoring."),
        ten=dict(approx_amplitudes_in=amps,
                 excess_over_trend_db=excess,
                 wavevector_angles_from_slope_deg=angles,
                 amplitude_prediction_in=[0.12, 0.24],
                 note="the naive peak/background ratio first computed here was "
                      "INVALID against a red spectrum and reported values up "
                      "to 318 where the detrended excess is 9 dB. The invalid "
                      "figure is retained in the residual artifact as "
                      "naive_ratio_INVALID so the correction is auditable."),
        rows=rows, cross_checks=checks)
    p = out / f"pitch-bias-score-{args.stamp}.json"
    p.write_text(json.dumps(doc, indent=2, default=float))

    print(f"\n  {'f':>2} {'truth':>7} {'pipeline':>9} {'offset':>8}  cluster")
    for x in rows:
        print(f"  {x['facet']:>2} {x['truth_deg']:>7.2f} "
              f"{x['pipeline_deg']:>9.3f} {x['offset_deg']:>+8.3f}  "
              f"{x['cluster']}")
    print(f"\n  shallow mean pitch {sh_p:.2f} deg -> mean offset {sh_o:+.4f} deg")
    print(f"  steep   mean pitch {st_p:.2f} deg -> mean offset {st_o:+.4f} deg")
    print(f"\n  OBSERVED RATIO shallow/steep = {ratio:.4f}")
    print(f"    predicted 1.00 under CONSTANT OFFSET  (band "
          f"{CONSTANT_BAND[0]}-{CONSTANT_BAND[1]})")
    print(f"    predicted {pred_stretch:.2f} under SCALE STRETCH  (band "
          f"{STRETCH_BAND[0]}-{STRETCH_BAND[1]})")
    print(f"    VERDICT: {verdict}")
    print(f"\n  scatter after removing a constant: sd "
          f"{resid.std(ddof=1):.4f} deg, range "
          f"{resid.min():+.3f} to {resid.max():+.3f} deg  (MEASUREMENT ONLY)")
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check'][:78]}")
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
