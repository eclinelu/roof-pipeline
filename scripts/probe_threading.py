# Task 6, T1 and T2: is probability=1.0 THREAD-INVARIANT?
#
#   # multithreaded (normal)
#   .venv/Scripts/python.exe -u scripts/probe_threading.py C:/odm/datasets/big_house \
#       --out reports/big_house/thread-mt.json
#   # single-threaded  (PowerShell: $env:OMP_NUM_THREADS = '1')
#   .venv/Scripts/python.exe -u scripts/probe_threading.py C:/odm/datasets/big_house \
#       --out reports/big_house/thread-1t.json
#   # compare
#   .venv/Scripts/python.exe scripts/probe_threading.py --compare \
#       reports/big_house/thread-mt.json reports/big_house/thread-1t.json \
#       --out reports/big_house/threading-<date>.json
#
# ---------------------------------------------------------------------------
# THE QUESTION THIS ANSWERS
#
# probability=1.0 removes the ADAPTIVE EARLY STOP, so every RANSAC candidate is
# always evaluated. That kills the timing dependence in WHEN the loop stops.
# It does NOT automatically kill a second possible timing dependence: WHICH
# candidate wins.
#
# RANSAC picks the candidate plane with the most inliers. Inlier count is an
# INTEGER. If two candidate planes tie on inlier count, the winner is whichever
# one the parallel reduction happened to compare first, which depends on thread
# finishing order and is not controlled by the seed. Exact integer ties are
# plausible, not merely theoretical, so "probability=1.0 fixed it" is a claim
# that needs measuring rather than assuming.
#
# THE TEST (Emmett's T1): run the full pipeline at probability=1.0 twice, once
# multithreaded and once with OMP_NUM_THREADS=1, and compare bit-for-bit on
#   - point counts, AND
#   - plane coefficients
# for EVERY candidate plane, not just the accepted facets and not just the
# facet count. If the two runs agree bit-for-bit, the candidate set does not
# depend on thread count, so no tie is being broken by timing on this cloud.
# If they differ, that is the tie case surfacing, and freezes need
# single-threading.
#
# WHY THE CANDIDATE LOG AND NOT JUST THE FACETS: the size floors reject some
# candidates. If we compared only accepted facets, a thread-dependent
# difference among REJECTED candidates would be invisible, and it would still
# matter, because a rejected plane has already had its points removed from the
# cloud and so changes what the next peel sees. recover_facets' log records
# every candidate with its exact integer point count and its full-precision
# normal, so diffing the log tests the whole candidate set.
#
# T2 is the wall-clock cost of each mode, which is the price of the fix.
# ---------------------------------------------------------------------------
import argparse
import hashlib
import json
import os
import platform
import sys
import time
from datetime import date
from pathlib import Path

# NOTE ON ORDERING: OMP_NUM_THREADS is read by the OpenMP runtime when it is
# first initialized, which happens at open3d import. It therefore CANNOT be set
# from inside this script; it must already be in the environment. We only READ
# it here, and record what we saw, so the output file states which mode it was.
_OMP = os.environ.get("OMP_NUM_THREADS")

import numpy as np                                              # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                           # noqa: E402
from recon_common import discover_facets                         # noqa: E402
from roofkit.stats import median_nn_spacing                      # noqa: E402
from roofkit.segment import level_cloud                          # noqa: E402
from roofkit.measure import up_from_tilt                         # noqa: E402
from roofkit import coverage as cov                              # noqa: E402

# Same constants the other 6-series probes use, so states are comparable.
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15

# The size floor, as it currently stands. MIN_AREA is already in transferable
# form (a count x spacing^2, so it rescales with any cloud). MIN_POINTS is a
# raw count and is NOT yet transferable; restating it is a separate step and
# does not affect this test, which only asks whether results depend on threads.
MIN_POINTS = 2000
MIN_AREA_POINTS_EQUIV = 3704          # MIN_AREA_CU2 = this x spacing^2

REPO = Path(__file__).resolve().parents[1]


