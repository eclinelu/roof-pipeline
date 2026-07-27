# Task 6A: is the recovery stage reproducible, and what makes it so?
#
#   .venv/Scripts/python.exe -u scripts/probe_determinism.py C:/odm/datasets/big_house
#   .venv/Scripts/python.exe -u scripts/probe_determinism.py C:/odm/datasets/big_house --threads 1
#
# Writes reports/big_house/determinism-<date>[-1thread].json   (standing rule R2)
#
# ---------------------------------------------------------------------------
# WHAT IS BEING TESTED
#
# Measured on 2026-07-25: Open3D 0.19's segment_plane returns DIFFERENT planes
# for an identical seed on identical points. On a 1.5M-point facet it never
# varied; on a 664-point facet it produced three different answers in 25 reps.
# Between two full runs the facet count came out 26 and then 25.
#
# Three candidate responses, tested independently so their effects do not get
# confused with each other:
#
#   FLOOR       A hard minimum facet size, applied even inside residual blobs.
#               Hypothesis: the unstable facets are exactly the sub-floor ones,
#               so excluding them removes the instability. This treats the
#               symptom's CAUSE (fits too weakly constrained to be repeatable)
#               rather than the library.
#
#   1 THREAD    Open3D's RANSAC is parallel. A parallel reduction that picks
#               the best plane across threads has no defined tie-break order,
#               which produces exactly this signature: irrelevant when one
#               plane dominates, decisive when several nearly tie on a small
#               set. Open3D exposes no thread argument, so this is pinned with
#               OMP_NUM_THREADS BEFORE open3d is imported, which is why it
#               needs a separate process (hence the --threads flag).
#
#   PROB 1.0    segment_plane defaults to probability=0.99999999, an ADAPTIVE
#               EARLY STOP: it quits as soon as its running estimate says it
#               has probably found the best plane. That estimate depends on the
#               best inlier count found so far, so under threading the stopping
#               ITERATION itself varies. probability=1.0 forces the full 1000
#               iterations every time.
#
# The test is the honest one: reset the seed to the SAME value before every
# repetition and change nothing else. If results still differ, the seed does
# not control the outcome.
# ---------------------------------------------------------------------------
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

# THREAD PINNING MUST HAPPEN BEFORE open3d IS IMPORTED. OpenMP reads these
# once at library load; setting them afterwards does nothing. argparse runs
# later, so the flag is read straight off sys.argv here.
_THREADS = None
if "--threads" in sys.argv:
    _THREADS = sys.argv[sys.argv.index("--threads") + 1]
    for _v in ("OMP_NUM_THREADS", "OPEN3D_CPU_RENDERING_NUM_THREADS",
               "MKL_NUM_THREADS", "OMP_THREAD_LIMIT"):
        os.environ[_v] = _THREADS

import numpy as np                                            # noqa: E402
import open3d as o3d                                          # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                        # noqa: E402
from recon_common import discover_facets                      # noqa: E402
from roofkit.segment import level_cloud, assign_to_planes     # noqa: E402
from roofkit.measure import up_from_tilt                      # noqa: E402
from roofkit import coverage as cov                           # noqa: E402

COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/big_house"

# ---------------------------------------------------------------------------
# THE PROPOSED HARD FLOOR. Stated, not tuned per site.
#
# Derived from the observed size distribution of the 2026-07-23 facets, which
# has a wide EMPTY BAND in it:
#
#   points : 664  (facet 23, unstable: 3 outcomes under one seed)
#            then NOTHING until
#            10,614 (facet 24, stable)
#   net    : 0.010 cu^2 (facet 23)   0.019 (facet 25, vanished entirely)
#            then NOTHING until
#            0.378 cu^2 (facet 22, a real dormer face)
#
# Both floors are placed INSIDE those empty bands, so the exact value does not
# change which facets are kept. That is the point: a threshold sitting in a gap
# is insensitive, whereas one sitting in a dense region is a tuned magic number.
#
# SCALE BEHAVIOUR, stated honestly:
#   MIN_POINTS is a COUNT. It does not depend on scale, but it does depend on
#   cloud DENSITY, so it transfers between clouds of similar ground sampling
#   distance and not between wildly different ones.
#   MIN_AREA_CU2 is an AREA in cloud units, so it IS scale-dependent and must
#   not be copied to a cloud at a different scale. The transferable form is the
#   same floor expressed in units of point spacing squared, which is what
#   min_area_in_spacing_sq() returns; that number is what should move between
#   datasets.
# ---------------------------------------------------------------------------
MIN_POINTS = 2000
MIN_AREA_CU2 = 0.10


def min_area_in_spacing_sq(spacing):
    """The area floor as a multiple of spacing^2, which is the scale-free way
    to carry it to another cloud."""
    return MIN_AREA_CU2 / (spacing ** 2)


