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
from roofkit.measure import (up_from_tilt, azimuth_degrees,      # noqa: E402
                             facet_area, rise_over_12, is_low_slope,
                             LOW_SLOPE_DEG)
from roofkit.segment import assert_single_ownership              # noqa: E402
from roofkit import coverage as cov                              # noqa: E402

# Same constants the whole 6-series uses, so every state is comparable.
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15

# THE SIZE FLOOR, both thresholds in transferable form (decision 2026-07-26).
#
#   MIN_AREA   = 3704 x spacing^2
#   MIN_POINTS = 3704 x d, where d is the run's OWN measured surface point
#                density: the median, over the MAIN facets, of
#                n_points x spacing^2 / gross_area.
#
# Neither is a raw constant. A raw point count would be a per-site constant in
# disguise, because point density depends on flight altitude and image overlap,
# so "2000 points" covers a different physical patch on every cloud. Main facets
# are used for d because they exist BEFORE recovery runs, so the floor can be
# derived without circularity.
#
# The value this works out to varies by dataset, so THE VALUE ACTUALLY USED IS
# WRITTEN INTO EVERY RUN'S OUTPUT. A threshold nobody can audit is not a
# threshold (Emmett, 2026-07-26).
MIN_AREA_POINTS_EQUIV = 3704          # MIN_AREA_CU2 = this x spacing^2
MIN_POINTS_LEGACY_RAW = 2000          # what it was; kept only for the report


