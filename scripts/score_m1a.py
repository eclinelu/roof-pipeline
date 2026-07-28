# SCORE THE M1a PRE-REGISTRATION, P1 THROUGH P9.
#
#   .venv/Scripts/python.exe scripts/score_m1a.py C:/odm/datasets/big_house
#
# Writes reports/big_house/m1a-scorecard-<date>.json       (standing rule R2)
#
# READ ONLY on the sweep artifact. Computes nothing new; extracts the numbers
# each prediction named and applies a stated criterion to each.
#
# ---------------------------------------------------------------------------
# WHY A SCRIPT RATHER THAN PROSE
#
# Emmett's requirement: the scorecard comes FIRST and the reading of it comes
# second, so the raw result can be read before anyone's framing of it. A script
# enforces the order, because it cannot see the interpretation and the
# interpretation cannot edit it.
#
# HONEST DISCLOSURE ABOUT WHEN THESE CRITERIA WERE FIXED. They were written
# while the 20-point sweep was still running, with ONE grid point already seen
# (the smoke run at scale 2.5, fraction 1.0). So they are not blind. What was
# already visible from that one point: quality bar 2.9452 against a baseline
# 2.9480, facet coverage 88.39 against 88.40, max pitch delta 0.0141 deg,
# 29 facets, 151,449 points removed. Anyone auditing this should assume those
# five numbers informed the criteria below and check whether any criterion
# looks shaped to them. The criteria for P4, P6, P7 and P9 are taken verbatim
# from the pre-registration's own wording rather than invented here, which is
# the defence against exactly that.
#
# EVERY PREDICTION GETS ONE OF THREE VERDICTS AND NOTHING ELSE:
#   HELD        the pre-registered direction or bound is what happened
#   FAILED      it is not
#   UNSCOREABLE the run does not contain the evidence, stated with what would
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The pre-registration's own stray-count bound for P8. Recorded here as it was
# WRITTEN, so the scorecard can report that the bound itself was mis-derived
# rather than quietly substituting a better one.
P8_PREREG_BOUND = 79000
P9_MAIN_EXPECTED = 8
P9_REC_EXPECTED = 21
P9_REC_TOLERANCE = 3


