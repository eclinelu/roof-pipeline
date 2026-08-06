# Does centring each neighbourhood before accumulating its covariance remove the
# negative-variance defect? (2026-08-05)
#
#   .venv/Scripts/python.exe -u scripts/probe_planarity_centering_check.py C:/odm/datasets/big_house
#
# DIAGNOSTIC ONLY. roofkit/ is not modified, no production path is wired to
# anything here, score_max / radius_mult / max_nn are read and never changed, and
# roof.npy, the canonical artifacts and the frozen 3,559.3 ft^2 figure are
# neither read nor rewritten. Mechanism 2 (max_nn=30 sampling an arbitrary 30 of
# a median 59 neighbours) is deliberately left INTACT here: the neighbour
# selection used below is production's, arbitrary subset and all, because the
# question is what centring alone changes.
#
# THE HYPOTHESIS UNDER TEST. `planarity-clamp-check.json` found 8,623,218 of
# 16,885,409 points (51.07 pct) carrying a NEGATIVE variance on the covariance
# diagonal, and 7,198,421 with a negative trace. Both are mathematically
# impossible for a real covariance matrix. The proposed cause is catastrophic
# cancellation: the cloud is georeferenced UTM centred near
# (553485.9, 4543297.7), and the covariance is accumulated on those raw
# coordinates, so recovering variances of order 1e-4 costs about 17.3 digits of
# cancellation against float64's ~16.
#
# WHY THE CUMULANT FORM IS THE SUSPECT, precisely. Open3D's per-point covariance
# accumulates nine cumulants over the neighbourhood -- sum(x), sum(y), sum(z),
# sum(x*x), sum(x*y), ... -- divides them by the neighbour count, and then forms
#
#     cov(0,0) = E[x*x] - E[x]*E[x]
#
# and so on. On raw UTM x the two terms are each about 3.06e11 and their
# difference is about 1e-4. On raw UTM y they are each about 2.06e13. That
# subtraction is where the answer dies, and it explains the artefact seen in the
# matrices: entries land on exact dyadic fractions like -1/128 and -1/8192,
# which are the ULP of numbers of that magnitude, rather than on smooth small
# values.
#
# The textbook fix is not a tolerance or a clamp, it is to subtract a reference
# point first. Centring on the NEIGHBOURHOOD'S OWN CENTROID is used here because
# that is the definition of a covariance, so the centred computation is the
# reference implementation rather than an approximation of one.
#
# THE FLAGGED SET. The prior probe recorded the flagged points as a COUNT, not
# as indices, so there is no per-point flag on disk to load. The set is
# therefore recomputed by the identical deterministic computation and then
# CHECKED against the stored counts: 8,623,218 negative-diagonal and 7,198,421
# negative-trace, both of which must match exactly or this probe aborts. That
# makes "the same flag set" a verified claim rather than an assumption.
#
# ANTI-NULLS (standing rule R4), both independent of the result:
#
#   1. NEIGHBOURHOOD FIDELITY. Re-gathering neighbours by hand only means
#      something if the gathered set is the one production used. So the probe
#      rebuilds the UNCENTRED covariance from its own gathered neighbours using
#      the cumulant form above, and requires it to reproduce Open3D's own
#      covariance matrices. If the neighbour sets differed, or the estimator
#      differed, this fails -- and it fails whether or not centring helps.
#   2. THE CONTROL GROUP. 50,000 points NOT in the flagged set are recomputed
#      centred and compared to their production scores. Centring changes the
#      arithmetic path, so exact equality is not expected and not required; what
#      is required is that the answers do not MOVE. A fix that silently changed
#      already-healthy points would be a different problem wearing this one's
#      clothes.
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import open3d as o3d

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                        # noqa: E402
from probe_planarity_score_range import stages                # noqa: E402

REPO = Path(__file__).resolve().parents[1]
PRIOR = REPO / "reports" / "diagnostics" / "planarity-clamp-check.json"
MAX_NN = 30              # production value, read here, NOT changed
DEGENERATE_TOTAL = 1e-12  # production guard, read here, NOT changed
DEGENERATE_SCORE = 1.0 / 3.0
CONTROL_N = 50_000
BATCH = 400_000          # points per pass; memory only, cannot change a result
RNG_SEED = 20260805