def measured_point_density(facets, spacing, alpha_mult):
    """Surface point density: points per spacing^2 of facet surface, median
    over the given facets. Dimensionless.

    A value near 1.0 would mean one point per spacing-square, which is what
    median nearest-neighbour spacing implies. It measures below that in
    practice (about 0.52 on big_house) because the alpha surface spans area the
    points do not densely fill: bridged gaps and trimmed clutter."""
    d = []
    for f in facets:
        pts = np.asarray(f["points"], float)
        s_f = float(np.median(cov._nn(pts)))
        gross = float(facet_area(pts, f["normal"], alpha_mult * s_f))
        d.append(len(pts) * spacing ** 2 / max(gross, 1e-12))
    return float(np.median(d)), [round(float(x), 4) for x in d]

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
        # Pitch in the form roofers state it, and the steep/low-slope class.
        # low_slope is a REPORTING LABEL, never an exclusion: the facet is
        # measured and counted exactly like any other. It exists because below
        # 2:12 the assembly, the material and the price all change, so a report
        # has to break the two out.
        pitch_rise_over_12=round(rise_over_12(f["pitch"]), 2),
        low_slope=is_low_slope(f["pitch"]),
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
    # Override the DERIVED point floor. Only for probes that ask what a
    # different floor would do; normal runs derive it from the cloud and never
    # pass this.
    ap.add_argument("--min-points", type=int, default=None)
    args = ap.parse_args()
    min_points_override = args.min_points
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

    # The point floor, DERIVED from this run's own main facets rather than
    # typed in. Computed here, after main discovery and before recovery, which
    # is the only moment where it can be both measured and used.
    density, density_per_facet = measured_point_density(facets, spacing,
                                                        cfg["alpha_mult"])
    derived_min_points = int(round(MIN_AREA_POINTS_EQUIV * density))
    min_points_hard = (derived_min_points if min_points_override is None
                       else int(min_points_override))
    print(f"  measured point density d = {density:.4f}  ->  MIN_POINTS = "
          f"{MIN_AREA_POINTS_EQUIV} x d = {derived_min_points}"
          + ("" if min_points_override is None
             else f"   (OVERRIDDEN to {min_points_hard})"))

    cell = COVERAGE_CELL_MULT * s_full
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    log = []
    new = cov.recover_facets(points, blobs, None, dist, band, s_full, bar,
                             alpha_mult=cfg["alpha_mult"], probability=1.0,
                             min_points_hard=min_points_hard,
                             min_area_hard=min_area, log=log, grid=g)
    allf = facets + new
    print(f"  {len(facets)} main + {len(new)} recovered = {len(allf)} facets "
          f"({len(blobs)} residual blobs)")

    # --- THE PERMANENT SINGLE-OWNERSHIP ASSERTION -------------------------
    # Every point belongs to exactly one facet. Runs on every run, fails loudly.
    # Cell-based blob selection is meant to make double ownership impossible;
    # this proves it each time rather than assuming it.
    assert_single_ownership(allf, where="canonical_state")
    print("  single-ownership check PASSED: no point is owned by two facets")

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

    # --- POST-recovery masks, for the reported coverage --------------------
    # Recomputed with every accepted facet counting as an explainer. Pure
    # arithmetic over fixed points: no fitting, no randomness.
    masks_post, g_post, _, _ = cov.coverage_masks(points, allf, band, cell)

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
            states=[
                dict(state="2026-07-23 26-facet state",
                     status="SUPERSEDED, not corrected",
                     reason="one sample from a distribution: produced by a "
                            "nondeterministic fit, and its geometry was never "
                            "written to disk, so it is permanently "
                            "unrecoverable. Its files stay on disk as the "
                            "evidence of the defect."),
                dict(state="canonical-2026-07-26 (25 facets)",
                     status="SUPERSEDED, not overwritten; its files remain",
                     reason="three defects were fixed after it: blob candidates "
                            "were selected by bounding box, so two facets owned "
                            "9,739 of the same points; min_pitch=10 was "
                            "deleting real low-slope roof; and the coverage "
                            "denominator was eroded with its holes still in it, "
                            "discarding 32.5 percent of the footprint. The "
                            "change in coverage between the two states is "
                            "decomposed cause by cause in "
                            "attribution-2026-07-26.json."),
            ],
            rule="supersede, never overwrite. A corrected file implies the old "
                 "numbers were an arithmetic mistake; they were not, they were "
                 "correct computations under a defective definition, and that "
                 "distinction is the finding."),
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
                    min_pitch_deg=5.0,
                    max_pitch_deg=60.0,
                    min_pitch_note="5, not 10. min_pitch is a DEFINITION of "
                                   "what counts as a roof, not a filter; see "
                                   "decisions/2026-07-26-min-pitch-definition.",
                    # THE FLOOR ACTUALLY USED, written out so it can be audited.
                    # It is derived per dataset, so a reader cannot look it up
                    # in the source. (Emmett, 2026-07-26.)
                    min_points_hard=min_points_hard,
                    min_points_hard_form=f"{MIN_AREA_POINTS_EQUIV} x d, "
                                         f"d = measured point density",
                    min_points_hard_derived=derived_min_points,
                    min_points_hard_overridden=(min_points_override is not None),
                    measured_point_density_d=round(float(density), 4),
                    measured_point_density_per_main_facet=density_per_facet,
                    min_points_legacy_raw_value=MIN_POINTS_LEGACY_RAW,
                    min_area_hard_cu2=fhex(min_area),
                    min_area_hard_cu2_readable=round(float(min_area), 6),
                    min_area_hard_form=f"{MIN_AREA_POINTS_EQUIV} x spacing^2 "
                                       f"(transferable)",
                    low_slope_boundary_deg=round(LOW_SLOPE_DEG, 4),
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
                    n_total=len(allf), n_blobs=len(blobs),
                    n_low_slope=sum(1 for f in allf if is_low_slope(f["pitch"])),
                    n_steep_slope=sum(1 for f in allf
                                      if not is_low_slope(f["pitch"]))),
        # B2: the footprint three ways, so the cost of each step is visible
        # without the reader having to know the erosion defect exists.
        footprint=cov.footprint_three_ways(masks_post, cell),
        filled_holes=cov.filled_hole_report(masks_post, cell),
        # B3: the two metrics the old single coverage number was conflating.
        coverage=cov.split_coverage(masks_post, cell),
        single_ownership_check=dict(
            ran=True, passed=True,
            what="no point index appears in two facets' index arrays",
            why="permanent, every run, fails loudly. Only possible because R1 "
                "persists inlier indices."),
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

    fp = doc["footprint"]
    cvg = doc["coverage"]
    print(f"\n  footprint  raw(>=2 pts) {fp['raw_cu2']} cu^2  -> "
          f"holes filled +{fp['holes_filled_cu2']} -> {fp['filled_cu2']} cu^2 "
          f"-> eroded {fp['eroded_cu2']} cu^2 "
          f"(erosion costs {fp['erosion_cost_pct_of_filled']}%)")
    print(f"  filled holes: {doc['filled_holes']['n_holes']:,}, largest "
          f"{doc['filled_holes']['largest'][0]['cu2'] if doc['filled_holes']['largest'] else 0} cu^2")
    d1 = cvg["density_testable_fraction"]
    d2 = cvg["facet_coverage"]
    print(f"  density-testable fraction (CAPTURE)  {d1['pct']:.2f}%  "
          f"({d1['testable_cu2']} of {d1['footprint_cu2']} cu^2)")
    print(f"  facet coverage (SEGMENTATION)        {d2['pct']:.2f}%  "
          f"({d2['explained_cu2']} of {d2['testable_cu2']} cu^2)")
    lo = [f for f in doc["facets"] if f["low_slope"]]
    print(f"  low-slope facets (< 2:12): {len(lo)}"
          + ("".join(f"\n    facet {f['facet']}: {f['pitch_deg']} deg "
                     f"({f['pitch_rise_over_12']}:12), {f['n_points']:,} pts"
                     for f in lo) if lo else ""))
    print(f"\n  wrote {jf}")
    print(f"  wrote {npz}  ({npz.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