def summarize(reps):
    """Turn a list of per-rep facet lists into stability numbers.

    Reported: whether the COUNT is identical in every rep (the gate Emmett set
    before any further work), and the per-facet pitch SPREAD (max minus min
    across reps). Spread is index-matched, which is only meaningful when the
    count is stable, so it is reported as null when it is not."""
    counts = sorted({len(r) for r in reps})
    stable = (len(counts) == 1)
    out = dict(reps=len(reps), counts_observed=counts,
               count_stable=bool(stable))
    if stable and reps:
        n = counts[0]
        spreads, worst = [], 0.0
        for k in range(n):
            p = [r[k]["pitch"] for r in reps]
            s = max(p) - min(p)
            worst = max(worst, s)
            spreads.append(dict(facet_index=k, pitch_spread_deg=round(s, 5),
                                min_pitch=round(min(p), 4),
                                max_pitch=round(max(p), 4),
                                n_points_min=min(r[k]["n"] for r in reps),
                                n_points_max=max(r[k]["n"] for r in reps)))
        # a facet set is only truly identical if the point counts match too
        exact = all(all(reps[0][k]["n"] == r[k]["n"] for k in range(n))
                    for r in reps)
        out.update(worst_pitch_spread_deg=round(worst, 5),
                   bit_identical_point_counts=bool(exact),
                   per_facet=spreads)
    else:
        out.update(worst_pitch_spread_deg=None, per_facet=None,
                   note="count varies across reps, so index-matched spread is "
                        "undefined")
    return out


def run_variant(points, blobs, dist, band, spacing, bar, reps, alpha_mult,
                use_floor, probability, label, g):
    """Run recovery `reps` times, re-seeding identically before each."""
    got = []
    for _ in range(reps):
        o3d.utility.random.seed(0)          # SAME seed every repetition
        new = cov.recover_facets(
            points, blobs, None, dist, band, spacing, bar, grid=g,
            min_points_hard=(MIN_POINTS if use_floor else None),
            min_area_hard=(MIN_AREA_CU2 if use_floor else None),
            alpha_mult=alpha_mult, probability=probability)
        got.append([dict(pitch=float(f["pitch"]), n=int(len(f["points"])))
                    for f in new])
    s = summarize(got)
    s.update(variant=label, floor_applied=bool(use_floor),
             probability=probability,
             min_points=(MIN_POINTS if use_floor else None),
             min_area_cu2=(MIN_AREA_CU2 if use_floor else None))
    print(f"  {label:<28} counts {s['counts_observed']}  "
          f"stable={s['count_stable']}  worst spread="
          f"{s['worst_pitch_spread_deg']}")
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--reps", type=int, default=25)
    ap.add_argument("--threads", default=None,
                    help="pin OMP threads (read before open3d import)")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"open3d {o3d.__version__}; OMP_NUM_THREADS="
          f"{os.environ.get('OMP_NUM_THREADS', '(unset, library default)')}")

    points = np.load(cfg["roof_path"])
    if cfg["level_tilt_deg"] is not None:
        points = level_cloud(points, up_from_tilt(cfg["level_tilt_deg"],
                                                  cfg["level_uphill_az_deg"]))

    # Main facets: fitted on 300k-1.5M points and already measured stable to
    # 0.0004 deg, so they are derived ONCE and held fixed. This isolates the
    # variable under test to the recovery stage.
    facets, band, spacing = discover_facets(points, cfg)
    bar, _ = cov.calibrate_quality_bar(facets, spacing)
    cell = COVERAGE_CELL_MULT * spacing
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    print(f"  main facets {len(facets)} (held fixed), blobs {len(blobs)}, "
          f"band {band:.6f}, spacing {spacing:.6f}, bar {bar:.3f}")
    print(f"  floor proposal: >= {MIN_POINTS} points AND >= {MIN_AREA_CU2} cu^2 "
          f"(= {min_area_in_spacing_sq(spacing):.0f} x spacing^2)")
    print()

    variants = [
        ("baseline (no floor, default prob)", False, 0.99999999),
        ("hard floor only", True, 0.99999999),
        ("probability=1.0 only", False, 1.0),
        ("floor + probability=1.0", True, 1.0),
    ]
    results = []
    for label, use_floor, prob in variants:
        results.append(run_variant(points, blobs, dist, band, spacing, bar,
                                   args.reps, cfg["alpha_mult"],
                                   use_floor, prob, label, g))

    tag = f"-{_THREADS}thread" if _THREADS else ""
    doc = dict(
        task="6A determinism probe",
        dataset="big_house", date=str(date.today()),
        open3d_version=o3d.__version__,
        omp_num_threads=os.environ.get("OMP_NUM_THREADS", "unset"),
        threads_pinned=bool(_THREADS),
        method=("re-seed to 0 immediately before each repetition, identical "
                "input points, identical parameters; main facets held fixed "
                "because they were already measured reproducible to 0.0004 deg"),
        reps=args.reps,
        floor=dict(min_points=MIN_POINTS, min_area_cu2=MIN_AREA_CU2,
                   min_area_in_spacing_sq=round(min_area_in_spacing_sq(spacing), 1),
                   spacing_cu=round(float(spacing), 6),
                   rationale=("both values sit inside an EMPTY band of the "
                              "observed distribution (points: 664 then nothing "
                              "until 10,614; net area: 0.019 then nothing until "
                              "0.378), so the threshold is insensitive to its "
                              "exact value"),
                   scale_note=("min_points is a count: density-dependent, not "
                               "scale-dependent. min_area_cu2 IS scale-dependent; "
                               "carry min_area_in_spacing_sq to another cloud "
                               "instead.")),
        inputs=dict(main_facets=len(facets), blobs=len(blobs),
                    band_cu=round(float(band), 6),
                    quality_bar=round(float(bar), 4)),
        variants=results)
    p = OUT / f"determinism-{date.today()}{tag}.json"
    p.write_text(json.dumps(doc, indent=2, default=float))
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
