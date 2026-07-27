# The CANONICAL FACET STATE, built once and written to disk (standing rule R1).
#
#   .venv/Scripts/python.exe -u scripts/canonical_state.py C:/odm/datasets/big_house
#
# Writes:
#   reports/big_house/canonical-<date>.json   plane coefficients + every scalar
#   reports/big_house/canonical-<date>.npz    per-facet inlier point INDICES
#
# ---------------------------------------------------------------------------
# WHY THIS FILE EXISTS
#
# The 2026-07-23 facet state is permanently unrecoverable: the run wrote summary
# rows only (pitch, gross, occluded, net), which is not enough to rebuild a
# plane, and the fit that produced it was nondeterministic, so it cannot be
# re-run either. Standing rule R1 came out of that: every run persists its plane
# coefficients AND its inlier point indices, so any run is replayable from its
# own output, regardless of whether the fit happens to be deterministic.
#
# Determinism (probability=1.0) and R1 are deliberately BELT AND BRACES. The
# determinism fix is a property of one library version and one set of arguments;
# a future Open3D could reintroduce the problem silently. Saved indices keep
# working either way, because replay then reads a file instead of re-running a
# fit.
#
# WHAT AN "INDEX" IS HERE. Every facet stores an array of row numbers into the
# LEVELED roof point array, i.e. np.load(roof.npy) put through level_cloud().
# Leveling is a rotation, which moves points but never reorders them, so row i
# is the same physical point before and after. points[idx] therefore rebuilds
# the facet exactly, with no fitting and no randomness.
#
# THE GUARD. Index bookkeeping is new code threaded through three functions, so
# it is not trusted, it is CHECKED: before writing anything, every facet's
# points[idx] is compared to the points the fit actually returned, bit for bit
# (np.array_equal on float64, not a tolerance). Any mismatch aborts. A state
# file whose indices point somewhere slightly wrong is worse than no file,
# because it looks authoritative.
# ---------------------------------------------------------------------------
import argparse
import hashlib
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                           # noqa: E402
from recon_common import discover_facets                         # noqa: E402
from roofkit.stats import median_nn_spacing                      # noqa: E402
from roofkit.segment import level_cloud                          # noqa: E402
from roofkit.measure import up_from_tilt, azimuth_degrees        # noqa: E402
from roofkit import coverage as cov                              # noqa: E402

# Same constants the whole 6-series uses, so every state is comparable.
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15

# THE SIZE FLOOR, as adopted 2026-07-25 and carried unchanged into this state.
# MIN_AREA is already in transferable form: a POINT-COUNT EQUIVALENT times
# spacing^2, so it rescales itself to any cloud's own point density. MIN_POINTS
# is still a raw count here, which is NOT transferable; restating it is a
# separate step (Task 6, step 4) that measures the band structure on THIS state
# before choosing a form. Recorded in the output so the state says which floor
# produced it.
MIN_POINTS = 2000
MIN_AREA_POINTS_EQUIV = 3704          # MIN_AREA_CU2 = this x spacing^2

REPO = Path(__file__).resolve().parents[1]


def fhex(x):
    """A float as an exact, round-trippable hex string. Two values compare
    equal here only if they are the identical 64-bit double, so a saved plane
    reloads as the same plane rather than a rounded one."""
    return float(x).hex()


def cloud_sha(points):
    """Fingerprint of the source cloud. Stored so a replay can prove it is
    indexing into the SAME points the state was built from; indices into a
    different cloud would silently select the wrong geometry."""
    return hashlib.sha256(
        np.ascontiguousarray(points, dtype=np.float64).tobytes()).hexdigest()


def plane_of(points, normal):
    """The facet's plane as (a, b, c, d) with a unit normal, where the plane is
    a*x + b*y + c*z + d = 0 and d = -(normal . centroid).

    The normal alone is NOT the plane: two parallel roof surfaces (a main slope
    and a dormer slope above it) share a normal and differ only in d. Both are
    saved."""
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    c = np.asarray(points, float).mean(axis=0)
    return n, float(-(n @ c)), c


