# Does the negative-eigenvalue defect (mechanism 1) actually change any
# keep/discard outcome? (2026-08-05)
#
#   .venv/Scripts/python.exe -u scripts/probe_planarity_clamp_check.py C:/odm/datasets/big_house
#
# DIAGNOSTIC ONLY. This script does not import a clamp into roofkit/, does not
# touch the production filter, does not change score_max, radius_mult or max_nn,
# and does not read or rewrite roof.npy or any canonical artifact. The clamp
# exists inside this file and nowhere else.
#
# THE QUESTION. `2026-08-05-planarity-score-leaves-its-range-and-depends-on-
# enumeration-order.md` recorded that 41.25 pct of production input points score
# NEGATIVE, and that 73.55 pct of the points the filter keeps were admitted on
# such a score. That measures how often the defect FIRES. It does not measure
# whether the defect CHANGES ANYTHING, and those are different questions: a
# score can be numerically wrong and still land on the correct side of the
# threshold. This probe measures the second question and only the second.
#
# Mechanism 2 (max_nn=30 sampling an arbitrary 30 of a median 59 neighbours,
# 598 flips on a 2M subset) is already measured and is deliberately untouched
# here.
#
# WHAT THE CLAMP IS. Production computes, per point,
#
#     eig    = eigvalsh(covariance)        ascending, so eig[0] is smallest
#     total  = eig.sum()
#     score  = eig[0] / total              only where total > 1e-12
#     score  = 1/3                         otherwise (the degenerate default)
#
# and keeps the point when `score <= score_max`. On a near-exactly-coplanar
# neighbourhood the covariance is numerically rank-deficient and eigvalsh
# returns a small NEGATIVE eig[0], which makes the score negative, which passes
# `<= score_max` unconditionally. The clamp replaces that negative eig[0] with
# the 0 it is a floating-point perturbation of, and recomputes.
#
# WHY THE CLAMP CONVENTION CANNOT MOVE THE SCORE, AND WHERE IT CAN STILL BITE.
# Once eig[0] is set to 0 the score is 0 / total = 0 for ANY positive total, so
# it makes no difference whether `total` is left as the original sum or
# recomputed from the clamped eigenvalues. The score is convention-free.
#
# The one place the convention CAN matter is the degeneracy guard, because
# clamping raises the sum: a point whose original total fell at or below 1e-12
# (production: score 1/3, DISCARDED) can have a clamped total above it
# (clamped: score 0, KEPT). That is a real flip and it is the only mechanism by
# which this clamp can flip anything at all. Both conventions are therefore
# computed and compared, so the convention is a measured quantity rather than an
# assumption.
#
# WHICH FLIP DIRECTIONS ARE EVEN POSSIBLE. Worth stating in advance, because it
# is what makes the result interpretable rather than a bare number:
#
#   - Points with eig[0] >= 0 are untouched by the clamp. They cannot flip.
#   - Points with eig[0] < 0 and total > 1e-12 score negative in production
#     (KEPT) and 0 when clamped (KEPT, since 0 <= score_max for any sane
#     positive score_max). They cannot flip either.
#   - Points with eig[0] < 0 and total <= 1e-12 score 1/3 in production
#     (DISCARDED) and may score 0 when clamped (KEPT). ONLY THESE CAN FLIP.
#
# So a nonzero count can only appear in the DISCARDED -> KEPT direction, and a
# KEPT -> DISCARDED count is structurally impossible. Both are reported anyway:
# a nonzero value in the impossible direction would mean this reasoning or the
# implementation is wrong, which makes it a free correctness check rather than a
# redundant column.
#
# ANTI-NULL (standing rule R4). The eigen-decomposition here is recomputed
# rather than reused, so it must be shown to be the SAME one production uses
# before any comparison built on it means anything. The probe asserts, before
# writing anything, that its reconstructed production score equals
# planarity_scores() BIT FOR BIT over all 16.9M points. That assertion is
# independent of everything this probe reports: it would fail identically
# whether the flip count came out at zero or at millions.
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
# The stage 0-4 chain is imported, never re-typed: this probe must see exactly
# the input the range probe saw, and two copies of a filter chain is two things
# to drift.
from probe_planarity_score_range import stages                # noqa: E402

