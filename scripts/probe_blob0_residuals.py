# DIAGNOSTIC C: is blob 0 one plane or two?
#
#   .venv/Scripts/python.exe -u scripts/probe_blob0_residuals.py C:/odm/datasets/big_house
#
# Writes (standing rule R2):
#   reports/big_house/blob0-residuals-<date>.json
#   reports/big_house/blob0-residuals-<date>.png        maps + histogram
#   reports/big_house/blob0-residuals-spectrum-<date>.png
#
# SIDE ARTIFACT ONLY. Nothing is adopted. No threshold, no comparison operator
# and no fit is changed anywhere in roofkit. canonical-2026-07-26-r2 remains
# canonical and published coverage remains 88.40 percent. Fitting two planes
# BELOW is a measurement inside this probe, not a split implemented in the
# pipeline.
#
# ---------------------------------------------------------------------------
# THE QUESTION
#
# Blob 0 is confirmed real roof by physical inspection (2026-07-27). Its single
# best-fit plane misses the quality bar by 0.0069 percent. Before anything
# upstream is touched, the cheapest hypothesis has to be tested: blob 0 may be
# TWO surfaces, and a single plane forced across both is charged for the gap
# between them.
#
# An RMS cannot answer that. RMS is one number and every one of the four
# candidate explanations below can produce the same one. The DISTRIBUTION and
# the SPATIAL ARRANGEMENT of the residuals can tell them apart:
#
#   gaussian, zero-mean, magnitude tracking local point density
#       -> capture noise. The metric is confounded and the bar is measuring
#          capture quality, not planarity.
#   bimodal, or spatially banded into contiguous same-sign regions
#       -> two planes. Split it; the bar is never touched.
#   systematic and smoothly correlated with position
#       -> genuinely not planar (a curved or sagging surface). The bar was
#          right and blob 0 is not a plane.
#   periodic at a fixed spacing
#       -> material structure: standing seam, corrugation, tile courses. The
#          surface IS a plane with relief on it.
#
# WHY THE PLANE HAS TO BE THE PRODUCTION PLANE
#
# Re-peeling blob 0 outside recover_facets returns a DIFFERENT plane, because
# Open3D's RANSAC draws from one global stream (decision
# 2026-07-27-reassignment-pass-contamination). So the plane is captured from
# inside the production call by wrapping cov.facet_quality, and its normal is
# then compared BIT FOR BIT against the normal recorded in
# quality-bar-tie-2026-07-27.json. If that check fails, this probe is describing
# some other plane and every number in it is void.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import spearmanr, pearsonr, skew, kurtosis

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                            # noqa: E402
from canonical import leveled_points                              # noqa: E402
from recon_common import discover_facets                          # noqa: E402
from roofkit.stats import median_nn_spacing                       # noqa: E402
from roofkit.measure import facet_area, tilt_degrees              # noqa: E402
from roofkit.segment import fit_plane_svd                         # noqa: E402
from roofkit import coverage as cov                               # noqa: E402

REPO = Path(__file__).resolve().parents[1]
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
MIN_AREA_POINTS_EQUIV = 3704
MAIN_MIN_PITCH = 5.0
RECOVERY_MIN_PITCH_DIAG = 1.0
CANONICAL_STAMP = "2026-07-26-r2"
MAP_CELL_MULT = 4.0        # map cells are 4x the coverage cell, so a cell holds
                           # tens of points and a per-cell mean is meaningful


def fhex(x):
    return float(x).hex()


def gauss_em_1d(x, iters=400, tol=1e-10, seed=0):
    """Two-component 1D Gaussian mixture by EM. Written out rather than pulled
    from sklearn to keep the probe's dependencies to what the project already
    has, and because at 1D with two components EM is a dozen lines.

    Returns (weights, means, sigmas, loglik). Initialised by splitting at the
    median, which is the natural guess if the data really is two lobes."""
    rng = np.random.default_rng(seed)
    lo, hi = x < np.median(x), x >= np.median(x)
    w = np.array([lo.mean(), hi.mean()])
    mu = np.array([x[lo].mean(), x[hi].mean()])
    sd = np.array([max(x[lo].std(), 1e-9), max(x[hi].std(), 1e-9)])
    prev = -np.inf
    for _ in range(iters):
        # E step: responsibility of each component for each point
        p = np.column_stack([
            w[k] * np.exp(-0.5 * ((x - mu[k]) / sd[k]) ** 2) /
            (sd[k] * np.sqrt(2 * np.pi)) for k in range(2)])
        tot = p.sum(axis=1) + 1e-300
        ll = float(np.log(tot).sum())
        r = p / tot[:, None]
        # M step
        nk = r.sum(axis=0) + 1e-300
        w = nk / len(x)
        mu = (r * x[:, None]).sum(axis=0) / nk
        sd = np.sqrt((r * (x[:, None] - mu) ** 2).sum(axis=0) / nk)
        sd = np.maximum(sd, 1e-9)
        if abs(ll - prev) < tol * abs(ll):
            break
        prev = ll
    return w, mu, sd, ll


def bic(loglik, n_params, n):
    return float(n_params * np.log(n) - 2.0 * loglik)


