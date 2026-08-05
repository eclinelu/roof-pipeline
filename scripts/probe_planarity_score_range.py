# The planarity score leaves its documented range, and the points that leave it
# are KEPT (2026-08-05).
#
#   .venv/Scripts/python.exe -u scripts/probe_planarity_score_range.py C:/odm/datasets/big_house
#
# WHAT PROMPTED THIS. Fitting the ultra cloud into memory needed the planarity
# filter run in spatial tiles instead of in one call. Tiling is exactly
# equivalent on paper: the score is a local operator, and each tile carried a
# halo of exactly the search radius, so every core point sees the neighbourhood
# it would have seen in the whole cloud. The equivalence check FAILED anyway --
# 2,378 of 2,000,000 points changed score and 368 changed the keep/discard
# decision, 236 of those while both scores sat inside the documented range.
#
# Chasing that failure into planarity_scores found the cause, and the cause is
# not the tiling.
#
# TWO SEPARATE FINDINGS, both about the EXISTING production path.
#
# 1. THE SCORE LEAVES ITS DOCUMENTED RANGE ON MOST OF THE ROOF.
#    planarity_scores documents "0 (perfect plane) to 1/3 (isotropic confetti)".
#    The score is eig[0] / sum(eig) from eigvalsh on each point's 3x3
#    covariance. When the sampled neighbourhood is nearly exactly coplanar the
#    covariance is numerically rank-deficient, eigvalsh returns a SMALL NEGATIVE
#    smallest eigenvalue, and the ratio becomes a large negative number. The
#    existing guard only rejects `total <= 1e-12`, which does not catch a
#    negative numerator over a small positive denominator.
#
#    A negative score passes `score <= score_max` unconditionally. So the
#    filter's admission of these points is not a graded judgement about
#    flatness, it is an arithmetic accident that happens to point the same way.
#
# 2. THE SCORE DEPENDS ON NEIGHBOUR ENUMERATION ORDER.
#    estimate_covariances is called with KDTreeSearchParamHybrid(radius, max_nn),
#    max_nn=30, while the median neighbourhood inside the radius holds far more
#    than 30 points. The covariance is therefore built from an arbitrary 30 of
#    them, chosen by KD-tree traversal order. Reorder the points -- which is all
#    tiling does -- and a different 30 are chosen, and the score moves. This is
#    the R5 shape (a raster's origin phase is a parameter) in a different
#    disguise: an implementation detail is deciding the answer.
#
# WHY THIS MATTERS FOR THE ULTRA PASS SPECIFICALLY, AND NOT ONLY IN GENERAL.
# Both findings are sensitive to POINT DENSITY, which is the single variable an
# ultra-against-medium pass exists to isolate. Denser data means more candidates
# inside the radius, so a smaller and more arbitrary fraction of the
# neighbourhood is sampled, and a flatter sampled subset, which is what drives
# the covariance rank-deficient. A medium-vs-ultra facet diff would therefore
# report this defect's response to density MIXED WITH the roof's, with no way to
# separate them after the fact. That is why this probe exists before the pass
# rather than after it.
#
# NOTHING IS FIXED HERE AND NO PARAMETER IS CHANGED. score_max, radius_mult and
# max_nn are the production configuration and changing them is Emmett's call;
# the same standing treatment as the min_pitch defect. This probe only measures.
#
# ANTI-NULL (standing rule R4). The probe asserts, from something known
# INDEPENDENTLY of anything it reports, that it is running the real production
# path: the stage 0-4 chain it drives must reproduce the committed roof.npy BIT
# FOR BIT. If that fails, every number below describes some other pipeline and
# the probe aborts rather than publishing them.
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import open3d as o3d

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                        # noqa: E402
from roofkit.io import load_xyz_rgb                           # noqa: E402
from roofkit.crop import crop_box                             # noqa: E402
from roofkit.isolate import (height_cutoff, color_filter,     # noqa: E402
                             planarity_scores, planarity_scores_blocked)
from roofkit.segment import clean_outliers                    # noqa: E402
from roofkit.stats import median_nn_spacing                   # noqa: E402

REPO = Path(__file__).resolve().parents[1]
MAX_NN = 30          # the value planarity_scores defaults to; not changed here
TILE_PROBE_N = 2_000_000   # subset size for the order-dependence probe
TILE_PROBE_BLOCK = 250_000  # forces 8 tiles over that subset


def stages(cfg):
    """The production stage 0-4 chain, run exactly as isolate_roof.py runs it."""
    points, colors = load_xyz_rgb(cfg["cloud_path"])
    n_raw = len(points)
    points, m = crop_box(points, cfg["crop_min"], cfg["crop_max"]); colors = colors[m]
    n_crop = len(points)
    points, m = height_cutoff(points, cfg["z_min"]); colors = colors[m]
    n_height = len(points)
    points, m = color_filter(points, colors, exg_max=cfg["exg_max"]); colors = colors[m]
    n_color = len(points)
    del colors
    spacing = median_nn_spacing(points)
    return points, spacing, dict(raw=n_raw, after_crop=n_crop,
                                 after_height=n_height, after_color=n_color)