def fhex(x):
    """A float as an EXACT round-trippable string. float.hex() writes the
    mantissa and exponent verbatim, so two values compare equal here only if
    they are the identical 64-bit double. Decimal formatting would hide a
    one-bit difference; this is what makes the comparison bit-for-bit."""
    return float(x).hex()


def arr_sha(a):
    """SHA-256 over an array's raw bytes. Order-SENSITIVE: reordering the same
    points changes this hash."""
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float64).tobytes()).hexdigest()[:16]


def member_sha(a):
    """SHA-256 over the array's rows sorted into a canonical order.
    Order-INSENSITIVE: this hash is equal when two runs selected the SAME SET
    of points, even if they returned them in a different order. Comparing both
    hashes separates 'different points' from 'same points, different order',
    which are two very different findings."""
    a = np.ascontiguousarray(a, dtype=np.float64)
    order = np.lexsort((a[:, 2], a[:, 1], a[:, 0]))
    return hashlib.sha256(a[order].tobytes()).hexdigest()[:16]


def facet_print(f):
    """A bit-exact fingerprint of one facet: its membership and its plane.

    The PLANE is recorded as the unit normal (a, b, c) plus d, where the plane
    is a*x + b*y + c*z + d = 0 and d = -(normal . centroid). Normal alone is
    not the plane; two parallel roof surfaces share a normal and differ only in
    d, so d must be compared too."""
    pts = np.asarray(f["points"], float)
    n = np.asarray(f["normal"], float)
    n = n / np.linalg.norm(n)
    c = pts.mean(axis=0)
    d = -float(n @ c)
    return dict(
        n_points=int(len(pts)),
        pitch=fhex(f["pitch"]),
        normal=[fhex(v) for v in n],
        plane_d=fhex(d),
        centroid=[fhex(v) for v in c],
        points_sha=arr_sha(pts),        # order-sensitive
        members_sha=member_sha(pts),    # order-insensitive
        # human-readable companions; never used for comparison
        _pitch_deg=round(float(f["pitch"]), 4),
    )