def two_plane_fit(pts, init_sign, iters=50):
    """Lloyd iteration for TWO planes: assign each point to the nearer plane,
    refit each plane by SVD, repeat. Initialised by the sign of the residual
    against the single-plane fit, which is the split the two-plane hypothesis
    predicts.

    This is a MEASUREMENT, not a pipeline change: it answers 'would two planes
    fit this patch materially better than one', and nothing in roofkit is
    touched. Returns (labels, normals, centroids)."""
    lab = (init_sign > 0).astype(int)
    for _ in range(iters):
        ns, cs = [], []
        for k in (0, 1):
            m = lab == k
            if m.sum() < 3:
                return None
            c = pts[m].mean(axis=0)
            n = fit_plane_svd(pts[m])
            ns.append(n / np.linalg.norm(n))
            cs.append(c)
        d = np.column_stack([np.abs((pts - cs[k]) @ ns[k]) for k in (0, 1)])
        new = d.argmin(axis=1)
        if (new == lab).all():
            break
        lab = new
    return lab, ns, cs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    name = Path(args.dataset).name
    out = REPO / "reports" / name
    checks = []

    points = leveled_points(cfg)
    spacing = median_nn_spacing(points)

    # --- the production prefix, in the production order --------------------
    # discover_facets reseeds Open3D's global RANSAC stream on its first line,
    # so the recovery pass that follows starts where the production run's does.
    _, band, s_full = discover_facets(points, cfg, probability=1.0,
                                      spacing=spacing, min_pitch=10.0)
    facets, _, _ = discover_facets(points, cfg, probability=1.0,
                                   spacing=spacing, min_pitch=MAIN_MIN_PITCH)
    bar, ratios = cov.calibrate_quality_bar(facets, s_full)
    cell = COVERAGE_CELL_MULT * s_full
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    b0 = blobs[0]

    min_area = MIN_AREA_POINTS_EQUIV * spacing ** 2
    d_ = []
    for f in facets:
        p_ = np.asarray(f["points"], float)
        s_ff = float(np.median(cov._nn(p_)))
        d_.append(len(p_) * spacing ** 2 /
                  max(float(facet_area(p_, f["normal"],
                                       cfg["alpha_mult"] * s_ff)), 1e-12))
    min_points = int(round(MIN_AREA_POINTS_EQUIV * float(np.median(d_))))

    # --- capture the production plane where it is computed -----------------
    captured = []
    _orig = cov.facet_quality

    def _spy(pts, normal, sp):
        q, n = _orig(pts, normal, sp)
        captured.append(dict(n=len(pts), q=float(q), points=pts,
                             normal=np.asarray(n, float).copy()))
        return q, n

    cov.facet_quality = _spy
    try:
        log = []
        cov.recover_facets(points, [b0], None, dist, band, s_full, bar,
                           alpha_mult=cfg["alpha_mult"], probability=1.0,
                           min_pitch=RECOVERY_MIN_PITCH_DIAG,
                           min_points_hard=min_points, min_area_hard=min_area,
                           log=log, grid=g)
    finally:
        cov.facet_quality = _orig
    logged = log[0]["planes"][0]
    shot = next(c for c in captured if c["n"] == logged["n"])

    P = np.asarray(shot["points"], float)            # the 162,938 inliers
    n_hat = shot["normal"] / np.linalg.norm(shot["normal"])
    q_prod = shot["q"]

    # Cross-check against the run this probe claims to extend.
    tie_path = out / f"quality-bar-tie-{args.stamp}.json"
    tie = json.loads(tie_path.read_text()) if tie_path.exists() else None
    same_normal = (tie is not None and
                   [fhex(v) for v in n_hat] == tie["candidate"]["normal_hex"])
    checks.append(dict(
        check="the plane analysed here IS the plane recover_facets rejected",
        passed=bool(len(P) == 162938 and same_normal),
        n_points=int(len(P)),
        normal_hex=[fhex(v) for v in n_hat],
        expected_normal_hex=(tie["candidate"]["normal_hex"] if tie else None),
        quality=repr(float(q_prod)),
        bar=repr(float(bar)),
        why="a re-peel returns a different plane (2026-07-27-reassignment-pass-"
            "contamination), so the identity of the plane has to be checked, "
            "not assumed"))

    # ======================================================================
    # SIGNED RESIDUALS
    # ======================================================================
    # facet_quality reports RMS over the TRIMMED subset, centred on that
    # subset's mean. The residuals below use the same origin, so a residual of
    # zero here is the same surface the quality number was measured against.
    # All 162,938 points are included; the trimmed subset is reported alongside
    # so the size of the discarded tail is visible.
    from roofkit.segment import fit_plane_trimmed
    _, keep = fit_plane_trimmed(P, trim_mult=3.0)
    origin = P[keep].mean(axis=0)
    r = (P - origin) @ n_hat                          # SIGNED, +n_hat is up
    r_keep = r[keep]

    # in-plane coordinates, so residuals can be mapped over the patch
    helper = np.array([1.0, 0, 0]) if abs(n_hat[0]) < 0.9 else np.array([0, 1.0, 0])
    u_ax = np.cross(n_hat, helper); u_ax /= np.linalg.norm(u_ax)
    v_ax = np.cross(n_hat, u_ax)
    U = (P - origin) @ u_ax
    V = (P - origin) @ v_ax

    in_per_cu = 40.4541
    sc = out / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])

    hist_counts, hist_edges = np.histogram(r, bins=200)
    dist_stats = dict(
        n=int(len(r)), n_trimmed_kept=int(keep.sum()),
        trim_discarded_pct=round(100.0 * (1 - keep.mean()), 3),
        mean=float(r.mean()), median=float(np.median(r)), std=float(r.std()),
        mean_in=float(r.mean() * in_per_cu), std_in=float(r.std() * in_per_cu),
        p1=float(np.percentile(r, 1)), p99=float(np.percentile(r, 99)),
        min=float(r.min()), max=float(r.max()),
        skew=float(skew(r)), excess_kurtosis=float(kurtosis(r)),
        rms_all=float(np.sqrt((r ** 2).mean())),
        rms_trimmed=float(np.sqrt((r_keep ** 2).mean())),
        rms_trimmed_over_spacing=float(np.sqrt((r_keep ** 2).mean()) / s_full),
        quality_reported_by_pipeline=float(q_prod),
        gaussian_expectation="skew 0, excess kurtosis 0. A heavy tail reads "
                             "positive kurtosis; two lobes read negative.")

    # ---- bimodality --------------------------------------------------------
    # Three independent readings, because no single one is conclusive.
    n_r = len(r)
    sk, ek = float(skew(r)), float(kurtosis(r))
    bc = ((sk ** 2 + 1.0) /
          (ek + 3.0 + 3.0 * (n_r - 1) ** 2 / ((n_r - 2) * (n_r - 3))))
    sub = r if n_r <= 200000 else r[np.random.default_rng(0).choice(n_r, 200000,
                                                                    replace=False)]
    w2, mu2, sd2, ll2 = gauss_em_1d(sub)
    ll1 = float(np.sum(-0.5 * ((sub - sub.mean()) / sub.std()) ** 2 -
                       np.log(sub.std() * np.sqrt(2 * np.pi))))
    bic1, bic2 = bic(ll1, 2, len(sub)), bic(ll2, 5, len(sub))
    ashman_d = float(np.sqrt(2) * abs(mu2[0] - mu2[1]) /
                     np.sqrt(sd2[0] ** 2 + sd2[1] ** 2))
    bimodality = dict(
        bimodality_coefficient=float(bc),
        bimodality_coefficient_reading="BC > 0.555 (the value for a uniform "
                                       "distribution) is the usual flag; a "
                                       "Gaussian sits near 0.333",
        two_component_mixture=dict(
            weights=[float(x) for x in w2],
            means=[float(x) for x in mu2],
            means_in=[float(x * in_per_cu) for x in mu2],
            sigmas=[float(x) for x in sd2],
            separation_ashman_D=ashman_d,
            ashman_reading="D > 2 is the conventional threshold for two "
                           "RESOLVABLE lobes. Below it the mixture is fitting "
                           "one lobe with two overlapping Gaussians, which it "
                           "can always do.",
            bic_one_component=bic1, bic_two_component=bic2,
            bic_favours=("two" if bic2 < bic1 else "one"),
            bic_reading="BIC always improves with more parameters on 100k+ "
                        "points, so a BIC win alone is not evidence. Read it "
                        "together with Ashman's D and the spatial map."),
        note="a mixture fit measures the SHAPE of the histogram. Two planes "
             "would also have to show up as two CONTIGUOUS same-sign regions "
             "in the spatial map, which is the test that actually "
             "discriminates.")

    # ---- local density, and whether residual magnitude tracks it -----------
    tree = cKDTree(P)
    kd, _ = tree.query(P, k=9)          # self + 8 neighbours
    local_spacing = kd[:, 1:].mean(axis=1)          # mean distance to 8 nn
    rng = np.random.default_rng(0)
    s_idx = rng.choice(len(P), min(50000, len(P)), replace=False)
    rho_s, p_s = spearmanr(local_spacing[s_idx], np.abs(r[s_idx]))
    rho_p, p_p = pearsonr(local_spacing[s_idx], np.abs(r[s_idx]))
    density = dict(
        method="mean distance to the 8 nearest neighbours, per point. Larger "
               "means sparser. Correlated against |residual| on a 50,000-point "
               "sample.",
        local_spacing_cu=dict(
            p5=float(np.percentile(local_spacing, 5)),
            median=float(np.median(local_spacing)),
            p95=float(np.percentile(local_spacing, 95)),
            median_in=float(np.median(local_spacing) * in_per_cu)),
        cloud_median_spacing_cu=float(s_full),
        spearman_rho=float(rho_s), spearman_p=float(p_s),
        pearson_r=float(rho_p), pearson_p=float(p_p),
        reading="a strong POSITIVE correlation means the residual is largest "
                "where the cloud is thinnest, which is the signature of "
                "capture noise rather than shape. Near zero means the "
                "roughness is a property of the surface, not of the capture.")

    # ---- spatial maps ------------------------------------------------------
    mcell = MAP_CELL_MULT * cell
    ui = ((U - U.min()) / mcell).astype(np.int64)
    vi = ((V - V.min()) / mcell).astype(np.int64)
    nu, nv = ui.max() + 1, vi.max() + 1
    flat = ui * nv + vi
    cnt = np.bincount(flat, minlength=nu * nv).astype(float)
    ssum = np.bincount(flat, weights=r, minlength=nu * nv)
    asum = np.bincount(flat, weights=np.abs(r), minlength=nu * nv)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_map = np.where(cnt > 0, ssum / np.maximum(cnt, 1), np.nan).reshape(nu, nv)
        abs_map = np.where(cnt > 0, asum / np.maximum(cnt, 1), np.nan).reshape(nu, nv)
    cnt_map = cnt.reshape(nu, nv)
    occ = cnt_map >= 5
    # Does the mean-residual field organise into contiguous same-sign regions?
    from scipy.ndimage import label as ndlabel
    pos = occ & (mean_map > 0); neg = occ & (mean_map < 0)
    _, n_pos = ndlabel(pos); _, n_neg = ndlabel(neg)
    lp, _ = ndlabel(pos); ln, _ = ndlabel(neg)
    big_pos = int(np.bincount(lp.ravel())[1:].max()) if n_pos else 0
    big_neg = int(np.bincount(ln.ravel())[1:].max()) if n_neg else 0
    # linear trend of the residual across the patch (a tilt the fit did not take)
    A = np.column_stack([U, V, np.ones(len(U))])
    coef, *_ = np.linalg.lstsq(A, r, rcond=None)
    pred = A @ coef
    r2_lin = float(1.0 - ((r - pred) ** 2).sum() / ((r - r.mean()) ** 2).sum())
    # correlation between per-cell |residual| and per-cell density
    cm, am = cnt_map[occ], abs_map[occ]
    rho_cell, p_cell = spearmanr(cm, am)
    spatial = dict(
        map_cell_cu=float(mcell), map_cell_in=float(mcell * in_per_cu),
        grid=[int(nu), int(nv)], occupied_cells=int(occ.sum()),
        sign_regions=dict(
            n_positive_regions=int(n_pos), n_negative_regions=int(n_neg),
            largest_positive_region_cells=big_pos,
            largest_negative_region_cells=big_neg,
            largest_positive_pct_of_positive=round(
                100.0 * big_pos / max(int(pos.sum()), 1), 2),
            largest_negative_pct_of_negative=round(
                100.0 * big_neg / max(int(neg.sum()), 1), 2),
            reading="TWO PLANES would give ~1 large positive region and ~1 "
                    "large negative region, each holding most of its sign's "
                    "cells, meeting along a line. Thousands of small regions of "
                    "both signs, each a few cells, is speckle: noise, not "
                    "geometry."),
        linear_trend=dict(
            slope_u_per_cu=float(coef[0]), slope_v_per_cu=float(coef[1]),
            r_squared=r2_lin,
            reading="a plane fit removes the linear trend from its own trimmed "
                    "subset, so a large R^2 here would mean the untrimmed "
                    "points carry a tilt the trim discarded. Near zero means "
                    "there is no leftover tilt and the residual is not a "
                    "smooth ramp."),
        per_cell_density_vs_abs_residual=dict(
            spearman_rho=float(rho_cell), spearman_p=float(p_cell)),
        points_per_cell=dict(median=float(np.median(cm)),
                             p5=float(np.percentile(cm, 5)),
                             p95=float(np.percentile(cm, 95))))

    # ---- periodicity -------------------------------------------------------
    # 2D power spectrum of the mean-residual field. Empty cells are set to zero
    # AFTER removing the mean, so a gap contributes no power of its own; the
    # gaps still spread energy, so only a clearly dominant peak counts.
    field = np.where(np.isfinite(mean_map), mean_map, 0.0)
    field = field - field[occ].mean()
    field = field * occ                       # zero outside the patch
    F = np.fft.fftshift(np.abs(np.fft.fft2(field)) ** 2)
    fu = np.fft.fftshift(np.fft.fftfreq(nu, d=mcell))
    fv = np.fft.fftshift(np.fft.fftfreq(nv, d=mcell))
    FU, FV = np.meshgrid(fu, fv, indexing="ij")
    rad = np.sqrt(FU ** 2 + FV ** 2)
    dc = rad < (1.0 / (max(nu, nv) * mcell)) * 2
    Fm = F.copy(); Fm[dc] = 0.0
    k_peak = np.unravel_index(np.argmax(Fm), Fm.shape)
    f_peak = float(rad[k_peak])
    lam = float(1.0 / f_peak) if f_peak > 0 else float("inf")
    power_frac = float(Fm[k_peak] / max(Fm.sum(), 1e-300))
    # radial profile, for the plot and for a human to see whether there IS a peak
    nb = 60
    rb = np.linspace(0, rad.max(), nb + 1)
    which = np.clip(np.digitize(rad.ravel(), rb) - 1, 0, nb - 1)
    prof = np.bincount(which, weights=Fm.ravel(), minlength=nb)
    prof_n = np.bincount(which, minlength=nb)
    prof = prof / np.maximum(prof_n, 1)
    periodicity = dict(
        method="2D power spectrum of the per-cell mean signed residual.",
        map_cell_in=float(mcell * in_per_cu),
        nyquist_wavelength_in=float(2 * mcell * in_per_cu),
        dominant_wavelength_cu=lam,
        dominant_wavelength_in=float(lam * in_per_cu) if np.isfinite(lam) else None,
        dominant_peak_power_fraction=power_frac,
        reading="a real periodic structure shows as a sharp peak holding a "
                "large share of the non-DC power at one wavelength. A power "
                "fraction of a fraction of a percent, with a smooth radial "
                "profile, is broadband and means NO periodicity. Reference "
                "spacings: standing seam 12-24 in, corrugation about 2.67 in, "
                "shingle courses about 5 in.")

    # ---- edge profile ------------------------------------------------------
    # The global linear trend above is a whole-patch ramp and will miss a
    # feature confined to the boundary. An eave, a gutter line, a wall
    # junction or a tree-shadowed margin all live at the edge, so residual is
    # profiled against distance from the patch boundary directly.
    from scipy.ndimage import distance_transform_edt
    edt = distance_transform_edt(occ) * mcell
    pt_edge = edt[np.clip(ui, 0, nu - 1), np.clip(vi, 0, nv - 1)]
    ebins = np.array([0, 1, 2, 3, 4, 6, 8, 12, 16, 24, 1e9]) * mcell
    which_e = np.clip(np.digitize(pt_edge, ebins) - 1, 0, len(ebins) - 2)
    edge_rows = []
    for k in range(len(ebins) - 1):
        m = which_e == k
        if m.sum() < 50:
            continue
        edge_rows.append(dict(
            from_edge_in=round(float(ebins[k] * in_per_cu), 2),
            to_edge_in=(round(float(ebins[k + 1] * in_per_cu), 2)
                        if ebins[k + 1] < 1e8 else None),
            n_points=int(m.sum()),
            mean_signed_in=round(float(r[m].mean() * in_per_cu), 4),
            mean_abs_in=round(float(np.abs(r[m]).mean() * in_per_cu), 4),
            median_local_spacing_in=round(
                float(np.median(local_spacing[m]) * in_per_cu), 4)))
    interior = pt_edge > 4 * mcell
    # The interior's quality must go through facet_quality, the SAME function
    # that produced the bar. facet_quality trims at 3x the median scatter
    # before taking its RMS; comparing an untrimmed RMS against the bar would
    # compare two different statistics and make the interior look worse than
    # the whole patch, which is arithmetically impossible for the same
    # estimator. The untrimmed figure is reported alongside, labelled, so both
    # are visible and neither can be mistaken for the other.
    q_int, _ = cov.facet_quality(P[interior], n_hat, s_full)
    edge_profile = dict(
        method="distance from each point to the boundary of the occupied "
               "patch, from a Euclidean distance transform of the occupancy "
               "grid. Profiles the residual against depth into the patch.",
        rows=edge_rows,
        interior_only=dict(
            depth_threshold_in=round(float(4 * mcell * in_per_cu), 2),
            n_points=int(interior.sum()),
            pct_of_patch=round(100.0 * float(interior.mean()), 2),
            mean_signed_in=round(float(r[interior].mean() * in_per_cu), 4),
            std_in=round(float(r[interior].std() * in_per_cu), 4),
            skew=round(float(skew(r[interior])), 4),
            excess_kurtosis=round(float(kurtosis(r[interior])), 4),
            quality_trimmed=float(q_int),
            bar=float(bar),
            interior_alone_clears_bar=bool(q_int <= bar),
            comparable_because="computed by cov.facet_quality, the same "
                               "function and the same 3x trim that produced "
                               "the bar",
            untrimmed_rms_over_spacing_interior=round(
                float(np.sqrt((r[interior] ** 2).mean()) / s_full), 5),
            untrimmed_rms_over_spacing_whole_patch=round(
                float(np.sqrt((r ** 2).mean()) / s_full), 5),
            untrimmed_note="these two are NOT comparable to the bar. They are "
                           "here only to show that the interior is quieter "
                           "than the whole patch on a like-for-like untrimmed "
                           "basis."),
        reading="if the edge rows carry a large systematic offset that the "
                "interior does not, the single-plane fit is being charged for "
                "a boundary effect rather than for the surface. The interior "
                "-only quality says what the surface would score without it.")

    # ---- directional profiles ---------------------------------------------
    # The distance transform treats all four boundaries alike, so a feature on
    # ONE edge is diluted by the other three. The signed-residual map shows the
    # far side of the patch running strongly negative, which is exactly that
    # case, so the residual is also profiled along each in-plane axis.
    ax_world = dict(
        u_axis_world_xyz=[float(v) for v in u_ax],
        v_axis_world_xyz=[float(v) for v in v_ax],
        note="+u and +v are the in-plane axes of the fitted plane. Their world "
             "x/y components say how they lie on the map: +x is UTM easting, "
             "+y is UTM northing, to within the 1.083 deg level tilt.")

    def axis_profile(coord, nbins=40):
        lo, hi = float(coord.min()), float(coord.max())
        e = np.linspace(lo, hi, nbins + 1)
        w = np.clip(np.digitize(coord, e) - 1, 0, nbins - 1)
        rows = []
        for k in range(nbins):
            m = w == k
            if m.sum() < 50:
                continue
            rows.append(dict(
                center_in=round(float((e[k] + e[k + 1]) / 2 * in_per_cu), 2),
                n_points=int(m.sum()),
                mean_signed_in=round(float(r[m].mean() * in_per_cu), 4),
                mean_abs_in=round(float(np.abs(r[m]).mean() * in_per_cu), 4),
                median_spacing_in=round(
                    float(np.median(local_spacing[m]) * in_per_cu), 4)))
        return rows

    prof_u, prof_v = axis_profile(U), axis_profile(V)
    swing_u = (max(x["mean_signed_in"] for x in prof_u) -
               min(x["mean_signed_in"] for x in prof_u)) if prof_u else 0.0
    swing_v = (max(x["mean_signed_in"] for x in prof_v) -
               min(x["mean_signed_in"] for x in prof_v)) if prof_v else 0.0
    directional = dict(
        axes=ax_world, along_u=prof_u, along_v=prof_v,
        swing_u_in=round(float(swing_u), 4), swing_v_in=round(float(swing_v), 4),
        reading="the swing is the range of the per-bin mean signed residual "
                "along that axis. A swing much larger than the per-bin scatter, "
                "concentrated at one end, is a one-sided edge effect; a swing "
                "spread smoothly across the axis is curvature; a small swing is "
                "neither.")

    # ---- the two-plane test -----------------------------------------------
    tp = two_plane_fit(P, r)
    two_plane = dict(status="not attempted")
    if tp is not None:
        lab, ns, cs = tp
        parts = []
        for k in (0, 1):
            m = lab == k
            qk, nk = cov.facet_quality(P[m], ns[k], s_full)
            parts.append(dict(
                part=k, n_points=int(m.sum()),
                pct=round(100.0 * m.mean(), 2),
                pitch_deg=round(float(tilt_degrees(nk)), 4),
                quality=float(qk), bar=float(bar),
                clears_bar=bool(qk <= bar)))
        ang = float(np.degrees(np.arccos(np.clip(abs(ns[0] @ ns[1]), -1, 1))))
        d0 = np.abs((P - cs[0]) @ ns[0]); d1 = np.abs((P - cs[1]) @ ns[1])
        rms2 = float(np.sqrt((np.minimum(d0, d1) ** 2).mean()))
        # Perpendicular separation of the two planes at the patch centroid. Two
        # parallel sheets a real distance apart is a physical thing; two planes
        # at ~0 angle AND ~0 offset is one sheet cut in half.
        ctr = P.mean(axis=0)
        sep = float(abs(((ctr - cs[0]) @ ns[0]) - ((ctr - cs[1]) @ ns[1])))
        # SPATIAL SEGREGATION, the test that actually discriminates. Per map
        # cell, what fraction of its points went to part 0? Two real surfaces
        # give cells that are nearly pure (near 0 or near 1) and grouped into
        # a few large regions. Slicing one noisy sheet along its own residual
        # sign gives every cell close to the global mix, everywhere.
        p0 = np.bincount(flat, weights=(lab == 0).astype(float),
                         minlength=nu * nv)
        with np.errstate(invalid="ignore"):
            frac0 = np.where(cnt > 0, p0 / np.maximum(cnt, 1), np.nan)
        f_occ = frac0.reshape(nu, nv)[occ]
        pure = float(((f_occ > 0.9) | (f_occ < 0.1)).mean())
        maj = (frac0.reshape(nu, nv) > 0.5) & occ
        lm, n_maj = ndlabel(maj)
        biggest_maj = (int(np.bincount(lm.ravel())[1:].max())
                       if n_maj else 0)
        segregation = dict(
            global_part0_fraction=round(float((lab == 0).mean()), 4),
            per_cell_part0_fraction=dict(
                mean=round(float(np.nanmean(f_occ)), 4),
                std=round(float(np.nanstd(f_occ)), 4),
                pct_cells_nearly_pure=round(100.0 * pure, 2)),
            majority_part0_regions=int(n_maj),
            largest_majority_region_cells=biggest_maj,
            largest_majority_region_pct=round(
                100.0 * biggest_maj / max(int(maj.sum()), 1), 2),
            reading="two real surfaces give nearly-pure cells grouped into a "
                    "few large regions. A per-cell fraction sitting at the "
                    "global mix everywhere, in hundreds of small regions, "
                    "means the split is cutting one sheet along its own noise "
                    "and the RMS gain is free rather than physical.")
        two_plane = dict(
            status="fitted as a MEASUREMENT inside this probe; nothing in "
                   "roofkit changed and no split is implemented",
            method="Lloyd iteration: assign each point to the nearer plane, "
                   "refit each by SVD, repeat to convergence. Initialised by "
                   "the sign of the single-plane residual, which is the split "
                   "the two-plane hypothesis predicts.",
            parts=parts,
            angle_between_planes_deg=ang,
            separation_at_centroid_cu=sep,
            separation_at_centroid_in=float(sep * in_per_cu),
            spatial_segregation=segregation,
            rms_one_plane=float(np.sqrt((r ** 2).mean())),
            rms_two_planes=rms2,
            rms_improvement_pct=round(
                100.0 * (1 - rms2 / float(np.sqrt((r ** 2).mean()))), 2),
            reading="an RMS gain from a two-plane fit is NOT evidence on its "
                    "own: two planes always beat one, and on a noisy sheet the "
                    "gain comes from cutting the noise cloud into an upper and "
                    "a lower half. Two real facets must ALSO show (a) a "
                    "genuine angle between them, (b) or a real perpendicular "
                    "separation if they are parallel sheets, and (c) spatial "
                    "segregation: each part occupying its own contiguous "
                    "region rather than being interleaved cell by cell.")

    # ---- the verdict -------------------------------------------------------
    # Stated by rule against the numbers above, so the reasoning is auditable
    # rather than asserted.
    # Each of the four candidate patterns gets its own PASS/FAIL against a
    # stated threshold, rather than one label chosen by a chain of elifs. The
    # patterns are not mutually exclusive and the honest answer here is a
    # combination, so a single label would have to suppress part of the
    # evidence to be stated at all.
    seg = (two_plane.get("spatial_segregation") or {})
    pure_pct = (seg.get("per_cell_part0_fraction") or {}).get(
        "pct_cells_nearly_pure", 0.0)
    edge_gap = None
    if edge_rows:
        edge_gap = abs(edge_rows[0]["mean_signed_in"] -
                       edge_profile["interior_only"]["mean_signed_in"])

    signals = dict(
        bimodal=dict(
            verdict=bool(ashman_d > 2.0 and bc > 0.555),
            ashman_D=ashman_d, threshold_D=2.0,
            bimodality_coefficient=float(bc), threshold_BC=0.555,
            note="BC below 0.333 (the Gaussian value) means MORE sharply "
                 "unimodal than a Gaussian, not less."),
        two_planes=dict(
            verdict=bool(ang > 2.0 or
                         (sep * in_per_cu > 1.0 and pure_pct > 60.0)),
            angle_deg=ang, threshold_angle_deg=2.0,
            separation_in=float(sep * in_per_cu), threshold_separation_in=1.0,
            pct_cells_nearly_pure=pure_pct, threshold_pure_pct=60.0,
            note="the RMS gain is deliberately NOT part of this test; two "
                 "planes always beat one."),
        spatially_banded=dict(
            verdict=bool(
                spatial["sign_regions"]["largest_positive_pct_of_positive"] > 50
                and
                spatial["sign_regions"]["largest_negative_pct_of_negative"] > 50),
            largest_positive_pct=spatial["sign_regions"][
                "largest_positive_pct_of_positive"],
            largest_negative_pct=spatial["sign_regions"][
                "largest_negative_pct_of_negative"],
            threshold_pct=50.0),
        systematic_global_trend=dict(
            verdict=bool(r2_lin > 0.10), r_squared=r2_lin, threshold=0.10),
        systematic_edge_effect=dict(
            verdict=bool(edge_gap is not None and edge_gap > 0.25),
            edge_minus_interior_mean_in=edge_gap, threshold_in=0.25,
            n_points_in_outermost_band=(edge_rows[0]["n_points"]
                                        if edge_rows else 0),
            pct_of_patch_in_outermost_band=(
                round(100.0 * edge_rows[0]["n_points"] / len(r), 3)
                if edge_rows else 0.0),
            directional_swing_u_in=round(float(swing_u), 4),
            directional_swing_v_in=round(float(swing_v), 4),
            note="a boundary feature is invisible to the global linear trend, "
                 "so it is tested separately. Read the point count with it: an "
                 "effect confined to a few hundred of 162,938 points is real "
                 "but cannot move the patch RMS."),
        periodic=dict(
            verdict=bool(power_frac > 0.05),
            dominant_peak_power_fraction=power_frac, threshold=0.05,
            dominant_wavelength_in=(float(lam * in_per_cu)
                                    if np.isfinite(lam) else None)),
        density_tracking=dict(
            verdict=bool(abs(rho_s) > 0.20 and p_s < 1e-6),
            spearman_rho=float(rho_s), threshold_abs_rho=0.20),
        near_gaussian=dict(
            verdict=bool(abs(sk) < 0.5 and abs(ek) < 1.0),
            skew=sk, excess_kurtosis=ek,
            note="a heavy one-sided tail reads as negative skew plus positive "
                 "excess kurtosis: a clean core with a contaminating "
                 "population on one side, which is not the same thing as "
                 "Gaussian noise."))

    fired = [k for k, v in signals.items() if v["verdict"] and k != "near_gaussian"]
    verdict = dict(
        patterns_that_fired=fired,
        which_of_the_four=dict(
            capture_noise_metric_confounded=bool(
                signals["density_tracking"]["verdict"]),
            two_planes_split_it=bool(signals["two_planes"]["verdict"] or
                                     signals["bimodal"]["verdict"] or
                                     signals["spatially_banded"]["verdict"]),
            genuinely_not_planar=bool(
                signals["systematic_global_trend"]["verdict"] or
                signals["systematic_edge_effect"]["verdict"]),
            material_structure=bool(signals["periodic"]["verdict"])),
        note="these are not mutually exclusive and more than one can be true. "
             "A single label would have to suppress evidence to be stated, so "
             "none is offered here; the prose reading belongs in the decision "
             "entry, written by a human against these numbers.")

    doc = dict(
        task="DIAGNOSTIC C: is blob 0 one plane or two? Residual DISTRIBUTION "
             "and spatial arrangement, not just RMS.",
        dataset=name, date=args.stamp,
        status=("SIDE ARTIFACT ONLY. No threshold, no comparison operator and "
                "no fit changed anywhere in roofkit. canonical-2026-07-26-r2 "
                "remains canonical; published coverage remains 88.40 pct. The "
                "two-plane fit below is a measurement in this probe, not a "
                "split implemented in the pipeline."),
        context=("blob 0 confirmed REAL ROOF by physical inspection "
                 "2026-07-27: a lower, tree-occluded section of different "
                 "material on the east elevation of the south wing."),
        cross_checks=checks,
        scale_in_per_cu=in_per_cu,
        plane=dict(n_points=int(len(P)),
                   normal_hex=[fhex(v) for v in n_hat],
                   pitch_deg=round(float(tilt_degrees(n_hat)), 4),
                   quality=repr(float(q_prod)), bar=repr(float(bar)),
                   margin=repr(float(q_prod - bar))),
        residual_distribution=dist_stats,
        histogram=dict(bin_edges=[float(x) for x in hist_edges],
                       counts=[int(x) for x in hist_counts]),
        bimodality=bimodality,
        local_density=density,
        spatial=spatial,
        edge_profile=edge_profile,
        directional_profiles=directional,
        periodicity=periodicity,
        two_plane_test=two_plane,
        signals=signals,
        verdict=verdict,
        plots=[f"blob0-residuals-{args.stamp}.png",
               f"blob0-residuals-spectrum-{args.stamp}.png",
               f"blob0-residuals-profiles-{args.stamp}.png"])
    p = out / f"blob0-residuals-{args.stamp}.json"
    p.write_text(json.dumps(doc, indent=2, default=float))
    print(f"  wrote {p}")

    fired_txt = ("patterns that fired:\n  " + "\n  ".join(fired)
                 if fired else "no pattern fired")
    render(out, args.stamp, name, r, hist_edges, hist_counts, w2, mu2, sd2,
           mean_map, abs_map, cnt_map, occ, mcell, in_per_cu, prof, rb,
           local_spacing, s_idx, dist_stats, two_plane, fired_txt)
    render_profiles(out, args.stamp, name, prof_u, prof_v, edge_rows, u_ax,
                    v_ax, float(bar), edge_profile)

    print(f"\n  n = {len(P):,}   quality {q_prod!r}  bar {bar!r}")
    print(f"  signed residual: mean {r.mean():+.6f} cu ({r.mean()*in_per_cu:+.4f} in)"
          f"  std {r.std():.6f} cu ({r.std()*in_per_cu:.4f} in)")
    print(f"  skew {sk:+.4f}   excess kurtosis {ek:+.4f}   BC {bc:.4f}")
    print(f"  mixture: Ashman D {ashman_d:.3f}   BIC favours "
          f"{'two' if bic2 < bic1 else 'one'}")
    print(f"  sign regions: {n_pos:,} positive / {n_neg:,} negative; largest "
          f"holds {spatial['sign_regions']['largest_positive_pct_of_positive']}% "
          f"/ {spatial['sign_regions']['largest_negative_pct_of_negative']}%")
    print(f"  linear trend R^2 {r2_lin:.5f}")
    print(f"  density vs |residual|: spearman {rho_s:+.4f} (p={p_s:.2e})")
    print(f"  dominant wavelength {periodicity['dominant_wavelength_in']} in, "
          f"power fraction {power_frac:.5f}")
    print("\n  depth into the patch -> mean signed residual")
    for e in edge_rows:
        hi = "inf" if e["to_edge_in"] is None else f"{e['to_edge_in']:.1f}"
        print(f"    {e['from_edge_in']:>6.1f} to {hi:>6} in   "
              f"n={e['n_points']:>7,}   mean {e['mean_signed_in']:+.4f} in   "
              f"|r| {e['mean_abs_in']:.4f} in")
    ei = edge_profile["interior_only"]
    print(f"  interior only (>{ei['depth_threshold_in']} in deep, "
          f"{ei['pct_of_patch']}% of the patch): quality {ei['quality_trimmed']:.5f}"
          f" vs bar {ei['bar']:.5f} -> clears={ei['interior_alone_clears_bar']}")
    print(f"  directional swing: along u {swing_u:+.4f} in, along v "
          f"{swing_v:+.4f} in")
    if two_plane.get("parts"):
        for pt in two_plane["parts"]:
            print(f"  two-plane part {pt['part']}: {pt['n_points']:,} pts  "
                  f"quality {pt['quality']:.5f}  clears_bar={pt['clears_bar']}")
        sg = two_plane["spatial_segregation"]
        print(f"  two-plane angle {two_plane['angle_between_planes_deg']:.4f} "
              f"deg, separation {two_plane['separation_at_centroid_in']:.4f} in,"
              f" RMS gain {two_plane['rms_improvement_pct']}%")
        print(f"  segregation: {sg['per_cell_part0_fraction']['pct_cells_nearly_pure']}"
              f"% of cells nearly pure, {sg['majority_part0_regions']:,} "
              f"majority regions, largest holds "
              f"{sg['largest_majority_region_pct']}%")
    print("\n  PATTERNS THAT FIRED: " + (", ".join(fired) if fired else "none"))
    for k, v in signals.items():
        print(f"    {'YES' if v['verdict'] else ' no'}  {k}")
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check']}")