def main():
    ap = argparse.ArgumentParser(
        description="Measure the planarity score's range and its dependence on "
                    "neighbour enumeration order. Measurement only.")
    ap.add_argument("dataset")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    dataset = Path(args.dataset).name

    pts, spacing, counts = stages(cfg)
    radius = cfg["radius_mult"] * spacing
    print(f"planarity input {len(pts):,}  spacing {spacing:.6f}  radius {radius:.6f}")

    scores = planarity_scores(pts, radius)
    kept = scores <= cfg["score_max"]
    negative = scores < 0.0
    above = scores > 1.0 / 3.0
    out_of_range = negative | above

    # --- the anti-null, run BEFORE anything is written -------------------
    roof = clean_outliers(pts[kept])
    ref_path = Path(cfg["roof_path"])
    if not ref_path.exists():
        raise SystemExit(f"ANTI-NULL UNRUNNABLE: no {ref_path} to check against")
    ref = np.load(ref_path)
    if not np.array_equal(roof, ref):
        raise SystemExit(
            "ANTI-NULL FAIL: this chain does not reproduce roof.npy "
            f"({len(roof):,} points vs {len(ref):,} on disk). The numbers this "
            "probe would report describe some other pipeline."
        )
    print(f"  ANTI-NULL PASS  reproduced roof.npy bit for bit ({len(ref):,} points)")

    # --- how full is a neighbourhood, against the max_nn cap -------------
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(pts)
    tree = o3d.geometry.KDTreeFlann(cloud)
    rng = np.random.default_rng(20260805)
    sample = rng.choice(len(pts), size=min(5000, len(pts)), replace=False)
    nbr = np.array([tree.search_radius_vector_3d(pts[i], radius)[0] for i in sample])

    # --- order dependence, shown by reordering and nothing else ----------
    sub = pts[:TILE_PROBE_N]
    sub_r = cfg["radius_mult"] * median_nn_spacing(sub)
    whole_s = planarity_scores(sub, sub_r)
    tiled_s = planarity_scores_blocked(sub, sub_r, max_block=TILE_PROBE_BLOCK)
    kw, kt = whole_s <= cfg["score_max"], tiled_s <= cfg["score_max"]
    flips = int((kw != kt).sum())
    in_range_both = (whole_s >= 0) & (whole_s <= 1 / 3) & (tiled_s >= 0) & (tiled_s <= 1 / 3)
    flips_in_range = int(((kw != kt) & in_range_both).sum())

    report = {
        "probe": "planarity score range and order dependence",
        "dataset": dataset,
        "date": date.today().isoformat(),
        "fixed": False,
        "note": "MEASUREMENT ONLY. No parameter changed. score_max, radius_mult "
                "and max_nn remain the production configuration.",
        "anti_null": {
            "claim": "the chain driven here IS the production stage 0-4 path",
            "evidence": "clean_outliers(planarity_filter(...)) == roof.npy, bit for bit",
            "passed": True,
            "roof_npy_points": int(len(ref)),
        },
        "stage_counts": counts,
        "params": {"radius_mult": cfg["radius_mult"], "score_max": cfg["score_max"],
                   "max_nn": MAX_NN, "spacing": float(spacing), "radius": float(radius)},
        "documented_range": [0.0, 1.0 / 3.0],
        "observed_range": [float(scores.min()), float(scores.max())],
        "counts": {
            "planarity_input": int(len(pts)),
            "kept_by_filter": int(kept.sum()),
            "negative_score": int(negative.sum()),
            "above_one_third": int(above.sum()),
            "out_of_documented_range": int(out_of_range.sum()),
            "kept_and_out_of_range": int((kept & out_of_range).sum()),
        },
        "fractions_pct": {
            "input_out_of_range": float(100.0 * out_of_range.mean()),
            "of_kept_points_admitted_out_of_range":
                float(100.0 * (kept & out_of_range).sum() / max(1, kept.sum())),
        },
        "neighbourhood_vs_max_nn": {
            "sampled_points": int(len(nbr)),
            "median_neighbours_in_radius": int(np.median(nbr)),
            "p90_neighbours_in_radius": int(np.percentile(nbr, 90)),
            "max_nn_cap": MAX_NN,
            "pct_sampled_over_cap": float(100.0 * (nbr > MAX_NN).mean()),
            "reading": "where this exceeds the cap the covariance is built from "
                       "an arbitrary subset chosen by KD-tree traversal order",
        },
        "order_dependence": {
            "how": "same points, same radius, reordered by spatial tiling with a "
                   "halo of exactly the search radius; tiling cannot change a "
                   "local operator's support, only the enumeration order",
            "subset_points": int(TILE_PROBE_N),
            "tiles": int(np.ceil(TILE_PROBE_N / TILE_PROBE_BLOCK)),
            "score_changed": int((whole_s != tiled_s).sum()),
            "keep_decision_flips": flips,
            "keep_decision_flips_with_both_scores_in_range": flips_in_range,
            "reading": "non-zero flips mean the roof membership depends on point "
                       "enumeration order, not only on geometry",
        },
        "why_it_blocks_the_ultra_pass":
            "both effects are driven by neighbour count inside the radius, which "
            "is a function of point density -- the one variable a medium-vs-ultra "
            "pass exists to isolate. A facet diff across the two clouds would mix "
            "this defect's density response with the roof's, inseparably.",
    }

    out = REPO / "reports" / dataset / f"planarity-score-range-{report['date']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"  observed score range      {scores.min():.4g} .. {scores.max():.4g}")
    print(f"  out of documented range   {out_of_range.sum():,} "
          f"({100.0 * out_of_range.mean():.2f} pct of input)")
    print(f"  of the points KEPT        {report['fractions_pct']['of_kept_points_admitted_out_of_range']:.2f} pct "
          f"were admitted on an out-of-range score")
    print(f"  neighbours in radius      median {int(np.median(nbr))} against a max_nn cap of {MAX_NN}")
    print(f"  keep flips from reorder   {flips} ({flips_in_range} with both scores in range)")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