def facet_record(k, f, kind, spacing):
    """One facet's full, replayable description."""
    pts = np.asarray(f["points"], float)
    n, d, c = plane_of(pts, f["normal"])
    q, _ = cov.facet_quality(pts, f["normal"], spacing)
    return dict(
        facet=k, kind=kind,
        blob=(int(f["blob"]) if "blob" in f else None),
        n_points=int(len(pts)),
        pitch_deg=round(float(f["pitch"]), 4),
        azimuth_deg=round(float(azimuth_degrees(f["normal"])), 4),
        quality_rms_over_spacing=round(float(q), 4),
        # exact, for replay
        plane_abcd_hex=[fhex(n[0]), fhex(n[1]), fhex(n[2]), fhex(d)],
        centroid_hex=[fhex(v) for v in c],
        # human-readable companions; never used to reload
        plane_abcd=[round(float(v), 9) for v in (*n, d)],
        centroid=[round(float(v), 4) for v in c],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    # Override the point floor. Used to test whether the transferable form of
    # MIN_POINTS (Task 6 step 4) would change the state at all; NOT a knob for
    # normal use, which is why it has no effect unless passed explicitly.
    ap.add_argument("--min-points", type=int, default=MIN_POINTS)
    args = ap.parse_args()
    min_points_hard = args.min_points
    cfg = load_config(args.dataset)
    out = REPO / "reports" / Path(args.dataset).name
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    raw = np.load(cfg["roof_path"])
    points = raw
    if cfg["level_tilt_deg"] is not None:
        points = level_cloud(raw, up_from_tilt(cfg["level_tilt_deg"],
                                               cfg["level_uphill_az_deg"]))
    spacing = median_nn_spacing(points)
    min_area = MIN_AREA_POINTS_EQUIV * spacing ** 2
    print(f"  {len(points):,} points   spacing {spacing:.6f} cu   "
          f"min_area {min_area:.5f} cu^2")

    # --- the pipeline, exactly as the recon runs it ------------------------
    facets, band, s_full = discover_facets(points, cfg, probability=1.0,
                                           spacing=spacing)
    bar, ratios = cov.calibrate_quality_bar(facets, s_full)
    cell = COVERAGE_CELL_MULT * s_full
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    log = []
    new = cov.recover_facets(points, blobs, None, dist, band, s_full, bar,
                             alpha_mult=cfg["alpha_mult"], probability=1.0,
                             min_points_hard=min_points_hard,
                             min_area_hard=min_area, log=log)
    allf = facets + new
    print(f"  {len(facets)} main + {len(new)} recovered = {len(allf)} facets "
          f"({len(blobs)} residual blobs)")

    # --- THE GUARD: do the saved indices really rebuild the facets? --------
    # Checked bit for bit on float64, not within a tolerance. Indices are a
    # lookup, so an exact match is the only acceptable answer; anything else
    # means the bookkeeping is wrong somewhere and the file must not be written.
    problems = []
    for k, f in enumerate(allf):
        if "idx" not in f:
            problems.append(f"facet {k}: no idx recorded")
            continue
        idx = np.asarray(f["idx"], dtype=np.int64)
        if len(idx) != len(f["points"]):
            problems.append(f"facet {k}: {len(idx)} indices vs "
                            f"{len(f['points'])} points")
            continue
        if not np.array_equal(points[idx], np.asarray(f["points"], float)):
            nbad = int((points[idx] != np.asarray(f["points"], float)).any(1).sum())
            problems.append(f"facet {k}: points[idx] differs on {nbad} rows")
    if problems:
        print("\n  INDEX CHECK FAILED, nothing written:")
        for p in problems:
            print("   ", p)
        sys.exit(2)
    print(f"  index check PASSED: points[idx] rebuilds all {len(allf)} facets "
          f"bit for bit")

    # --- write ------------------------------------------------------------
    npz = out / f"canonical-{args.stamp}.npz"
    np.savez_compressed(
        npz, **{f"facet_{k}": np.asarray(f["idx"], dtype=np.int64)
                for k, f in enumerate(allf)})

    rows = [facet_record(k, f, "main" if k < len(facets) else "recovered",
                         s_full) for k, f in enumerate(allf)]
    doc = dict(
        task="canonical facet state under probability=1.0 + size floor (R1)",
        dataset=Path(args.dataset).name, date=args.stamp,
        supersedes=dict(
            state="2026-07-23 26-facet state",
            status="SUPERSEDED, not corrected",
            reason="that state was one sample from a distribution: it was "
                   "produced by a nondeterministic fit and its geometry was "
                   "never written to disk, so it is permanently unrecoverable. "
                   "Its files stay on disk as the evidence of the defect."),
        replay=dict(
            how="np.load(roof.npy) -> level_cloud(...) -> points; then "
                "points[npz['facet_k']] rebuilds facet k exactly.",
            index_frame="row numbers into the LEVELED roof point array; "
                        "leveling is a rotation, so row order is unchanged "
                        "from roof.npy",
            index_check="points[idx] compared to the fitted points bit for bit "
                        "(np.array_equal on float64) before this file was "
                        "written; a mismatch aborts the run",
            npz=npz.name,
            source_cloud_sha256=cloud_sha(points),
            source_cloud_n=int(len(points))),
        params=dict(probability=1.0,
                    min_points_hard=min_points_hard,
                    min_points_hard_form=("RAW COUNT, not yet transferable; "
                                          "see Task 6 step 4"
                                          if min_points_hard == MIN_POINTS else
                                          "overridden from the command line"),
                    min_area_hard_cu2=fhex(min_area),
                    min_area_hard_form=f"{MIN_AREA_POINTS_EQUIV} x spacing^2 "
                                       f"(transferable)",
                    coverage_cell_mult=COVERAGE_CELL_MULT,
                    min_blob_area_cu2=MIN_BLOB_AREA,
                    band_mult=cfg["band_mult"], trim_mult=cfg["trim_mult"],
                    alpha_mult=cfg["alpha_mult"],
                    min_points_frac=cfg["min_points_frac"],
                    fit_sample=cfg["fit_sample"], max_planes=cfg["max_planes"]),
        scalars=dict(spacing_cu=fhex(spacing), band_cu=fhex(band),
                     cell_cu=fhex(cell), quality_bar=fhex(bar),
                     n_points=int(len(points)),
                     spacing_cu_readable=round(float(spacing), 6),
                     band_cu_readable=round(float(band), 6),
                     cell_cu_readable=round(float(cell), 6),
                     quality_bar_readable=round(float(bar), 4)),
        main_quality_ratios=[round(float(r), 4) for r in ratios],
        counts=dict(n_main=len(facets), n_recovered=len(new),
                    n_total=len(allf), n_blobs=len(blobs)),
        blobs=[dict(blob=i, area_cu2=round(float(b["area_cu2"]), 4),
                    n_cells=int(len(b["cells"])),
                    box=[[round(float(v), 4) for v in b["box"][0]],
                         [round(float(v), 4) for v in b["box"][1]]])
               for i, b in enumerate(blobs)],
        facets=rows,
        # Every plane RANSAC proposed inside every blob, kept or rejected, plus
        # the PEEL log (planes the pitch window discarded before they ever
        # became candidates). Task 6C reads this.
        recovery_log=log,
        wall_clock_s=round(time.perf_counter() - t0, 1),
    )
    jf = out / f"canonical-{args.stamp}.json"
    jf.write_text(json.dumps(doc, indent=2, default=float))
    print(f"  wrote {jf}")
    print(f"  wrote {npz}  ({npz.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
