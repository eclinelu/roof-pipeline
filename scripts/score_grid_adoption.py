# SCORES THE FIVE PREDICTIONS OF THE 2026-07-30 GRID-ADOPTION PRE-REGISTRATION.
#
#   .venv/Scripts/python.exe scripts/score_grid_adoption.py C:/odm/datasets/big_house
#
# Writes reports/big_house/grid-adoption-score-<date>.json      (standing rule R2)
#
# READ ONLY. Fits nothing, adopts nothing, and writes into no frozen artifact.
# The pre-registration is decisions/2026-07-30-preregistration-grid-adoption-
# execution.md and is NOT edited by this script: a score that can rewrite its
# own prediction is not a score.
#
# ---------------------------------------------------------------------------
# EVERY PRIOR VALUE BELOW IS COPIED FROM THE PRE-REGISTRATION, which was
# committed and pushed before the run. They are hard-coded on purpose. Reading
# them back out of the artifact being scored would make each prediction compare
# the run to itself, which is the failure the separate stamp exists to avoid.
# ---------------------------------------------------------------------------
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                           # noqa: E402
from roofkit.measure import facet_area, up_from_tilt             # noqa: E402
from roofkit.segment import level_cloud                          # noqa: E402
from roofkit import coverage as cov                              # noqa: E402

REPO = Path(__file__).resolve().parents[1]

REFERENCE_STAMP = "2026-07-26-r2"
NEW_STAMP = "2026-07-30-grid-adopted"
PRIOR_GRID_STAMP = "2026-07-28-grid"

# P1: the combined 8-main hash, from the pre-registration.
PRIOR_COMBINED_MAIN_HASH = (
    "e1df986ea6ac840be520663b398e9d6edd8d392a8dcc8a27dcd06a60eea64824")

# P2 / P5: the published deliverable.
PUBLISHED_TOTAL_FT2 = 3559.3
PUBLISHED_N_FACETS = 8

# P3: coverage under the adopted grid.
PRIOR_COVERAGE_PCT = 94.25
PRIOR_EXPLAINED_CU2 = 272.618
PRIOR_TESTABLE_CU2 = 289.237

# P4: phase spread under the adopted configuration.
PRIOR_PHASE_SPREAD = 0.18

# P5: recovery.
PRIOR_N_RECOVERED = 21


def main_facet_hash(idx, rec):
    """Identical definition to canonical_state.main_facet_hash. Restated here
    rather than imported so the scorer does not depend on the module it is
    scoring: if that definition drifted, importing it would hide the drift."""
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(np.sort(np.asarray(idx, dtype=np.int64)),
                                  dtype=np.int64).tobytes())
    h.update("|".join(rec["plane_abcd_hex"]).encode())
    h.update("|".join(rec["centroid_hex"]).encode())
    return h.hexdigest()