def run_once(dataset, out_path):
    """One full pipeline at probability=1.0. Writes a fingerprint file."""
    cfg = load_config(dataset)
    points = np.load(cfg["roof_path"])
    if cfg["level_tilt_deg"] is not None:
        points = level_cloud(points, up_from_tilt(cfg["level_tilt_deg"],
                                                 cfg["level_uphill_az_deg"]))

    t = {}
    t0 = time.perf_counter()
    spacing = median_nn_spacing(points)
    t["spacing_s"] = time.perf_counter() - t0

    min_area = MIN_AREA_POINTS_EQUIV * spacing ** 2

    t0 = time.perf_counter()
    facets, band, s_full = discover_facets(points, cfg, probability=1.0,
                                           spacing=spacing)
    t["discovery_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    bar, ratios = cov.calibrate_quality_bar(facets, s_full)
    cell = COVERAGE_CELL_MULT * s_full
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    t["coverage_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    log = []
    new = cov.recover_facets(points, blobs, None, dist, band, s_full, bar,
                             alpha_mult=cfg["alpha_mult"], probability=1.0,
                             min_points_hard=MIN_POINTS,
                             min_area_hard=min_area, log=log)
    t["recovery_s"] = time.perf_counter() - t0
    t["total_s"] = sum(t.values())

    doc = dict(
        task="6 T1/T2: thread-invariance of probability=1.0",
        dataset=Path(dataset).name, date=str(date.today()),
        mode=dict(omp_num_threads=_OMP, cpu_count=os.cpu_count(),
                  machine=platform.machine(), python=platform.python_version()),
        params=dict(probability=1.0, min_points_hard=MIN_POINTS,
                    min_area_hard=fhex(min_area),
                    min_area_points_equiv=MIN_AREA_POINTS_EQUIV,
                    coverage_cell_mult=COVERAGE_CELL_MULT,
                    min_blob_area=MIN_BLOB_AREA),
        # every scalar that feeds a downstream threshold, bit-exact
        scalars=dict(spacing=fhex(spacing), band=fhex(band),
                     cell=fhex(cell), quality_bar=fhex(bar),
                     n_points=int(len(points))),
        quality_ratios=[fhex(r) for r in ratios],
        counts=dict(n_main=len(facets), n_recovered=len(new),
                    n_total=len(facets) + len(new), n_blobs=len(blobs)),
        blobs=[dict(area_cu2=fhex(b["area_cu2"]), n_cells=int(len(b["cells"])))
               for b in blobs],
        main_facets=[facet_print(f) for f in facets],
        recovered_facets=[facet_print(f) for f in new],
        # THE CANDIDATE SET: every plane proposed inside every blob, kept or
        # rejected, with exact integer point count and full-precision normal.
        candidate_log=log,
        timing_s={k: round(v, 3) for k, v in t.items()},
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2, default=float))

    print(f"  OMP_NUM_THREADS={_OMP!r}  cpus={os.cpu_count()}")
    print(f"  spacing {spacing:.6f} cu   band {band:.6f} cu   bar {bar:.3f}x")
    print(f"  {len(facets)} main + {len(new)} recovered = {len(facets)+len(new)}"
          f"   ({len(blobs)} blobs, "
          f"{sum(len(e['planes']) for e in log)} candidates)")
    print(f"  timing: " + "  ".join(f"{k}={v:.2f}" for k, v in t.items()))
    print(f"  wrote {out_path}")
    return doc


# ---------------------------------------------------------------------------
# COMPARISON
# ---------------------------------------------------------------------------
def diff_facets(a, b, label):
    """Per-facet bit comparison. Returns (rows, n_diff)."""
    rows = []
    if len(a) != len(b):
        rows.append(dict(facet="COUNT", field="len",
                         a=len(a), b=len(b), same=False))
    for i in range(min(len(a), len(b))):
        for field in ("n_points", "pitch", "plane_d", "normal", "centroid",
                      "points_sha", "members_sha"):
            same = a[i][field] == b[i][field]
            if not same:
                rows.append(dict(facet=f"{label}{i}", field=field,
                                 a=a[i][field], b=b[i][field], same=False))
    return rows


def diff_candidates(la, lb):
    """Bit comparison of the candidate log, blob by blob, plane by plane."""
    rows = []
    if len(la) != len(lb):
        rows.append(dict(where="blob_count", a=len(la), b=len(lb), same=False))
    for i in range(min(len(la), len(lb))):
        ea, eb = la[i], lb[i]
        for field in ("blob", "n_candidate", "area_cu2", "skipped"):
            if ea.get(field) != eb.get(field):
                rows.append(dict(where=f"blob{i}.{field}", a=ea.get(field),
                                 b=eb.get(field), same=False))
        pa, pb = ea.get("planes", []), eb.get("planes", [])
        if len(pa) != len(pb):
            rows.append(dict(where=f"blob{i}.n_planes", a=len(pa), b=len(pb),
                             same=False))
        for j in range(min(len(pa), len(pb))):
            for field in ("n", "normal_hex", "kept", "rejected_by", "quality",
                          "pitch", "gross_cu2"):
                if pa[j].get(field) != pb[j].get(field):
                    rows.append(dict(where=f"blob{i}.plane{j}.{field}",
                                     a=pa[j].get(field), b=pb[j].get(field),
                                     same=False))
    return rows


def compare(pa, pb, out_path):
    A = json.loads(Path(pa).read_text())
    B = json.loads(Path(pb).read_text())

    rows = []
    for k, v in A["scalars"].items():
        if v != B["scalars"][k]:
            rows.append(dict(where=f"scalars.{k}", a=v, b=B["scalars"][k],
                             same=False))
    if A["quality_ratios"] != B["quality_ratios"]:
        rows.append(dict(where="quality_ratios", a=A["quality_ratios"],
                         b=B["quality_ratios"], same=False))
    if A["counts"] != B["counts"]:
        rows.append(dict(where="counts", a=A["counts"], b=B["counts"],
                         same=False))
    if A["blobs"] != B["blobs"]:
        rows.append(dict(where="blobs", a="(differs)", b="(differs)",
                         same=False))
    rows += diff_facets(A["main_facets"], B["main_facets"], "main")
    rows += diff_facets(A["recovered_facets"], B["recovered_facets"], "rec")
    cand_rows = diff_candidates(A["candidate_log"], B["candidate_log"])
    rows += cand_rows

    identical = len(rows) == 0
    n_cand = sum(len(e.get("planes", [])) for e in A["candidate_log"])

    ta, tb = A["timing_s"], B["timing_s"]
    speed = dict(
        multithreaded=(A if A["mode"]["omp_num_threads"] in (None, "")
                       else B)["mode"]["omp_num_threads"],
        a_label=f"OMP={A['mode']['omp_num_threads']}",
        b_label=f"OMP={B['mode']['omp_num_threads']}",
        a_timing=ta, b_timing=tb,
        total_ratio_b_over_a=round(tb["total_s"] / max(ta["total_s"], 1e-9), 3),
        discovery_ratio_b_over_a=round(
            tb["discovery_s"] / max(ta["discovery_s"], 1e-9), 3),
        recovery_ratio_b_over_a=round(
            tb["recovery_s"] / max(ta["recovery_s"], 1e-9), 3),
    )

    doc = dict(
        task="6 T1/T2 comparison: probability=1.0 multithreaded vs single-threaded",
        dataset=A["dataset"], date=str(date.today()),
        inputs=dict(a=Path(pa).name, b=Path(pb).name),
        modes=dict(a=A["mode"], b=B["mode"]),
        T1=dict(
            verdict="BIT-IDENTICAL" if identical else "DIFFERS",
            bit_identical=identical,
            n_differences=len(rows),
            compared=dict(
                main_facets=len(A["main_facets"]),
                recovered_facets=len(A["recovered_facets"]),
                candidate_planes=n_cand,
                fields_per_facet=["n_points", "pitch", "plane_d", "normal",
                                  "centroid", "points_sha", "members_sha"],
                fields_per_candidate=["n", "normal_hex", "kept", "rejected_by",
                                      "quality", "pitch", "gross_cu2"]),
            differences=rows[:200],
            candidate_set_identical=len(cand_rows) == 0,
        ),
        T2=speed,
        interpretation=(
            "T1 compares point counts AND plane coefficients bit-for-bit "
            "(exact hex floats), across every candidate plane including the "
            "ones the size floors reject, not merely the facet count. "
            "BIT-IDENTICAL means the candidate set does not depend on thread "
            "count on this cloud, i.e. no inlier-count tie is being broken by "
            "thread finishing order here. It is evidence of thread-invariance "
            "on big_house, NOT a proof that ties are impossible in general."),
    )
    Path(out_path).write_text(json.dumps(doc, indent=2, default=float))

    print(f"\n  T1 VERDICT: {doc['T1']['verdict']}")
    print(f"    compared {len(A['main_facets'])} main + "
          f"{len(A['recovered_facets'])} recovered facets on 7 fields each, "
          f"plus {n_cand} candidate planes")
    print(f"    candidate set identical: {doc['T1']['candidate_set_identical']}")
    if rows:
        print(f"    {len(rows)} DIFFERENCES, first 10:")
        for r in rows[:10]:
            print(f"      {r}")
    print(f"\n  T2 wall clock:")
    print(f"    {speed['a_label']:<12} total {ta['total_s']:>8.2f}s "
          f"(discovery {ta['discovery_s']:.2f}, recovery {ta['recovery_s']:.2f})")
    print(f"    {speed['b_label']:<12} total {tb['total_s']:>8.2f}s "
          f"(discovery {tb['discovery_s']:.2f}, recovery {tb['recovery_s']:.2f})")
    print(f"    b/a total ratio {speed['total_ratio_b_over_a']}x")
    print(f"\n  wrote {out_path}")
    return identical


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", nargs="?")
    ap.add_argument("--out", required=True)
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
    args = ap.parse_args()
    if args.compare:
        ok = compare(args.compare[0], args.compare[1], args.out)
        sys.exit(0 if ok else 2)   # exit 2 on DIFFERS, so the shell can gate
    if not args.dataset:
        ap.error("dataset is required unless --compare is given")
    run_once(args.dataset, args.out)


if __name__ == "__main__":
    main()