REPO = Path(__file__).resolve().parents[1]
MAX_NN = 30          # production value, read here, NOT changed
DEGENERATE_TOTAL = 1e-12   # production guard, read here, NOT changed
DEGENERATE_SCORE = 1.0 / 3.0   # production default for degenerate points


def covariance_validity(points, radius, max_nn=MAX_NN):
    """Are the covariance matrices production feeds to eigvalsh even valid?

    This is not a detour. The clamp's premise is that eig[0] is a small negative
    perturbation of a true zero, i.e. that the matrix is a genuine covariance
    and only its decomposition is noisy. That premise is checkable directly and
    independently of any eigenvalue: every diagonal entry of a covariance matrix
    is a variance and cannot be negative, and the trace cannot be negative. If
    those fail, the input is not a covariance and clamping its eigenvalues is
    fixing the wrong end of the computation.

    Also reported: the coordinate magnitude. The cloud is georeferenced UTM, so
    x is order 5.5e5 and y order 4.5e6. A covariance accumulated as E[xy] minus
    E[x]E[y] on those magnitudes subtracts numbers near 2e13 to obtain a result
    near 1e-4, which is roughly seventeen orders of magnitude of cancellation
    against float64's sixteen digits of precision. That is enough to lose the
    result entirely, and it predicts exactly the artefact seen here: entries
    quantised to dyadic fractions like 1/128 and 1/8192, which are the ULP of
    numbers of that size, rather than smooth small values.
    """
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    cloud.estimate_covariances(
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=max_nn))
    cov = np.asarray(cloud.covariances)
    diag = np.einsum("...ii->...i", cov)
    neg_diag = (diag < 0.0).any(axis=1)
    neg_trace = diag.sum(axis=1) < 0.0
    centre = points.mean(axis=0)
    return {
        "why": "a covariance's diagonal entries are variances and cannot be "
               "negative; a negative one proves the matrix is not a covariance",
        "points_with_a_negative_variance_on_the_diagonal": int(neg_diag.sum()),
        "pct_with_a_negative_variance": float(100.0 * neg_diag.mean()),
        "points_with_negative_trace": int(neg_trace.sum()),
        "coordinate_centre": [float(v) for v in centre],
        "coordinate_magnitude_note":
            "cloud is georeferenced UTM and is NOT centred before the covariance "
            "is accumulated; x**2 and y**2 reach ~3e11 and ~2e13 while the "
            "variances being recovered are ~1e-4",
        "cancellation_digits_estimate":
            float(np.log10((centre ** 2).max() / 1e-4)),
        "reading": "if this count is large, the negative smallest eigenvalue is a "
                   "SYMPTOM. The clamp addresses the eigenvalue, not the lost "
                   "precision that produced it.",
    }


def eigen_parts(points, radius, max_nn=MAX_NN):
    """The eigenvalues production computes, obtained the way production does.

    This is a re-derivation of the inside of planarity_scores, not a variation
    on it: same Open3D call, same search parameters, same eigvalsh. The probe
    needs eig[0] and the total separately, which planarity_scores does not
    return, and the anti-null in main() is what proves the re-derivation lands
    on the identical numbers.
    """
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    cloud.estimate_covariances(
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=max_nn))
    eig = np.linalg.eigvalsh(np.asarray(cloud.covariances))   # ascending
    return eig


def production_score(eig):
    """Exactly roofkit.isolate.planarity_scores' arithmetic, from eigenvalues."""
    total = eig.sum(axis=1)
    scores = np.full(len(eig), DEGENERATE_SCORE)
    ok = total > DEGENERATE_TOTAL
    scores[ok] = eig[ok, 0] / total[ok]
    return scores, total


def clamped_score(eig, recompute_total):
    """The clamp, defined ONLY in this diagnostic.

    eig[0] < 0 is treated as 0. `recompute_total` selects whether the sum used
    by the degeneracy guard is rebuilt from the clamped eigenvalues (True) or
    left as the original sum (False). The score is 0 either way; see the header
    for why only the guard can differ.
    """
    e0 = np.where(eig[:, 0] < 0.0, 0.0, eig[:, 0])
    if recompute_total:
        total = e0 + eig[:, 1] + eig[:, 2]
    else:
        total = eig.sum(axis=1)
    scores = np.full(len(eig), DEGENERATE_SCORE)
    ok = total > DEGENERATE_TOTAL
    scores[ok] = e0[ok] / total[ok]
    return scores