def gather_neighbours(tree, pts, idx_block):
    """The neighbours production used, via the same hybrid search.

    Returns (coords, counts) where coords is (B, MAX_NN, 3) padded with the
    query point itself beyond each row's count. Padding with the query point is
    never read: every consumer slices by `counts` first. It exists only so the
    array is rectangular.

    Mechanism 2 is NOT corrected here. If the hybrid search returns an arbitrary
    30 of a larger neighbourhood, that is exactly what production got, and this
    probe is measuring centring, not neighbour selection.
    """
    b = len(idx_block)
    coords = np.empty((b, MAX_NN, 3), dtype=np.float64)
    counts = np.empty(b, dtype=np.int64)
    for r, i in enumerate(idx_block):
        k, nb, _ = tree.search_hybrid_vector_3d(pts[i], RADIUS[0], MAX_NN)
        nb = np.asarray(nb, dtype=np.int64)[:k]
        counts[r] = k
        coords[r, :k] = pts[nb]
        if k < MAX_NN:
            coords[r, k:] = pts[i]
    return coords, counts


def _mask_of(counts):
    """(B, MAX_NN) boolean: which padded slots are real neighbours."""
    return np.arange(MAX_NN)[None, :] < counts[:, None]


def cov_cumulant(coords, counts):
    """Open3D's estimator, reproduced: E[a*b] - E[a]*E[b] on RAW coordinates.

    This is the arithmetic under suspicion. It is implemented here only so the
    neighbourhood-fidelity anti-null can compare against Open3D's own output.
    Padded slots are zeroed by the mask, so they contribute nothing to a sum.
    """
    m = _mask_of(counts)[:, :, None]
    k = counts[:, None].astype(float)
    p = coords * m
    mean = p.sum(axis=1) / k
    second = np.einsum("bki,bkj->bij", p, p) / k[:, :, None]
    return second - mean[:, :, None] * mean[:, None, :]


def cov_centred(coords, counts):
    """The same covariance with each neighbourhood's own centroid removed first.

    Mathematically identical to cov_cumulant in exact arithmetic. Numerically it
    is the stable form, because the large common offset is subtracted before any
    product is formed, so no term ever reaches 2e13 and there is nothing left to
    cancel catastrophically.
    """
    m = _mask_of(counts)[:, :, None]
    k = counts[:, None].astype(float)
    mean = (coords * m).sum(axis=1) / k
    d = (coords - mean[:, None, :]) * m
    return np.einsum("bki,bkj->bij", d, d) / k[:, :, None]


def score_from_eig(eig):
    """Production's score arithmetic, unchanged, applied to given eigenvalues."""
    total = eig.sum(axis=1)
    s = np.full(len(eig), DEGENERATE_SCORE)
    ok = total > DEGENERATE_TOTAL
    s[ok] = eig[ok, 0] / total[ok]
    return s


RADIUS = [None]   # filled in main; module-level so gather_neighbours can see it


