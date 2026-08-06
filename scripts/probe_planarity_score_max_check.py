# What does the CURRENT score_max keep, once the covariance is computed
# correctly? (2026-08-05)
#
#   .venv/Scripts/python.exe -u scripts/probe_planarity_score_max_check.py C:/odm/datasets/big_house
#
# DIAGNOSTIC ONLY. roofkit/ is not modified, no production path is wired to
# anything here, score_max / radius_mult / max_nn are read and never changed, and
# roof.npy, the canonical artifacts and the frozen 3,559.3 ft^2 figure are
# neither read nor rewritten. Mechanism 2 (max_nn=30 sampling an arbitrary 30 of
# a median 59 neighbours) is left INTACT: the neighbourhood gathering is
# imported unchanged from probe_planarity_centering_check, arbitrary subset and
# all, because this probe is about the threshold and nothing else.
#
# THIS PROBE DOES NOT CHOOSE A THRESHOLD, and that restraint is the point.
# It reports the corrected score distribution and what the EXISTING score_max
# does to it. It does not search for a replacement value, does not report which
# value would reproduce the current keep count, and does not hint at one.
# Picking a threshold is a decision that needs its own justification and its own
# pre-registration; a probe that quietly surfaced "the value that keeps the
# artifact stable" would be fitting the threshold to the answer, which is the
# failure this project has already logged for scale-dependent cutoffs.
#
# WHY THE QUESTION EXISTS. `planarity-centering-check.json` established two
# things. Centring resolves the negative-diagonal defect for all 8,623,218
# flagged points, completely. And, less expected, 31,322 of 50,000 points that
# were NEVER flagged also flip keep/discard once centred, median absolute score
# deviation 0.125 on a scale whose valid range is 0 to 1/3. A third method,
# numpy's covariance, agreed with the centred computation to 5.4e-20 and
# disagreed with production by up to the full magnitude of the matrix, so the
# centred numbers are the correct ones and the unflagged points were never
# healthy.
#
# The consequence for the threshold: score_max=0.05 was tuned by eye against
# scores produced by the uncentred computation, across MOST of the cloud rather
# than just the visibly broken half. Whatever tradeoff it was set to strike, it
# was struck against numbers that were wrong. That does not by itself mean the
# value is wrong now, and this probe deliberately does not assert that it is.
# It measures the size of the question.
#
# ANTI-NULLS (standing rule R4), all independent of anything reported:
#
#   1. The reconstructed production score must equal planarity_scores() BIT FOR
#      BIT over all 16.9M points, so the "before" side is production's own.
#   2. The flag set must match the counts the two prior probes recorded,
#      8,623,218 negative-diagonal and 7,198,421 negative-trace, exactly.
#   3. Neighbourhood fidelity: rebuilding the UNCENTRED covariance from the
#      re-gathered neighbours with Open3D's own cumulant form must reproduce
#      Open3D's matrices, so the "after" side is computed on production's
#      neighbourhoods rather than on a differently-chosen set.
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import open3d as o3d

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                        # noqa: E402
from roofkit.isolate import planarity_scores                  # noqa: E402
from probe_planarity_score_range import stages                # noqa: E402
# Imported, never re-implemented: the corrected computation must be the SAME one
# the centring probe validated against numpy, or this probe is measuring a third
# thing that resembles it.
import probe_planarity_centering_check as C                   # noqa: E402

REPO = Path(__file__).resolve().parents[1]
PRIOR = REPO / "reports" / "diagnostics" / "planarity-clamp-check.json"
BATCH = 400_000          # memory only; cannot change a result
PCTILES = [1, 5, 10, 25, 50, 75, 90, 95, 99]
FIDELITY_N = 2000
RNG_SEED = 20260805