def load(out, stamp):
    doc = json.loads((out / f"canonical-{stamp}.json").read_text())
    npz = np.load(out / f"canonical-{stamp}.npz")
    return doc, npz


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    new_doc, new_npz = load(out, NEW_STAMP)
    ref_doc, ref_npz = load(out, REFERENCE_STAMP)
    scored = json.loads(
        (out / "comparison-2026-07-18-scored-2026-07-18.json").read_text())

    results = []
    assertions = []

    # ---- P1 -------------------------------------------------------------
    new_main = [r for r in new_doc["facets"] if r["kind"] == "main"]
    ref_main = [r for r in ref_doc["facets"] if r["kind"] == "main"]
    per_facet, all_match = [], (len(new_main) == len(ref_main))
    for k in range(min(len(new_main), len(ref_main))):
        got = main_facet_hash(new_npz[f"facet_{k}"], new_main[k])
        want = main_facet_hash(ref_npz[f"facet_{k}"], ref_main[k])
        ok = (got == want)
        all_match = all_match and ok
        per_facet.append(dict(facet=k, hash=got, reference=want, match=ok,
                              n_points=new_main[k]["n_points"]))
    combined = hashlib.sha256(
        "".join(p["hash"] for p in per_facet).encode()).hexdigest()
    prior_ok = (combined == PRIOR_COMBINED_MAIN_HASH)

    # The AREA CROSS-CHECK. Pre-registered explicitly as a check on the AREA
    # FUNCTION, not as confirmation of bit-identity: identical indices and
    # identical coefficients necessarily give identical areas, so this can add
    # no evidence about facet identity. It can only detect drift in the area
    # code or the scale factor since 2026-07-18.
    cfg = load_config(args.dataset)
    pts_all = np.load(cfg["roof_path"])
    if cfg["level_tilt_deg"] is not None:
        pts_all = level_cloud(pts_all, up_from_tilt(cfg["level_tilt_deg"],
                                                    cfg["level_uphill_az_deg"]))
    in_per_cu = float(scored["scale"]["in_per_cu"])
    ft2_per_cu2 = (in_per_cu / 12.0) ** 2
    areas = []
    for k, rec in enumerate(new_main):
        p = pts_all[new_npz[f"facet_{k}"]]
        n = np.array([float.fromhex(h) for h in rec["plane_abcd_hex"][:3]])
        s_f = float(np.median(cov._nn(p)))
        a_cu2 = float(facet_area(p, n, cfg["alpha_mult"] * s_f))
        want = next((a for a in scored["areas"] if a["facet"] == k), None)
        areas.append(dict(
            facet=k, area_cu2=round(a_cu2, 4),
            area_ft2=round(a_cu2 * ft2_per_cu2, 2),
            stored_2026_07_18_ft2=(want or {}).get("area_ft2"),
            delta_ft2=(None if want is None
                       else round(a_cu2 * ft2_per_cu2 - want["area_ft2"], 3))))
    area_within = [a for a in areas
                   if a["delta_ft2"] is not None and abs(a["delta_ft2"]) <= 0.1]

    results.append(dict(
        prediction="P1",
        claim="the 8 main facets are bit-identical to canonical-2026-07-26-r2: "
              "same sorted index sets, same plane coefficients, same centroids, "
              "at full stored precision",
        verdict="PASS" if (all_match and prior_ok) else "FAIL",
        detail=dict(all_match=all_match,
                    combined_hash=combined,
                    prior_combined_hash=PRIOR_COMBINED_MAIN_HASH,
                    matches_preregistered_prior=prior_ok,
                    per_facet=per_facet),
        area_cross_check=dict(
            status="REPORTED, NOT PART OF THE VERDICT",
            what="a check on the AREA FUNCTION, not independent confirmation "
                 "of bit-identity: identical indices and coefficients "
                 "necessarily give identical areas",
            n_within_0_1_ft2=len(area_within), n_facets=len(areas),
            areas=areas)))

    # ---- P2 -------------------------------------------------------------
    total = scored["total_area_ft2"]
    n_rows = len(scored["areas"])
    s = round(sum(a["area_ft2"] for a in scored["areas"]), 1)
    results.append(dict(
        prediction="P2",
        claim=f"the published deliverable stays {PUBLISHED_TOTAL_FT2} ft^2 over "
              f"{PUBLISHED_N_FACETS} main facets",
        verdict="PASS" if (total == PUBLISHED_TOTAL_FT2
                           and n_rows == PUBLISHED_N_FACETS
                           and s == PUBLISHED_TOTAL_FT2) else "FAIL",
        detail=dict(total_area_ft2=total, n_facet_rows=n_rows,
                    sum_of_rows=s, expected=PUBLISHED_TOTAL_FT2)))

    # ---- P3 -------------------------------------------------------------
    fc = new_doc["coverage"]["facet_coverage"]
    p3 = (fc["pct"] == PRIOR_COVERAGE_PCT
          and fc["explained_cu2"] == PRIOR_EXPLAINED_CU2
          and fc["testable_cu2"] == PRIOR_TESTABLE_CU2)
    results.append(dict(
        prediction="P3",
        claim=f"coverage on the fixed grid reproduces {PRIOR_COVERAGE_PCT} pct",
        verdict="PASS" if p3 else "FAIL",
        detail=dict(pct=fc["pct"], explained_cu2=fc["explained_cu2"],
                    testable_cu2=fc["testable_cu2"],
                    expected=dict(pct=PRIOR_COVERAGE_PCT,
                                  explained_cu2=PRIOR_EXPLAINED_CU2,
                                  testable_cu2=PRIOR_TESTABLE_CU2))))

    # ---- P4 -------------------------------------------------------------
    # Read from the phase sweep re-run under the adopted configuration.
    sweeps = sorted(out.glob("grid-adoption-*.json"))
    sweeps = [p for p in sweeps if "score" not in p.name]
    spread, sweep_src = None, None
    if sweeps:
        sweep_src = sweeps[-1].name
        sw = json.loads(sweeps[-1].read_text())
        spread = sw["new_stability_claim"]["spread"]["facet_coverage_pct"]["spread"]
    results.append(dict(
        prediction="P4",
        claim=f"phase spread across the grid-origin sweep <= "
              f"{PRIOR_PHASE_SPREAD} points",
        verdict=("PASS" if (spread is not None and spread <= PRIOR_PHASE_SPREAD)
                 else "FAIL" if spread is not None else "UNSCORED"),
        detail=dict(spread=spread, threshold=PRIOR_PHASE_SPREAD,
                    source=sweep_src)))

    # ---- P5 -------------------------------------------------------------
    n_rec = new_doc["counts"]["n_recovered"]
    p5 = (n_rec == PRIOR_N_RECOVERED and total == PUBLISHED_TOTAL_FT2
          and n_rows == PUBLISHED_N_FACETS)
    results.append(dict(
        prediction="P5",
        claim=f"recovered facets stay {PRIOR_N_RECOVERED} and stay OUT of the "
              f"deliverable total",
        verdict="PASS" if p5 else "FAIL",
        detail=dict(n_recovered=n_rec, expected_n_recovered=PRIOR_N_RECOVERED,
                    total_area_ft2=total, n_facet_rows=n_rows),
        note="404.9 ft^2, named in the task as the recovered-facet area, does "
             "not appear anywhere in this repo and is NOT what P5 is scored "
             "on. No area total has ever been computed from the 29-facet "
             "state."))

    # ---- INDEPENDENT ASSERTIONS (standing rule R4) ----------------------
    # Each is built from something known independently of the result it guards.
    assertions.append(dict(
        id="S0",
        check="the scorer is reading the NEW artifact, not the reference: the "
              "two states must differ somewhere",
        passed=bool(new_doc["coverage"]["facet_coverage"]["pct"]
                    != ref_doc["coverage"]["facet_coverage"]["pct"]),
        why="ANTI-NULL. If a path bug made both loads return the same file, "
            "every prediction would pass trivially and the pass would be "
            "meaningless.",
        detail=dict(new=new_doc["coverage"]["facet_coverage"]["pct"],
                    reference=ref_doc["coverage"]["facet_coverage"]["pct"])))
    assertions.append(dict(
        id="S1",
        check="both states index the SAME source cloud",
        passed=bool(new_doc["replay"]["source_cloud_sha256"]
                    == ref_doc["replay"]["source_cloud_sha256"]),
        why="indices into a different cloud would select different geometry "
            "and the hash comparison would be meaningless",
        detail=dict(sha=new_doc["replay"]["source_cloud_sha256"][:16])))
    assertions.append(dict(
        id="S2",
        check="the run recorded its own in-run main-facet hash check as passing",
        passed=bool((new_doc.get("main_facet_hash_check") or {})
                    .get("all_match") is True),
        why="the scorer recomputes the hashes independently; this confirms the "
            "RUN also checked them and would have aborted before writing",
        detail=(new_doc.get("main_facet_hash_check") or {}).get(
            "combined_hash")))
    assertions.append(dict(
        id="S3",
        check="the new artifact did not overwrite either frozen state",
        passed=bool(new_doc["date"] == NEW_STAMP
                    and ref_doc["date"] == REFERENCE_STAMP
                    and (out / f"canonical-{PRIOR_GRID_STAMP}.json").exists()),
        why="adoption must supersede, never overwrite",
        detail=dict(new=new_doc["date"], reference=ref_doc["date"])))
    assertions.append(dict(
        id="S4",
        check="the single-ownership assertion ran and passed in the new run",
        passed=bool(new_doc["single_ownership_check"]["passed"]),
        why="permanent, every run: no point may be owned by two facets"))

    passed = [r for r in results if r["verdict"] == "PASS"]
    failed = [r for r in results if r["verdict"] == "FAIL"]
    a_failed = [a for a in assertions if not a["passed"]]

    doc = dict(
        task="score the five predictions of the 2026-07-30 grid-adoption "
             "pre-registration",
        preregistration="decisions/2026-07-30-preregistration-grid-adoption-"
                        "execution.md",
        dataset=name, date=args.stamp,
        scored_artifact=f"canonical-{NEW_STAMP}",
        reference_artifact=f"canonical-{REFERENCE_STAMP}",
        summary=dict(n_pass=len(passed), n_fail=len(failed),
                     verdicts={r["prediction"]: r["verdict"] for r in results}),
        predictions=results,
        assertions=assertions,
        assertions_all_passed=not a_failed,
        carried_forward=dict(
            footprint_residue_NOT_fixed=dict(
                filled_spread_cu2=4.40, eroded_spread_cu2=6.20,
                cause="min_pts=2 discretisation, not a grid artifact",
                rule="must be carried on ANY footprint claim"),
            capture_on_fixed_grid=dict(
                density_testable_pct=82.72,
                testable_cu2=289.237, footprint_eroded_cu2=349.640,
                one_point_cells=227964, p10_points_per_occupied_cell=1.0),
            pitch_bias=dict(
                deg=1.83, status="ACCEPTED, UNTESTED. Known limit under 3e.",
                rule="stated attached to ANY pitch number, never in an "
                     "appendix. NO correction is applied to any pitch on any "
                     "facet anywhere in this pass.")),
    )
    jf = out / f"grid-adoption-score-{args.stamp}.json"
    jf.write_text(json.dumps(doc, indent=2, default=float))

    print(f"\n  SCORE: {len(passed)} PASS, {len(failed)} FAIL")
    for r in results:
        print(f"    {r['prediction']}  {r['verdict']:8s} {r['claim'][:66]}")
    print(f"\n  assertions: {len(assertions) - len(a_failed)}/"
          f"{len(assertions)} passed")
    for a in assertions:
        print(f"    {a['id']}  {'PASS' if a['passed'] else 'FAIL'}  "
              f"{a['check'][:64]}")
    print(f"\n  wrote {jf}")
    if a_failed:
        print("\n  ASSERTION FAILED: the score itself is not trustworthy.")
        sys.exit(4)
    if failed:
        print("\n  A PREDICTION FAILED. Per the pre-registration, the pass "
              "STOPS and nothing is adopted.")
        sys.exit(5)


if __name__ == "__main__":
    main()