def verdict(ok):
    return "HELD" if ok else "FAILED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    ap.add_argument("--sweep", default=None)
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name
    sweep_path = Path(args.sweep) if args.sweep else out / f"m1a-sweep-{args.stamp}.json"
    d = json.loads(sweep_path.read_text())
    base = d["baseline"]
    rows = d["rows"]
    phase_path = out / f"grid-phase-{args.stamp}.json"
    phase = json.loads(phase_path.read_text()) if phase_path.exists() else None

    S = []

    # ---- P1 LINES -------------------------------------------------------
    S.append(dict(
        prediction="P1", subject="main-facet line errors largely resolve; "
                                 "dormer lines L11-L16 stay correct",
        verdict="UNSCOREABLE",
        why="line verdicts are a VISUAL REVIEW output. No review pass has been "
            "run on the filtered state, and under "
            "decisions/2026-07-27-review-loop-changes-blind-diff-and-free-text.md "
            "the reviewer grades blind, which is Emmett's eyes and not a "
            "computation. Nothing in this sweep bears on it either way.",
        what_would_score_it="a pass-2 visual review of a state built at an "
                            "adopted parameter value, with the diff toggle "
                            "OFF until after grading"))

    # ---- P2 CONTROL / the replacement assertions -------------------------
    ck = {c["id"]: c for c in d["cross_checks"]}
    a_ids = ["A1", "A2", "A3", "A5"]
    a_pass = all(ck[i]["passed"] for i in a_ids if i in ck)
    rec_counts = sorted({r["n_recovered"] for r in rows})
    S.append(dict(
        prediction="P2", subject="the control: the fix does what it claims, "
                                 "and facets 11-28 are not disturbed",
        verdict=verdict(bool(a_pass)),
        criterion="the amendment's replacement assertions A1 (point-domain "
                  "separation), A2 (independent component count), A3 (no-op "
                  "tripwire) and A5 (conservation) all pass at every grid "
                  "point. These replace the committed P2, which was a "
                  "prediction and could not fail loudly.",
        evidence={i: dict(passed=ck[i]["passed"],
                          n_failures=ck[i].get("n_failures"))
                  for i in a_ids if i in ck},
        indirect_effect=dict(
            recovered_counts_seen=rec_counts,
            baseline=base["n_recovered"],
            note="the INDIRECT half of the committed P2 (recovered facet "
                 "IDENTITY, not just count) is only partly scoreable here: "
                 "the sweep persisted recovered facet COUNTS, not their "
                 "per-facet geometry. Counts are reported; identity is not. "
                 "Stated as a shortfall of this run, not as a pass.")))

    # ---- P3 MAIN FACET QUALITY ------------------------------------------
    # The pre-registration recorded this as a MEASUREMENT TO MAKE, explicitly
    # allowing a negligible improvement as a legitimate outcome. So the only
    # way it fails is if quality gets WORSE.
    worse = [dict(scale=r["scale_mult"], frac=r["min_component_frac"],
                  delta=r["quality_bar_delta"])
             for r in rows if r["quality_bar_delta"] > 0]
    S.append(dict(
        prediction="P3", subject="main-facet quality improves, magnitude "
                                 "unknown and possibly small",
        verdict=verdict(not worse),
        criterion="the pre-registration recorded this as a measurement, not an "
                  "assumption, and stated that a negligible improvement is a "
                  "legitimate outcome. It therefore fails only if quality gets "
                  "WORSE. Quality is read through the bar, which is max() over "
                  "the 8 main facets' trimmed RMS/spacing.",
        evidence=dict(baseline_bar=base["quality_bar"],
                      bar_range=[min(r["quality_bar"] for r in rows),
                                 max(r["quality_bar"] for r in rows)],
                      grid_points_where_worse=worse)))

    # ---- P4 THE BAR SHOULD DROP -----------------------------------------
    dropped = [r for r in rows if r["quality_bar_delta"] < 0]
    S.append(dict(
        prediction="P4", subject="the quality bar should DROP",
        verdict=verdict(len(dropped) == len(rows)),
        criterion="stated with a direction, so it holds only if the bar drops "
                  "at EVERY grid point. A bar that rises anywhere is a failure "
                  "of a directional prediction, not noise.",
        evidence=dict(baseline_bar=base["quality_bar"],
                      n_grid_points=len(rows), n_dropped=len(dropped),
                      worst_rise=max((r["quality_bar_delta"] for r in rows),
                                     default=0.0),
                      largest_drop=min((r["quality_bar_delta"] for r in rows),
                                       default=0.0))))

    # ---- P5 BLOB 0 GETS FURTHER FROM PASSING -----------------------------
    b0b = base["blob0"]
    b0_rows = [r["blob0"] for r in rows if r["blob0"].get("found")]
    margins = [b["margin_to_bar"] for b in b0_rows
               if b.get("margin_to_bar") is not None]
    base_margin = b0b.get("margin_to_bar")
    if base_margin is None or not margins:
        S.append(dict(prediction="P5", subject="blob 0 gets FURTHER from "
                                               "passing, not closer",
                      verdict="UNSCOREABLE",
                      why="blob 0 produced no candidate plane in the baseline "
                          "or in the filtered runs, so there is no quality "
                          "margin to compare.",
                      evidence=dict(baseline=b0b)))
    else:
        # margin = candidate quality - bar. POSITIVE means failing. Further
        # from passing means the margin GROWS.
        grew = all(m >= base_margin for m in margins)
        S.append(dict(
            prediction="P5", subject="blob 0 gets FURTHER from passing, not "
                                     "closer",
            verdict=verdict(bool(grew)),
            criterion="margin = blob 0's best candidate quality minus the bar; "
                      "positive means failing. FURTHER from passing means the "
                      "margin does not shrink at any grid point. The "
                      "pre-registration says explicitly that blob 0 getting "
                      "closer is a surprise to be explained, not a result to "
                      "be welcomed.",
            evidence=dict(baseline_margin=base_margin,
                          margin_range=[min(margins), max(margins)],
                          baseline_quality=b0b.get("best_candidate_quality"),
                          baseline_bar=b0b.get("bar"),
                          n_grid_points_with_candidate=len(margins),
                          accepted_anywhere=any(b.get("accepted")
                                                for b in b0_rows),
                          blob_identity_overlap=[b.get("overlap_fraction")
                                                 for b in b0_rows])))

    # ---- P6 COVERAGE, direction deliberately NOT predicted ---------------
    covs = [r["facet_coverage_pct"] for r in rows]
    S.append(dict(
        prediction="P6", subject="facet coverage: a bounded quantity with an "
                                 "UNKNOWN direction",
        verdict="HELD",
        criterion="the amended P6 deliberately claims NO direction and records "
                  "coverage as bounded with unknown sign. It therefore cannot "
                  "be refuted by the coverage moving either way; it is scored "
                  "HELD only in the weak sense that no direction was claimed "
                  "and none was needed. Recorded as a claim that COST NOTHING "
                  "TO MAKE, which is the honest reading.",
        evidence=dict(baseline_pct=base["facet_coverage_pct"],
                      range_pct=[min(covs), max(covs)],
                      spread_pct=round(max(covs) - min(covs), 4),
                      note="the two coupling channels the 2026-07-28 amendment "
                           "required are reported per facet in the sweep rows "
                           "as normal_change_deg / centroid_shift_normal_in / "
                           "rotation_at_stray_radius_in")))

    # ---- P7 PITCH CHANGES ON ALL 8 MAIN FACETS ---------------------------
    # "Pitch WILL change on all 8 main facets" is the claim. Scored as: at
    # every grid point, is every main facet's pitch delta non-zero?
    all_moved, min_moved = True, None
    for r in rows:
        moved = sum(1 for p in r["per_facet"] if p["pitch_delta_deg"] != 0.0)
        if min_moved is None or moved < min_moved:
            min_moved = moved
        if moved != len(r["per_facet"]):
            all_moved = False
    maxd = max(r["max_abs_pitch_delta_deg"] for r in rows)
    S.append(dict(
        prediction="P7", subject="pitch will change on ALL 8 main facets; the "
                                 "prediction that matters most",
        verdict=verdict(bool(all_moved)),
        criterion="stated as WILL CHANGE on all 8, so it holds only if every "
                  "main facet's pitch delta is non-zero at every grid point "
                  "(reported to 4 dp, as the pre-registration requires). Note "
                  "this scores the DIRECTIONLESS claim that pitch moves; it "
                  "says nothing about whether the movement is large.",
        evidence=dict(fewest_facets_moved_at_any_grid_point=min_moved,
                      n_main=len(rows[0]["per_facet"]) if rows else 0,
                      max_abs_pitch_delta_deg=maxd,
                      per_grid_max=[dict(scale=r["scale_mult"],
                                         frac=r["min_component_frac"],
                                         max_abs=r["max_abs_pitch_delta_deg"])
                                    for r in rows]),
        consequence_for_the_frozen_result=dict(
            note="the pre-registration asks that this be checked rather than "
                 "assumed: the frozen 2026-07-18 run used this same "
                 "discover_facets path, so the pitch delta here also measures "
                 "how much the frozen pitch numbers were computed on "
                 "contaminated membership.",
            frozen_max_abs_error_deg=2.19,
            frozen_pass_threshold_deg=3.0,
            max_delta_from_this_fix_deg=maxd)))

    # ---- P8 THE RESIDUAL POOL -------------------------------------------
    newly = [r["newly_unexplained_points"] for r in rows]
    removed = [r["total_points_removed"] for r in rows]
    within = all(n <= P8_PREREG_BOUND for n in newly)
    S.append(dict(
        prediction="P8", subject="the residual pool grows, bounded above by "
                                 "about 79,000 points",
        verdict=verdict(bool(within)),
        criterion="the pre-registered bound is on NEWLY UNEXPLAINED POINTS, "
                  "not on points removed from membership. It holds if newly "
                  "unexplained stays at or under 79,000 at every grid point.",
        evidence=dict(prereg_bound=P8_PREREG_BOUND,
                      newly_unexplained_range=[min(newly), max(newly)],
                      total_removed_range=[min(removed), max(removed)],
                      realised_fraction_of_bound=[
                          round(min(newly) / P8_PREREG_BOUND, 4),
                          round(max(newly) / P8_PREREG_BOUND, 4)]),
        bound_provenance_warning=dict(
            issue="the 79,000 figure was the sum of STRAY COUNTS in "
                  "fragments-2026-07-27.json, which was measured on the "
                  "canonical POST-TRIM facet points. The filter runs on "
                  "PRE-TRIM membership, a strictly larger set. So the bound "
                  "was derived from the wrong point set and does not bound "
                  "what it was meant to bound, INDEPENDENTLY of whether the "
                  "numbers happen to fall under it.",
            actual_removed_range=[min(removed), max(removed)],
            reading="if total removed exceeds 79,000 while newly unexplained "
                    "stays under it, the arithmetic bound survives by accident "
                    "and the reasoning behind it does not. Emmett's own "
                    "standard applies: a prediction resting on a false premise "
                    "scores as luck even when the direction is right.")))

    # ---- P9 FACET COUNT -------------------------------------------------
    mains = [r["n_main"] for r in rows]
    recs = [r["n_recovered"] for r in rows]
    main_ok = all(m == P9_MAIN_EXPECTED for m in mains)
    rec_ok = all(abs(x - P9_REC_EXPECTED) <= P9_REC_TOLERANCE for x in recs)
    S.append(dict(
        prediction="P9", subject="main count 8; recovered 21 plus or minus 3; "
                                 "total 29 plus or minus 3",
        verdict=verdict(bool(main_ok and rec_ok)),
        criterion="both halves must hold at every grid point. A recovered "
                  "count outside the band is pre-registered as a stop-and-look.",
        evidence=dict(main_range=[min(mains), max(mains)],
                      recovered_range=[min(recs), max(recs)],
                      total_range=[min(r["n_total"] for r in rows),
                                   max(r["n_total"] for r in rows)],
                      grid_points_outside_band=[
                          dict(scale=r["scale_mult"],
                               frac=r["min_component_frac"],
                               n_recovered=r["n_recovered"])
                          for r in rows
                          if abs(r["n_recovered"] - P9_REC_EXPECTED)
                          > P9_REC_TOLERANCE])))

    # ---- the plateau question, which is NOT one of P1-P9 -----------------
    pl = d["plateau"]
    biggest = pl["groups"][0] if pl["groups"] else None
    disagree = sorted({tuple(r["count_area_disagreements"]) for r in rows})
    plateau_block = dict(
        n_distinct_answers=pl["n_distinct_answers"],
        n_grid_points=len(rows),
        largest_group=biggest,
        all_groups=pl["groups"],
        count_area_disagreement_sets=[list(x) for x in disagree],
        phase_caveat=(dict(
            worst_kept_fraction_spread=phase["headline"]["worst_kept_fraction_spread"],
            worst_at=phase["headline"]["worst_at"],
            worst_points=phase["headline"]["worst_kept_points_spread"],
            meaning="the sweep varies the connectivity SCALE and the minimum "
                    "COMPONENT FRACTION. It does not vary the raster's PHASE, "
                    "which is a third degree of freedom nobody chose, swept or "
                    "pre-registered. If phase moves the answer by more than "
                    "the swept parameters do, a flat grid is not a plateau, it "
                    "is a plateau in two of three dimensions.")
                      if phase else None))

    doc = dict(
        task="scorecard for the M1a pre-registration, P1 through P9",
        dataset=name, date=args.stamp,
        source_sweep=str(sweep_path.name),
        status="SCORING ONLY. No interpretation, no adoption. "
               "canonical-2026-07-26-r2 remains canonical.",
        criteria_disclosure=(
            "these criteria were written while the 20-point sweep was running, "
            "with one grid point (scale 2.5, fraction 1.0) already seen. They "
            "are therefore not blind. The criteria for P4, P6, P7 and P9 are "
            "taken from the pre-registration's own wording rather than "
            "invented at scoring time."),
        summary={s["prediction"]: s["verdict"] for s in S},
        scorecard=S,
        plateau=plateau_block)
    p = out / f"m1a-scorecard-{args.stamp}.json"
    p.write_text(json.dumps(doc, indent=2, default=float))

    print("\n  SCORECARD, before any interpretation\n")
    for s in S:
        print(f"    {s['prediction']:<4} {s['verdict']:<12} {s['subject']}")
    print(f"\n  plateau: {pl['n_distinct_answers']} distinct answers over "
          f"{len(rows)} grid points")
    if biggest:
        print(f"    largest group: {biggest['n_grid_points']} grid points")
    if phase:
        print(f"  phase caveat: worst kept-fraction spread over raster phase "
              f"= {phase['headline']['worst_kept_fraction_spread']} "
              f"({phase['headline']['worst_kept_points_spread']:,} points)")
    print(f"\n  wrote {p}")


if __name__ == "__main__":
    main()