def main():
    ap = argparse.ArgumentParser(
        description="Report the corrected planarity score distribution and what "
                    "the EXISTING score_max does to it. Diagnostic only; "
                    "proposes no replacement value.")
    ap.add_argument("dataset")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    dataset = Path(args.dataset).name
    score_max = cfg["score_max"]

    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    want_diag = prior["covariance_validity"]["points_with_a_negative_variance_on_the_diagonal"]
    want_trace = prior["covariance_validity"]["points_with_negative_trace"]

    pts, spacing, counts_stage = stages(cfg)
    radius = cfg["radius_mult"] * spacing
    C.RADIUS[0] = radius
    n = len(pts)
    print(f"planarity input {n:,}  spacing {spacing:.6f}  radius {radius:.6f}")
    print(f"score_max {score_max}  max_nn {C.MAX_NN}  (read from production, unchanged)")

    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(pts)
    cloud.estimate_covariances(
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=C.MAX_NN))
    cov_prod = np.asarray(cloud.covariances)
    diag = np.einsum("...ii->...i", cov_prod)
    flagged = (diag < 0.0).any(axis=1)
    n_flagged, n_trace = int(flagged.sum()), int((diag.sum(axis=1) < 0.0).sum())

    if n_flagged != want_diag or n_trace != want_trace:
        raise SystemExit(
            f"ANTI-NULL FAIL: flag set differs from the prior probes "
            f"({n_flagged:,}/{n_trace:,} vs {want_diag:,}/{want_trace:,} recorded)")
    print(f"  ANTI-NULL PASS  flag set matches the prior probes "
          f"({n_flagged:,} negative-diagonal, {n_trace:,} negative-trace)")

    prod = C.score_from_eig(np.linalg.eigvalsh(cov_prod))
    reference = planarity_scores(pts, radius)
    if not np.array_equal(prod, reference):
        raise SystemExit(
            f"ANTI-NULL FAIL: reconstructed production score differs from "
            f"planarity_scores() on {int((prod != reference).sum()):,} points")
    print(f"  ANTI-NULL PASS  production score == planarity_scores() bit for bit "
          f"over {n:,} points")
    del reference

    tree = o3d.geometry.KDTreeFlann(cloud)

    rng = np.random.default_rng(RNG_SEED)
    fid = rng.choice(n, size=FIDELITY_N, replace=False)
    fc, fk = C.gather_neighbours(tree, pts, fid)
    rebuilt = C.cov_cumulant(fc, fk)
    # Open3D returns the IDENTITY matrix when a neighbourhood is too small to
    # define a covariance (seen at k=1 and k=2). That is a documented fallback,
    # not a neighbour-selection difference, so it cannot be allowed to answer the
    # question this assertion asks. It is excluded and COUNTED, never waved past:
    # these points are also the ones whose corrected and production scores differ
    # for a reason that has nothing to do with centring, so the count belongs in
    # the report.
    fid_ident = np.all(np.isclose(cov_prod[fid], np.eye(3)), axis=(1, 2))
    n_fid_ident = int(fid_ident.sum())
    real = ~fid_ident
    dev = float(np.abs(rebuilt[real] - cov_prod[fid][real]).max()) if real.any() else 0.0
    if not np.allclose(rebuilt[real], cov_prod[fid][real], rtol=1e-6, atol=1e-12):
        raise SystemExit(
            f"ANTI-NULL FAIL: re-gathered neighbourhoods do not reproduce Open3D's "
            f"covariance (max deviation {dev:.3e} over {int(real.sum()):,} "
            f"non-fallback points); the corrected scores would be computed on a "
            f"different neighbour set than production used")
    print(f"  ANTI-NULL PASS  re-gathered neighbourhoods reproduce Open3D's "
          f"covariance (max dev {dev:.3e} over {int(real.sum()):,} points; "
          f"{n_fid_ident} identity fallbacks excluded)")

    # How many points cloud-wide sit on that fallback, since they flip for a
    # reason unrelated to centring and the reader needs to be able to net them out.
    identity_all = int(np.all(np.isclose(cov_prod, np.eye(3)), axis=(1, 2)).sum())
    del cov_prod, diag

    # --- the corrected score, over every point ---------------------------
    corrected = np.empty(n, dtype=np.float64)
    for start in range(0, n, BATCH):
        block = np.arange(start, min(start + BATCH, n))
        coords, ks = C.gather_neighbours(tree, pts, block)
        eig = np.linalg.eigvalsh(C.cov_centred(coords, ks))
        corrected[start:start + len(block)] = C.score_from_eig(eig)
        print(f"    corrected {min(start + BATCH, n):,} / {n:,}", end="\r", flush=True)
    print(" " * 60, end="\r")

    keep_prod = prod <= score_max
    keep_corr = corrected <= score_max
    flip = keep_prod != keep_corr
    k2d = flip & keep_prod        # kept by production, discarded once corrected
    d2k = flip & ~keep_prod       # discarded by production, kept once corrected

    def split(mask):
        return {
            "flips": int((flip & mask).sum()),
            "kept_to_discarded": int((k2d & mask).sum()),
            "discarded_to_kept": int((d2k & mask).sum()),
            "population": int(mask.sum()),
            "pct_of_population_flipping":
                float(100.0 * (flip & mask).sum() / max(1, int(mask.sum()))),
        }

    pcts = {str(p): float(np.percentile(corrected, p)) for p in PCTILES}

    report = {
        "probe": "what the existing score_max keeps once the covariance is centred",
        "kind": "diagnostic",
        "dataset": dataset,
        "date": date.today().isoformat(),
        "production_unchanged": True,
        "proposes_a_new_threshold": False,
        "note": "roofkit/ unmodified, no production path wired to this, "
                "score_max/radius_mult/max_nn read only, no artifact read or "
                "rewritten. Mechanism 2 left intact. No replacement score_max is "
                "searched for, reported, or implied: choosing a threshold is a "
                "separate decision needing its own justification.",
        "anti_nulls": {
            "production_score_is_productions_own": {
                "evidence": "reconstructed score == planarity_scores(), array_equal",
                "points_checked": int(n), "passed": True},
            "flag_set_matches_prior_probes": {
                "negative_diagonal": n_flagged, "recorded": want_diag,
                "negative_trace": n_trace, "recorded_trace": want_trace,
                "passed": True},
            "neighbourhood_fidelity": {
                "evidence": "uncentred rebuild from re-gathered neighbours "
                            "reproduces Open3D's covariance",
                "sampled_points": FIDELITY_N,
                "identity_fallbacks_excluded_from_sample": n_fid_ident,
                "max_abs_deviation": dev,
                "passed": True,
                "note": "Open3D returns the identity matrix for neighbourhoods too "
                        "small to define a covariance (k=1, k=2). Excluded here "
                        "because it is a documented fallback rather than a "
                        "neighbour-selection difference, and counted below because "
                        "those points flip for a reason unrelated to centring."},
        },
        "params_read_not_changed": {
            "score_max": float(score_max),
            "radius_mult": float(cfg["radius_mult"]),
            "max_nn": C.MAX_NN,
            "spacing": float(spacing), "radius": float(radius),
        },
        "stage_counts": counts_stage,
        "corrected_score_distribution": {
            "min": float(corrected.min()),
            "max": float(corrected.max()),
            "percentiles": pcts,
            "valid_range_note": "a correctly computed score lies in 0 .. 1/3",
            "outside_valid_range": int(((corrected < 0.0) | (corrected > 1/3)).sum()),
        },
        "production_score_distribution": {
            "min": float(prod.min()), "max": float(prod.max()),
            "percentiles": {str(p): float(np.percentile(prod, p)) for p in PCTILES},
        },
        "under_existing_score_max": {
            "score_max": float(score_max),
            "kept_by_production": int(keep_prod.sum()),
            "kept_by_corrected": int(keep_corr.sum()),
            "change_in_kept": int(keep_corr.sum()) - int(keep_prod.sum()),
            "total_flips": int(flip.sum()),
            "kept_to_discarded": int(k2d.sum()),
            "discarded_to_kept": int(d2k.sum()),
            "pct_of_all_points_flipping": float(100.0 * flip.mean()),
            "identity_fallback_points_cloud_wide": identity_all,
            "identity_fallback_note":
                "these carry Open3D's identity matrix, so their production score is "
                "the degenerate 1/3 for a reason unrelated to centring; they are "
                "included in the counts above and reported here so they can be "
                "netted out",
        },
        "breakdown": {
            "previously_flagged_negative_diagonal": split(flagged),
            "previously_unflagged": split(~flagged),
            "reading": "if the flip rate is comparable in both, the corrected "
                       "computation's impact is BROAD, and the visible negative "
                       "diagonal was never a good indicator of which points were "
                       "affected",
        },
    }

    out = REPO / "reports" / "diagnostics" / "planarity-scoremax-check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    w = 46
    print()
    print("  " + "-" * (w + 18))
    print(f"  {'PLANARITY score_max CHECK (corrected covariance)':<{w}}{'':>18}")
    print("  " + "-" * (w + 18))
    rows = [("corrected score distribution", ""),
            ("  min", f"{corrected.min():.6g}"),
            ("  max", f"{corrected.max():.6g}")]
    rows += [(f"  p{p}", f"{pcts[str(p)]:.6f}") for p in PCTILES]
    fl, un = report["breakdown"]["previously_flagged_negative_diagonal"], \
        report["breakdown"]["previously_unflagged"]
    rows += [
        ("outside the valid 0..1/3 range",
         f"{report['corrected_score_distribution']['outside_valid_range']:,}"),
        (f"under existing score_max = {score_max}", ""),
        ("  kept by production", f"{int(keep_prod.sum()):,}"),
        ("  kept by corrected", f"{int(keep_corr.sum()):,}"),
        ("  TOTAL FLIPS", f"{int(flip.sum()):,}"),
        ("    kept -> discarded", f"{int(k2d.sum()):,}"),
        ("    discarded -> kept", f"{int(d2k.sum()):,}"),
        ("    as pct of all points", f"{100.0 * flip.mean():.2f} pct"),
        ("  of which identity-fallback points", f"{identity_all:,}"),
        ("flips within previously-FLAGGED set", f"{fl['flips']:,}"),
        (f"  of {fl['population']:,} points",
         f"{fl['pct_of_population_flipping']:.2f} pct"),
        ("flips within previously-UNFLAGGED set", f"{un['flips']:,}"),
        (f"  of {un['population']:,} points",
         f"{un['pct_of_population_flipping']:.2f} pct"),
    ]
    for label, value in rows:
        print(f"  {label:<{w}}{value:>18}")
    print("  " + "-" * (w + 18))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