def main():
    ap = argparse.ArgumentParser(
        description="Measure whether clamping negative smallest eigenvalues "
                    "changes any keep/discard decision. Diagnostic only.")
    ap.add_argument("dataset")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    dataset = Path(args.dataset).name
    score_max = cfg["score_max"]

    pts, spacing, counts = stages(cfg)
    radius = cfg["radius_mult"] * spacing
    n = len(pts)
    print(f"planarity input {n:,}  spacing {spacing:.6f}  radius {radius:.6f}")
    print(f"score_max {score_max}  max_nn {MAX_NN}  (read from production, unchanged)")

    validity = covariance_validity(pts, radius)
    eig = eigen_parts(pts, radius)
    prod, total = production_score(eig)

    # --- anti-null, BEFORE any comparison or any write --------------------
    reference = planarity_scores(pts, radius)
    if not np.array_equal(prod, reference):
        n_bad = int((prod != reference).sum())
        raise SystemExit(
            f"ANTI-NULL FAIL: the reconstructed production score differs from "
            f"planarity_scores() on {n_bad:,} of {n:,} points. This probe is not "
            f"reproducing the production path and its flip count would describe "
            f"some other computation."
        )
    print(f"  ANTI-NULL PASS  reconstructed production score == planarity_scores() "
          f"bit for bit over {n:,} points")
    del reference

    keep_prod = prod <= score_max
    negative = eig[:, 0] < 0.0

    clamp_a = clamped_score(eig, recompute_total=True)    # primary convention
    clamp_b = clamped_score(eig, recompute_total=False)
    convention_differs = int((clamp_a != clamp_b).sum())

    keep_clamp = clamp_a <= score_max
    flip = keep_prod != keep_clamp
    kept_to_discarded = int((flip & keep_prod).sum())
    discarded_to_kept = int((flip & ~keep_prod).sum())

    # The SAME comparison under the other convention. This is not a variant
    # worth burying in a note: if the two conventions disagree on the flip
    # count, then "does the clamp change anything" has no single answer and the
    # headline number is a property of the fix, not of the defect.
    keep_clamp_b = clamp_b <= score_max
    flip_b = keep_prod != keep_clamp_b
    flip_b_total = int(flip_b.sum())

    # Characterise the flip set, because a flip driven purely by the degeneracy
    # guard raises the question of whether those neighbourhoods carry any signal
    # at all. total is the trace of the covariance, i.e. the neighbourhood's
    # total spatial variance; radius**2 is the scale it would have if the
    # neighbourhood filled the search sphere.
    fl = flip if flip.any() else None
    if fl is not None:
        tot_fl = total[fl]
        ratio = tot_fl / (radius ** 2)
        flip_scale = {
            "total_variance_median": float(np.median(tot_fl)),
            "total_variance_p99": float(np.percentile(tot_fl, 99)),
            "total_variance_max": float(tot_fl.max()),
            "as_fraction_of_radius_squared_median": float(np.median(ratio)),
            "as_fraction_of_radius_squared_max": float(ratio.max()),
            "abs_eig0_over_sum_other_two_median": float(np.median(
                np.abs(eig[fl, 0]) / np.maximum(eig[fl, 1] + eig[fl, 2], 1e-300))),
            "reading": "these neighbourhoods' total variance against the scale a "
                       "full neighbourhood would have. A ratio near zero means the "
                       "covariance is numerical noise, and the eigen-decomposition "
                       "of noise is what the two conventions disagree about.",
        }
    else:
        flip_scale = {"reading": "no flips; nothing to characterise"}

    report = {
        "probe": "planarity negative-eigenvalue clamp: does it change any decision",
        "kind": "diagnostic",
        "dataset": dataset,
        "date": date.today().isoformat(),
        "mechanism": "1 of 2 (negative smallest eigenvalue). Mechanism 2 "
                     "(max_nn enumeration order) is measured elsewhere and is "
                     "untouched here.",
        "production_unchanged": True,
        "note": "The clamp exists only inside scripts/probe_planarity_clamp_check.py. "
                "roofkit/ is unmodified, no production path is wired to it, and no "
                "artifact was read or rewritten.",
        "anti_null": {
            "claim": "the eigenvalues used here are the ones production uses",
            "evidence": "reconstructed production score == planarity_scores(), "
                        "np.array_equal over every point",
            "passed": True,
            "points_checked": int(n),
        },
        "params_read_not_changed": {
            "score_max": float(score_max),
            "radius_mult": float(cfg["radius_mult"]),
            "max_nn": MAX_NN,
            "degenerate_total_guard": DEGENERATE_TOTAL,
            "spacing": float(spacing),
            "radius": float(radius),
        },
        "stage_counts": counts,
        "totals": {
            "total_points": int(n),
            "negative_smallest_eigenvalue": int(negative.sum()),
            "negative_pct": float(100.0 * negative.mean()),
            "kept_by_production": int(keep_prod.sum()),
            "kept_by_clamped": int(keep_clamp.sum()),
        },
        "flips": {
            "total": int(flip.sum()),
            "kept_by_production_discarded_by_clamped": kept_to_discarded,
            "discarded_by_production_kept_by_clamped": discarded_to_kept,
            "pct_of_all_points": float(100.0 * flip.mean()),
            "pct_of_negative_score_points":
                float(100.0 * flip.sum() / max(1, int(negative.sum()))),
            "structurally_possible_directions":
                "only discarded->kept; a nonzero kept->discarded count would mean "
                "the clamp reasoning or this implementation is wrong",
        },
        "clamped_score_range": [float(clamp_a.min()), float(clamp_a.max())],
        "production_score_range": [float(prod.min()), float(prod.max())],
        "clamp_convention_check": {
            "question": "does rebuilding the total from clamped eigenvalues differ "
                        "from leaving the original sum",
            "points_differing": convention_differs,
            "flips_convention_recompute_total": int(flip.sum()),
            "flips_convention_keep_original_total": flip_b_total,
            "reading": "the score is 0/total either way; only the 1e-12 degeneracy "
                       "guard can distinguish them. If these two flip counts "
                       "differ, the answer to 'does the clamp change anything' is "
                       "a property of the chosen fix, not of the defect.",
        },
        "flip_set_scale": flip_scale,
        "covariance_validity": validity,
    }

    out = REPO / "reports" / "diagnostics" / "planarity-clamp-check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    w = 46
    print()
    print("  " + "-" * (w + 18))
    print(f"  {'PLANARITY CLAMP CHECK (mechanism 1)':<{w}}{'':>18}")
    print("  " + "-" * (w + 18))
    rows = [
        ("total points", f"{n:,}"),
        ("negative smallest eigenvalue", f"{int(negative.sum()):,}"),
        ("  as pct of all points", f"{100.0 * negative.mean():.2f} pct"),
        ("kept by production", f"{int(keep_prod.sum()):,}"),
        ("kept by clamped", f"{int(keep_clamp.sum()):,}"),
        ("FLIPS, total", f"{int(flip.sum()):,}"),
        ("  kept by prod -> discarded by clamp", f"{kept_to_discarded:,}"),
        ("  discarded by prod -> kept by clamp", f"{discarded_to_kept:,}"),
        ("  as pct of all points", f"{100.0 * flip.mean():.6f} pct"),
        ("production score range",
         f"{prod.min():.4g} .. {prod.max():.4g}"),
        ("clamped score range",
         f"{clamp_a.min():.6g} .. {clamp_a.max():.6g}"),
        ("clamp convention, points differing", f"{convention_differs:,}"),
        ("  flips if total is recomputed", f"{int(flip.sum()):,}"),
        ("  flips if original total is kept", f"{flip_b_total:,}"),
        ("covariances with a NEGATIVE variance on diag",
         f"{validity['points_with_a_negative_variance_on_the_diagonal']:,}"),
        ("  as pct of all points",
         f"{validity['pct_with_a_negative_variance']:.2f} pct"),
    ]
    for label, value in rows:
        print(f"  {label:<{w}}{value:>18}")
    print("  " + "-" * (w + 18))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