def render(out, stamp, name, r, edges, counts, w2, mu2, sd2, mean_map, abs_map,
           cnt_map, occ, mcell, in_per_cu, prof, rb, local_spacing, s_idx,
           dist_stats, two_plane, verdict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    r_in = r * in_per_cu
    fig, ax = plt.subplots(2, 3, figsize=(19, 11), dpi=130)

    # 1. histogram + single Gaussian + 2-component mixture
    a = ax[0, 0]
    c_in = (edges[:-1] + edges[1:]) / 2 * in_per_cu
    wdt = (edges[1] - edges[0]) * in_per_cu
    a.bar(c_in, counts, width=wdt, color="#6f8fb5", ec="none", label="residuals")
    xs = np.linspace(c_in.min(), c_in.max(), 800)
    tot = counts.sum() * wdt
    g1 = (tot / (r_in.std() * np.sqrt(2 * np.pi)) *
          np.exp(-0.5 * ((xs - r_in.mean()) / r_in.std()) ** 2))
    a.plot(xs, g1, color="#111111", lw=2, label="single Gaussian")
    for k in (0, 1):
        gk = (tot * w2[k] / (sd2[k] * in_per_cu * np.sqrt(2 * np.pi)) *
              np.exp(-0.5 * ((xs - mu2[k] * in_per_cu) / (sd2[k] * in_per_cu)) ** 2))
        a.plot(xs, gk, lw=1.6, ls="--",
               color=["#c1440e", "#1b7837"][k], label=f"mixture component {k}")
    a.set_xlabel("signed residual, inches"); a.set_ylabel("points")
    a.set_title("residual distribution")
    a.legend(fontsize=8)

    # 2. mean signed residual map (diverging)
    a = ax[0, 1]
    m = np.where(occ, mean_map, np.nan) * in_per_cu
    lim = float(np.nanpercentile(np.abs(m), 98))
    im = a.imshow(np.flipud(m.T), cmap="RdBu_r", vmin=-lim, vmax=lim,
                  interpolation="nearest")
    plt.colorbar(im, ax=a, label="mean signed residual, in")
    a.set_title(f"mean SIGNED residual per {mcell*in_per_cu:.1f} in cell\n"
                "two planes would show two large solid-colour regions")
    a.set_xticks([]); a.set_yticks([])

    # 3. |residual| map
    a = ax[0, 2]
    m2 = np.where(occ, abs_map, np.nan) * in_per_cu
    im = a.imshow(np.flipud(m2.T), cmap="magma",
                  vmax=float(np.nanpercentile(m2, 98)), interpolation="nearest")
    plt.colorbar(im, ax=a, label="mean |residual|, in")
    a.set_title("residual MAGNITUDE")
    a.set_xticks([]); a.set_yticks([])

    # 4. point density map
    a = ax[1, 0]
    m3 = np.where(occ, cnt_map, np.nan)
    im = a.imshow(np.flipud(m3.T), cmap="viridis",
                  vmax=float(np.nanpercentile(m3, 98)), interpolation="nearest")
    plt.colorbar(im, ax=a, label="points per cell")
    a.set_title("local point density\n(compare with the magnitude map)")
    a.set_xticks([]); a.set_yticks([])

    # 5. |residual| vs local spacing
    a = ax[1, 1]
    a.hexbin(local_spacing[s_idx] * in_per_cu, np.abs(r[s_idx]) * in_per_cu,
             gridsize=60, cmap="Blues", bins="log")
    a.set_xlabel("local point spacing (mean dist to 8 nn), in")
    a.set_ylabel("|residual|, in")
    a.set_title("does roughness track sparseness?")

    # 6. verdict panel
    a = ax[1, 2]; a.axis("off")
    tp = two_plane.get("parts")
    lines = [
        f"n = {dist_stats['n']:,} points",
        f"mean   {dist_stats['mean_in']:+.4f} in",
        f"std    {dist_stats['std_in']:.4f} in",
        f"skew   {dist_stats['skew']:+.4f}",
        f"excess kurtosis {dist_stats['excess_kurtosis']:+.4f}",
        f"quality {dist_stats['quality_reported_by_pipeline']:.5f}",
        "",
    ]
    if tp:
        lines.append("two-plane test:")
        for pt in tp:
            lines.append(f"  part {pt['part']}: {pt['n_points']:,} pts, "
                         f"q={pt['quality']:.4f}, clears={pt['clears_bar']}")
        lines.append(f"  angle {two_plane['angle_between_planes_deg']:.4f} deg")
        lines.append(f"  RMS gain {two_plane['rms_improvement_pct']}%")
        lines.append("")
    lines.append("VERDICT")
    a.text(0.02, 0.98, "\n".join(lines), va="top", ha="left", fontsize=11,
           family="monospace", transform=a.transAxes)
    a.text(0.02, 0.20, verdict, va="top", ha="left", fontsize=12,
           fontweight="bold", wrap=True, transform=a.transAxes, color="#8b0000")

    fig.suptitle(f"{name}: blob 0 residual structure against the production "
                 f"single-plane fit ({stamp})   SIDE ARTIFACT, nothing changed",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out / f"blob0-residuals-{stamp}.png")
    plt.close(fig)

    # spectrum figure
    fig, a = plt.subplots(figsize=(9, 5.5), dpi=140)
    ctr = (rb[:-1] + rb[1:]) / 2
    good = ctr > 0
    lam_in = 1.0 / ctr[good] * in_per_cu
    a.loglog(lam_in, prof[good], color="#12305c", lw=1.6)
    for ref, lbl in ((2.67, "corrugation ~2.67 in"), (5.0, "shingle course ~5 in"),
                     (12.0, "standing seam 12 in"), (24.0, "standing seam 24 in")):
        a.axvline(ref, color="#c1440e", ls="--", lw=1)
        a.text(ref, a.get_ylim()[1], lbl, rotation=90, fontsize=7,
               va="top", ha="right", color="#c1440e")
    a.axvline(2 * mcell * in_per_cu, color="#555555", ls=":", lw=1.2)
    a.text(2 * mcell * in_per_cu, a.get_ylim()[0], " Nyquist", fontsize=7,
           va="bottom", color="#555555")
    a.set_xlabel("wavelength, inches"); a.set_ylabel("mean power")
    a.set_title(f"{name}: blob 0 residual radial power spectrum ({stamp})\n"
                "a material structure would appear as a sharp peak")
    fig.tight_layout()
    fig.savefig(out / f"blob0-residuals-spectrum-{stamp}.png")
    plt.close(fig)


def render_profiles(out, stamp, name, prof_u, prof_v, edge_rows, u_ax, v_ax,
                    bar, edge_profile):
    """Mean signed residual along each in-plane axis, and against depth into
    the patch. These separate a ONE-SIDED edge effect (a step at one end) from
    CURVATURE (a smooth bow across the whole axis) from neither."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 3, figsize=(17, 5), dpi=140)
    for a, prof, lbl, axis in ((ax[0], prof_u, "u", u_ax),
                               (ax[1], prof_v, "v", v_ax)):
        x = [p["center_in"] for p in prof]
        y = [p["mean_signed_in"] for p in prof]
        a.axhline(0, color="#888888", lw=1)
        a.plot(x, y, "o-", color="#12305c", ms=4, lw=1.6)
        a.set_xlabel(f"position along {lbl}, inches from patch centroid")
        a.set_ylabel("mean signed residual, in")
        a.set_title(f"profile along {lbl}   (world xy of +{lbl}: "
                    f"{axis[0]:+.2f}, {axis[1]:+.2f})\n"
                    "a step at one end is an edge effect; a smooth bow is "
                    "curvature", fontsize=9)
        a.grid(alpha=0.25)

    a = ax[2]
    x = [e["from_edge_in"] for e in edge_rows]
    a.axhline(0, color="#888888", lw=1)
    a.plot(x, [e["mean_signed_in"] for e in edge_rows], "o-",
           color="#c1440e", ms=5, lw=1.8, label="mean signed")
    a.plot(x, [e["mean_abs_in"] for e in edge_rows], "s--",
           color="#1b7837", ms=5, lw=1.5, label="mean |residual|")
    a.set_xlabel("distance from the patch boundary, inches")
    a.set_ylabel("inches")
    ei = edge_profile["interior_only"]
    a.set_title(f"depth into the patch\ninterior-only quality "
                f"{ei['quality_trimmed']:.4f} vs bar {bar:.4f} -> "
                f"clears={ei['interior_alone_clears_bar']}", fontsize=9)
    a.legend(fontsize=8); a.grid(alpha=0.25)

    fig.suptitle(f"{name}: blob 0 residual, directional and depth profiles "
                 f"({stamp})   SIDE ARTIFACT, nothing changed", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out / f"blob0-residuals-profiles-{stamp}.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