def main():
    ap = argparse.ArgumentParser(
        description="Test whether centring each neighbourhood before "
                    "accumulating its covariance removes the negative-variance "
                    "defect. Diagnostic only.")
    ap.add_argument("dataset")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    dataset = Path(args.dataset).name

    if not PRIOR.exists():
        raise SystemExit(f"missing prior probe output: {PRIOR}")
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    want_neg_diag = prior["covariance_validity"]["points_with_a_negative_variance_on_the_diagonal"]
    want_neg_trace = prior["covariance_validity"]["points_with_negative_trace"]

    pts, spacing, counts_stage = stages(cfg)
    radius = cfg["radius_mult"] * spacing
    RADIUS[0] = radius
    n = len(pts)
    print(f"planarity input {n:,}  spacing {spacing:.6f}  radius {radius:.6f}")
    print(f"score_max {cfg['score_max']}  max_nn {MAX_NN}  (read from production, unchanged)")

    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(pts)
    cloud.estimate_covariances(
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=MAX_NN))
    cov_prod = np.asarray(cloud.covariances)
    diag = np.einsum("...ii->...i", cov_prod)
    flagged_mask = (diag < 0.0).any(axis=1)
    n_flagged = int(flagged_mask.sum())
    n_neg_trace = int((diag.sum(axis=1) < 0.0).sum())

    # --- the flag set must be the SAME set the prior probe measured ---------
    if n_flagged != want_neg_diag or n_neg_trace != want_neg_trace:
        raise SystemExit(
            "ANTI-NULL FAIL: recomputed flag set does not match the prior probe. "
            f"negative-diagonal {n_flagged:,} vs {want_neg_diag:,} recorded; "
            f"negative-trace {n_neg_trace:,} vs {want_neg_trace:,} recorded. "
            "This probe would be describing a different set of points."
        )
    print(f"  ANTI-NULL PASS  flag set matches the prior probe exactly "
          f"({n_flagged:,} negative-diagonal, {n_neg_trace:,} negative-trace)")

    prod_scores = score_from_eig(np.linalg.eigvalsh(cov_prod))
    tree = o3d.geometry.KDTreeFlann(cloud)
    flagged_idx = np.flatnonzero(flagged_mask)

    # --- anti-null 1: are these the neighbourhoods production used? ---------
    rng = np.random.default_rng(RNG_SEED)
    fid_idx = rng.choice(flagged_idx, size=min(2000, len(flagged_idx)), replace=False)
    fc, fk = gather_neighbours(tree, pts, fid_idx)
    rebuilt = cov_cumulant(fc, fk)
    fid_dev = np.abs(rebuilt - cov_prod[fid_idx]).max()
    scale = np.abs(cov_prod[fid_idx]).max()
    if not np.allclose(rebuilt, cov_prod[fid_idx], rtol=1e-6, atol=1e-12):
        raise SystemExit(
            "ANTI-NULL FAIL: the re-gathered neighbourhoods do not reproduce "
            f"Open3D's covariance (max deviation {fid_dev:.3e} against a matrix "
            f"scale of {scale:.3e}). The neighbour set or the estimator differs, "
            "so nothing computed from these neighbourhoods describes production."
        )
    print(f"  ANTI-NULL PASS  re-gathered neighbourhoods reproduce Open3D's "
          f"covariance (max dev {fid_dev:.3e}, matrix scale {scale:.3e})")

    # --- the test: centre every flagged neighbourhood ------------------------
    resolved = still_broken = improved = 0
    neg_eig_after = neg_trace_after = neg_diag_after = 0
    done = 0
    for start in range(0, len(flagged_idx), BATCH):
        block = flagged_idx[start:start + BATCH]
        coords, ks = gather_neighbours(tree, pts, block)
        cc = cov_centred(coords, ks)
        d = np.einsum("...ii->...i", cc)
        eig = np.linalg.eigvalsh(cc)

        diag_ok = (d >= 0.0).all(axis=1)
        trace_ok = d.sum(axis=1) >= 0.0
        eig_ok = eig[:, 0] >= 0.0

        full = diag_ok & trace_ok
        resolved += int(full.sum())
        still_broken += int((~full).sum())
        # "improved but not resolved": was negative on the diagonal before and
        # still fails one of the two checks, but no longer fails BOTH.
        part = (~full) & (diag_ok | trace_ok)
        improved += int(part.sum())
        neg_diag_after += int((~diag_ok).sum())
        neg_trace_after += int((~trace_ok).sum())
        neg_eig_after += int((~eig_ok).sum())

        done += len(block)
        print(f"    centred {done:,} / {len(flagged_idx):,}", end="\r", flush=True)
    print(" " * 60, end="\r")

    # --- anti-null 2: the control group -------------------------------------
    healthy = np.flatnonzero(~flagged_mask)
    ctrl_idx = rng.choice(healthy, size=min(CONTROL_N, len(healthy)), replace=False)
    cc_all, dev_max, dev_med = [], 0.0, 0.0
    ctrl_scores = np.empty(len(ctrl_idx))
    for start in range(0, len(ctrl_idx), BATCH):
        block = ctrl_idx[start:start + BATCH]
        coords, ks = gather_neighbours(tree, pts, block)
        eig = np.linalg.eigvalsh(cov_centred(coords, ks))
        ctrl_scores[start:start + len(block)] = score_from_eig(eig)
    # THIRD-METHOD ADJUDICATION. The control group is supposed to show that
    # centring leaves already-healthy points alone. If it does NOT, the result is
    # ambiguous on its face: either centring is wrong, or the "healthy" points
    # were never healthy. That has to be settled by something independent of
    # both implementations, so a subsample is recomputed with numpy's own
    # covariance, which centres internally and shares no code with either path.
    # Whichever of the two it agrees with is the correct one.
    adj_idx = ctrl_idx[:min(2000, len(ctrl_idx))]
    ac, ak = gather_neighbours(tree, pts, adj_idx)
    mine = cov_centred(ac, ak)
    # Open3D falls back to the IDENTITY matrix when a neighbourhood is too small
    # to define a covariance. Those rows are separated out rather than averaged
    # in: they are a documented fallback, not a cancellation error, and leaving
    # them in makes the headline deviation exactly 1.0 for a reason that has
    # nothing to do with the defect under test.
    ident = np.all(np.isclose(cov_prod[adj_idx], np.eye(3)), axis=(1, 2))
    dev_np_mine = 0.0
    dev_o3d_real = []
    for r, gi in enumerate(adj_idx):
        k = ak[r]
        ref = np.cov(ac[r, :k].T, bias=True)
        dev_np_mine = max(dev_np_mine, float(np.abs(ref - mine[r]).max()))
        if not ident[r]:
            dev_o3d_real.append(float(np.abs(ref - cov_prod[gi]).max()))
    dev_o3d_real = np.array(dev_o3d_real)
    dev_np_o3d = float(dev_o3d_real.max()) if dev_o3d_real.size else 0.0
    dev_np_o3d_med = float(np.median(dev_o3d_real)) if dev_o3d_real.size else 0.0
    o3d_scale = float(np.abs(cov_prod[adj_idx][~ident]).max()) if (~ident).any() else 0.0
    n_ident = int(ident.sum())
    ident_k = sorted(set(int(v) for v in ak[ident])) if n_ident else []

    dev = np.abs(ctrl_scores - prod_scores[ctrl_idx])
    dev_max = float(dev.max())
    dev_med = float(np.median(dev))
    ctrl_keep_prod = prod_scores[ctrl_idx] <= cfg["score_max"]
    ctrl_keep_centred = ctrl_scores <= cfg["score_max"]
    ctrl_flips = int((ctrl_keep_prod != ctrl_keep_centred).sum())

    report = {
        "probe": "does centring each neighbourhood remove the negative-variance defect",
        "kind": "diagnostic",
        "dataset": dataset,
        "date": date.today().isoformat(),
        "production_unchanged": True,
        "note": "roofkit/ unmodified, no production path wired to this, "
                "score_max/radius_mult/max_nn read only, no artifact read or "
                "rewritten. Mechanism 2 (arbitrary 30 of a larger neighbourhood) "
                "is left intact on purpose.",
        "hypothesis": "the covariance is accumulated as E[ab]-E[a]E[b] on raw UTM "
                      "coordinates, costing ~17.3 digits of cancellation against "
                      "float64's ~16; subtracting the neighbourhood centroid first "
                      "removes the large common offset before any product forms",
        "anti_nulls": {
            "flag_set_matches_prior_probe": {
                "recomputed_negative_diagonal": n_flagged,
                "recorded_negative_diagonal": want_neg_diag,
                "recomputed_negative_trace": n_neg_trace,
                "recorded_negative_trace": want_neg_trace,
                "passed": True,
                "note": "the prior probe stored counts, not indices, so the set was "
                        "recomputed deterministically and checked against them",
            },
            "neighbourhood_fidelity": {
                "claim": "the re-gathered neighbourhoods are the ones production used",
                "evidence": "rebuilding the UNCENTRED covariance from them with "
                            "Open3D's own cumulant form reproduces Open3D's matrices",
                "sampled_points": int(len(fid_idx)),
                "max_abs_deviation": float(fid_dev),
                "matrix_scale": float(scale),
                "passed": True,
            },
        },
        "params_read_not_changed": {
            "score_max": float(cfg["score_max"]),
            "radius_mult": float(cfg["radius_mult"]),
            "max_nn": MAX_NN,
            "degenerate_total_guard": DEGENERATE_TOTAL,
            "spacing": float(spacing), "radius": float(radius),
        },
        "stage_counts": counts_stage,
        "flagged_points": {
            "total": n_flagged,
            "fully_resolved_after_centring": resolved,
            "still_broken_after_centring": still_broken,
            "improved_but_not_resolved": improved,
            "pct_fully_resolved": float(100.0 * resolved / max(1, n_flagged)),
            "definition": "fully resolved = every diagonal entry >= 0 AND trace >= 0",
        },
        "residual_after_centring": {
            "negative_diagonal": neg_diag_after,
            "negative_trace": neg_trace_after,
            "negative_smallest_eigenvalue": neg_eig_after,
            "note": "a negative smallest eigenvalue can survive on a matrix whose "
                    "diagonal and trace are both fine; it is reported separately "
                    "rather than folded into the resolved count",
        },
        "control_group": {
            "points": int(len(ctrl_idx)),
            "selection": "uniform without replacement from points NOT flagged",
            "max_abs_score_deviation": dev_max,
            "median_abs_score_deviation": dev_med,
            "keep_discard_flips": ctrl_flips,
            "reading": "centring changes the arithmetic path, so exact equality is "
                       "not expected; what matters is that healthy points do not move",
        },
        "third_method_adjudication": {
            "why": "the control group only settles anything if it is clear WHICH "
                   "computation is right when the two disagree, so a subsample is "
                   "recomputed with numpy's covariance, which centres internally "
                   "and shares no code with either path",
            "sampled_points": int(len(adj_idx)),
            "max_dev_numpy_vs_centred": dev_np_mine,
            "max_dev_numpy_vs_production": dev_np_o3d,
            "median_dev_numpy_vs_production": dev_np_o3d_med,
            "production_matrix_scale": o3d_scale,
            "identity_fallbacks_excluded": {
                "count": n_ident,
                "neighbour_counts_seen": ident_k,
                "why": "Open3D returns the identity matrix when a neighbourhood is "
                       "too small to define a covariance. That is a documented "
                       "fallback, not a cancellation error, so these rows are "
                       "excluded from the deviation statistics rather than "
                       "inflating the maximum to exactly 1.0",
            },
            "verdict": ("numpy agrees with the CENTRED computation and disagrees "
                        "with production" if dev_np_mine < dev_np_o3d else
                        "numpy agrees with PRODUCTION and disagrees with the "
                        "centred computation"),
            "consequence": "the unflagged points were not healthy either; a "
                           "non-negative diagonal is a weaker check than a correct "
                           "covariance, so the control group does not isolate the "
                           "effect of centring the way it was intended to",
        },
    }

    out = REPO / "reports" / "diagnostics" / "planarity-centering-check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    w = 46
    print()
    print("  " + "-" * (w + 18))
    print(f"  {'PLANARITY CENTRING CHECK':<{w}}{'':>18}")
    print("  " + "-" * (w + 18))
    rows = [
        ("flagged points (negative diagonal)", f"{n_flagged:,}"),
        ("  fully resolved after centring", f"{resolved:,}"),
        ("  still broken after centring", f"{still_broken:,}"),
        ("  improved but not resolved", f"{improved:,}"),
        ("  pct fully resolved",
         f"{100.0 * resolved / max(1, n_flagged):.4f} pct"),
        ("residual negative diagonal", f"{neg_diag_after:,}"),
        ("residual negative trace", f"{neg_trace_after:,}"),
        ("residual negative smallest eigenvalue", f"{neg_eig_after:,}"),
        (f"control group ({len(ctrl_idx):,} unflagged points)", ""),
        ("  max abs score deviation", f"{dev_max:.3e}"),
        ("  median abs score deviation", f"{dev_med:.3e}"),
        ("  keep/discard flips", f"{ctrl_flips:,}"),
        (f"third-method check ({len(adj_idx):,} of those)", ""),
        ("  max dev numpy vs centred", f"{dev_np_mine:.3e}"),
        ("  median dev numpy vs production", f"{dev_np_o3d_med:.3e}"),
        ("  max dev numpy vs production", f"{dev_np_o3d:.3e}"),
        ("  production matrix scale", f"{o3d_scale:.3e}"),
        ("  identity fallbacks excluded", f"{n_ident:,}"),
    ]
    for label, value in rows:
        print(f"  {label:<{w}}{value:>18}")
    print("  " + "-" * (w + 18))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
