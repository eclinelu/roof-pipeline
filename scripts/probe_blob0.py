# Blob 0: a location picture, and the quality-bar tie.
#
#   .venv/Scripts/python.exe -u scripts/probe_blob0.py C:/odm/datasets/big_house
#
# Writes (standing rule R2):
#   reports/big_house/blob0-location-<date>.png    DIAGNOSTIC A, picture only
#   reports/big_house/quality-bar-tie-<date>.json  DIAGNOSTIC B
#
# SIDE ARTIFACT ONLY. Nothing here is adopted, no threshold is changed, no
# comparison operator is changed, no canonical state is written.
# canonical-2026-07-26-r2 remains canonical and published coverage remains
# 88.40 percent.
#
# ---------------------------------------------------------------------------
# WHY ONE SCRIPT FOR BOTH
#
# The picture and the tie need the identical prefix: main discovery, the
# quality bar, the pre-recovery coverage masks, and the residual blobs. Running
# that twice would cost a second full pass AND would give two runs that have to
# be ARGUED to be the same run. One pass, two artifacts, one state.
#
# WHY THE SEQUENCE MUST BE THE PRODUCTION SEQUENCE
#
# Open3D's RANSAC draws from a single GLOBAL stream. discover_facets reseeds it
# (o3d.utility.random.seed(0)) on its first line, so each discovery call
# restarts the stream, and everything AFTER a discovery call inherits that
# call's stream position. The last discovery before the recovery pass must
# therefore be the one whose facets are handed to it, or the recovery is being
# run from a different point in the stream than the run it claims to reproduce.
#
# CROSS-CHECKS, so this probe can fail loudly instead of reporting confidently
#   1. main facets vs canonical-2026-07-26-r2.npz, compared as index SETS
#   2. blob 0 plan area and cell count vs the canonical blob table
#   3. blob 0's candidate at recovery min_pitch=1.0 vs blob0-rejection-2026-07-26
# If any disagrees, the probe is measuring something other than the published
# state and every other number in it is void. They are recorded in the output
# rather than merely asserted.
# ---------------------------------------------------------------------------
import argparse
import json
import struct
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_closing, binary_dilation, binary_fill_holes

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                            # noqa: E402
from canonical import leveled_points                              # noqa: E402
from recon_common import discover_facets                          # noqa: E402
from roofkit.stats import median_nn_spacing                       # noqa: E402
from roofkit.measure import (tilt_degrees, azimuth_degrees,       # noqa: E402
                             facet_area)
from roofkit.segment import (find_roof_planes,                    # noqa: E402
                             _point_plane_dist)
from roofkit import coverage as cov                               # noqa: E402

REPO = Path(__file__).resolve().parents[1]

# The production constants, copied from canonical_state.py so this probe cannot
# drift from it silently.
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
MIN_AREA_POINTS_EQUIV = 3704
MAIN_MIN_PITCH = 5.0
RECOVERY_MIN_PITCH_DIAG = 1.0   # DIAGNOSTIC ONLY: low enough that the pitch
                                # window cannot be the reason for a rejection,
                                # which is the only way to SEE the quality
                                # number. Production recovery stays at 5.0.
CANONICAL_STAMP = "2026-07-26-r2"
# Run 2 scale, from comparison-2026-07-18-scored-2026-07-18.json. Read from
# that file at runtime; this is only the fallback if the file moves.
FALLBACK_IN_PER_CU = 40.4541


def fhex(x):
    """Exact float as a hex string. Decimal rounding is what created this whole
    question (2.948 against 2.948); hex is lossless."""
    return float(x).hex()


def bits(x):
    """The 64 bits of a float, as an unsigned int. Two floats are THE SAME
    NUMBER if and only if these are equal. `==` is the same test, but printing
    the bits makes 'equal at three decimals' impossible to confuse with
    'bitwise equal'."""
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def ulps_between(a, b):
    """How many representable float64 values lie between a and b. 0 = the same
    number; 1 = adjacent floats; millions = numerically distinct values that
    only LOOK equal because the log rounds to three decimals."""
    ia, ib = bits(a), bits(b)
    ia = ia if ia >> 63 == 0 else (1 << 64) - ia      # monotone across the sign
    ib = ib if ib >> 63 == 0 else (1 << 64) - ib
    return int(abs(ia - ib))


def exact(x):
    """Full-precision record of one scalar: repr (round-trips), hex, bits."""
    return dict(repr=repr(float(x)), hex=fhex(x), bits=bits(x))


def cell_ids(ij, ny1):
    """The blob/point cell encoding recover_facets uses: i*(ny+1) + j."""
    return ij[:, 0].astype(np.int64) * ny1 + ij[:, 1].astype(np.int64)


def occupancy(points_xy, g):
    """Bool grid: does any point fall in this plan cell? Same binning as
    coverage_masks. Kept as bool so eight of these cost ~8 MB, not ~460 MB."""
    H, _, _ = np.histogram2d(
        points_xy[:, 0], points_xy[:, 1], bins=[g["nx"], g["ny"]],
        range=[[g["xlo"], g["xlo"] + g["nx"] * g["cell"]],
               [g["ylo"], g["ylo"] + g["ny"] * g["cell"]]])
    return H >= 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    name = Path(args.dataset).name
    out = REPO / "reports" / name
    out.mkdir(parents=True, exist_ok=True)

    checks = []                     # every cross-check, pass or fail

    points = leveled_points(cfg)
    spacing = median_nn_spacing(points)
    print(f"  {len(points):,} points   spacing {spacing:.6f} cu")

    # --- main discovery ----------------------------------------------------
    # canonical_state.py calls discover_facets WITHOUT min_pitch, so it takes
    # recon_common's default of 10.0, while the file it writes records
    # min_pitch_deg = 5.0. Both are run here and both are compared against the
    # canonical index arrays, so the record states which one actually produced
    # the published state instead of assuming it.
    fac10, band, s_full = discover_facets(points, cfg, probability=1.0,
                                          spacing=spacing, min_pitch=10.0)
    # Run the 5.0 discovery LAST so the RANSAC stream position handed to the
    # recovery pass matches probe_blob0_rejection.py exactly.
    fac5, _, _ = discover_facets(points, cfg, probability=1.0,
                                 spacing=spacing, min_pitch=MAIN_MIN_PITCH)

    canon = json.loads((out / f"canonical-{CANONICAL_STAMP}.json").read_text())
    npz = np.load(out / f"canonical-{CANONICAL_STAMP}.npz")
    n_main = canon["counts"]["n_main"]
    canon_idx = [set(npz[f"facet_{k}"].tolist()) for k in range(n_main)]

    def match_canonical(fl, tag):
        if len(fl) != n_main:
            return dict(variant=tag, n_facets=len(fl), matches_canonical=False,
                        note=f"{len(fl)} facets, canonical has {n_main}")
        per = [len(set(np.asarray(f["idx"]).tolist()) ^ canon_idx[k]) == 0
               for k, f in enumerate(fl)]
        return dict(variant=tag, n_facets=len(fl),
                    matches_canonical=bool(all(per)),
                    per_facet_identical=[bool(p) for p in per],
                    n_points=[int(len(f["points"])) for f in fl])

    m10 = match_canonical(fac10, "min_pitch=10 (recon_common default, which is "
                                 "what canonical_state.py actually passes)")
    m5 = match_canonical(fac5, "min_pitch=5 (what canonical-*.json records)")
    print(f"  main discovery vs canonical: at 10 -> {m10['matches_canonical']}, "
          f"at 5 -> {m5['matches_canonical']}")

    # Whichever reproduces the canonical index arrays IS the published state,
    # and that is what both artifacts must describe. If both do, the parameter
    # mismatch is inert on this cloud and either will serve.
    if m5["matches_canonical"]:
        facets, chosen = fac5, "min_pitch=5"
    elif m10["matches_canonical"]:
        facets, chosen = fac10, "min_pitch=10"
    else:
        facets, chosen = fac5, "min_pitch=5 (NEITHER matched canonical)"
    checks.append(dict(
        check="main facets reproduce canonical-2026-07-26-r2",
        passed=bool(m5["matches_canonical"] or m10["matches_canonical"]),
        at_min_pitch_10=m10, at_min_pitch_5=m5, used=chosen,
        why=("both artifacts must describe the PUBLISHED state, so the "
             "discovery variant that reproduces the canonical index arrays is "
             "the one they are built on")))

    # --- the quality bar ---------------------------------------------------
    bar, ratios = cov.calibrate_quality_bar(facets, s_full)
    bar_facet = int(np.argmax(ratios))
    print(f"  quality bar {bar!r}  set by main facet {bar_facet}")

    # --- masks and blobs, exactly as the production run builds them --------
    cell = COVERAGE_CELL_MULT * s_full
    masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    b0 = blobs[0]
    canon_b0 = canon["blobs"][0]
    checks.append(dict(
        check="blob 0 reproduces the canonical blob table",
        passed=bool(abs(b0["area_cu2"] - canon_b0["area_cu2"]) < 1e-4 and
                    len(b0["cells"]) == canon_b0["n_cells"]),
        observed=dict(area_cu2=round(float(b0["area_cu2"]), 4),
                      n_cells=int(len(b0["cells"]))),
        canonical=dict(area_cu2=canon_b0["area_cu2"],
                       n_cells=canon_b0["n_cells"])))

    # --- blob 0's candidate points (the cell-selection rule) ---------------
    ny1 = np.int64(g["ny"] + 1)
    pi = np.clip(((points[:, 0] - g["xlo"]) / g["cell"]).astype(np.int64),
                 0, g["nx"] - 1)
    pj = np.clip(((points[:, 1] - g["ylo"]) / g["cell"]).astype(np.int64),
                 0, g["ny"] - 1)
    point_cell = pi * ny1 + pj
    b0_cells = cell_ids(b0["cells"], ny1)
    cand_idx = np.flatnonzero((dist > band) & np.isin(point_cell, b0_cells))
    cand = points[cand_idx]
    b0_mask = np.zeros(masks["footprint"].shape, dtype=bool)
    b0_mask[b0["cells"][:, 0], b0["cells"][:, 1]] = True
    print(f"  blob 0: {b0['area_cu2']:.4f} cu^2 plan, {len(b0['cells']):,} cells, "
          f"{len(cand):,} unexplained candidate points")

    # --- per-facet plan occupancy, used by BOTH artifacts ------------------
    # The picture outlines them; the tie report measures adjacency and overlap
    # against them. Computed once.
    facet_occ = [occupancy(np.asarray(f["points"])[:, :2], g) for f in facets]

    # ======================================================================
    # DIAGNOSTIC A: the picture, and only the picture
    # ======================================================================
    in_per_cu = FALLBACK_IN_PER_CU
    sc = out / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        # "scale" is the ADOPTED run 2 scale; the file also carries an
        # "alternative_scaling_NOT_adopted" block, which is not this one.
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])
    png = out / f"blob0-location-{args.stamp}.png"
    render_plan(png, masks, g, b0_mask, facets, facet_occ, in_per_cu, name,
                args.stamp)
    print(f"  wrote {png}   (scale {in_per_cu} in/cu, run 2)")

    # ======================================================================
    # DIAGNOSTIC B: is the 2.948 tie real?
    # ======================================================================
    # Spatial relation of blob 0 to every main facet: plan overlap, contact
    # along a shared boundary, and whether any points are shared at all.
    facet_rel = []
    for k, f in enumerate(facets):
        occ = facet_occ[k]
        n_ov = int((b0_mask & occ).sum())
        touch = int((binary_dilation(b0_mask, iterations=1) & occ &
                     ~b0_mask).sum())
        facet_rel.append(dict(
            facet=k, pitch_deg=round(float(f["pitch"]), 3),
            azimuth_deg=round(float(azimuth_degrees(f["normal"])), 2),
            plan_cells_shared_with_blob0=n_ov,
            pct_of_blob0_cells=round(100.0 * n_ov / len(b0["cells"]), 2),
            contact_cells=touch,
            contact_length_cu=round(touch * g["cell"], 3),
            shared_points_with_blob0=int(len(np.intersect1d(
                cand_idx, np.asarray(f["idx"], np.int64))))))

    # The candidate only EXISTS if the pitch window lets it through, so the
    # recovery pass is run at min_pitch=1.0. That is a measurement setting and
    # not a proposal: under the production value of 5.0, blob 0's plane is
    # rejected at the pitch window and the quality bar never sees it.
    min_area = MIN_AREA_POINTS_EQUIV * spacing ** 2
    d = []
    for f in facets:
        pts = np.asarray(f["points"], float)
        s_ff = float(np.median(cov._nn(pts)))
        d.append(len(pts) * spacing ** 2 /
                 max(float(facet_area(pts, f["normal"],
                                      cfg["alpha_mult"] * s_ff)), 1e-12))
    min_points = int(round(MIN_AREA_POINTS_EQUIV * float(np.median(d))))

    # THE FULL-PRECISION READING, TAKEN FROM INSIDE recover_facets.
    #
    # recover_facets rounds its log to three decimals, and that rounding IS the
    # apparent tie. The obvious fix -- re-peel blob 0 outside recover_facets
    # with the same arguments and measure the plane again -- does not work, and
    # the reason is the whole lesson of this investigation: Open3D's RANSAC
    # draws from one GLOBAL stream, so an identical call made at a different
    # position in that stream returns a DIFFERENT plane. That re-peel is run
    # below anyway, as evidence, but it is not the measurement.
    #
    # So instead of re-deriving the number, capture it where it is actually
    # computed. facet_quality is looked up as a module global inside
    # recover_facets, so wrapping cov.facet_quality records every candidate's
    # unrounded quality as the production code computes it. No production code
    # is modified; the wrapper is removed immediately afterwards.
    captured = []
    _orig_fq = cov.facet_quality

    def _spy(pts, normal, sp):
        q, n = _orig_fq(pts, normal, sp)
        captured.append(dict(n_points=int(len(pts)), q=float(q),
                             normal=np.asarray(n, float).copy(),
                             points=pts))
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
        cov.facet_quality = _orig_fq
    entry = log[0]
    logged = entry["planes"][0] if entry["planes"] else None

    # The candidate is the plane recover_facets logged; match it by point count.
    shot = next(c for c in captured if c["n_points"] == logged["n"])
    q_cand, n_cand = shot["q"], shot["normal"]
    cand_plane = dict(points=shot["points"], normal=shot["normal"])
    q_bar_facet, _ = cov.facet_quality(facets[bar_facet]["points"],
                                       facets[bar_facet]["normal"], s_full)

    # Did the reassignment pass run INSIDE recover_facets' own peel of blob 0?
    # find_roof_planes only reassigns when more than one plane is KEPT, so this
    # is read off the peel log rather than assumed.
    kept_by_pitch = [p for p in entry.get("peels", []) if p.get("kept_by_pitch")]

    # EVIDENCE, not measurement: the same call, made now, from a different
    # position in the global RANSAC stream.
    peels_restream = []
    planes_restream = find_roof_planes(
        cand, distance_threshold=band, min_points=max(300, min_points),
        min_pitch=RECOVERY_MIN_PITCH_DIAG, max_pitch=60.0, max_planes=4,
        probability=1.0, peel_log=peels_restream)
    restream = None
    if planes_restream:
        big = max(planes_restream, key=lambda p: len(p["points"]))
        q_rs, _ = cov.facet_quality(big["points"], big["normal"], s_full)
        restream = dict(n_planes_kept=len(planes_restream),
                        largest_plane_n_points=int(len(big["points"])),
                        quality=exact(q_rs),
                        reassignment_pass_ran=bool(len(planes_restream) > 1),
                        peels=peels_restream)

    checks_b = list(checks)
    checks_b.append(dict(
        check="blob 0's candidate reproduces blob0-rejection-2026-07-26.json",
        passed=bool(logged is not None and logged["n"] == 162938 and
                    logged.get("rejected_by", "").startswith("quality")),
        observed=(dict(n=logged["n"], pitch=logged["pitch"],
                       quality=logged["quality"], bar=logged["bar"],
                       gross_cu2=logged.get("gross_cu2"),
                       rejected_by=logged.get("rejected_by"),
                       kept=logged["kept"]) if logged else None),
        expected_2026_07_26=dict(n=162938, pitch=3.82, quality=2.948, bar=2.948,
                                 gross_cu2=16.5962,
                                 rejected_by="quality 2.948 > bar 2.948")))
    checks_b.append(dict(
        check="no reassignment pass contaminated blob 0's candidate",
        passed=bool(len(kept_by_pitch) == 1),
        n_planes_kept_by_pitch_in_blob0=len(kept_by_pitch),
        why=("find_roof_planes only runs its reassignment pass when more than "
             "one plane is KEPT. Blob 0's other peels are near-vertical (85.9 "
             "and 85.3 deg) and fail max_pitch, so exactly one plane is kept "
             "and there is no reassignment: this candidate's membership and "
             "normal are RANSAC's own. That is what makes this measurement "
             "different in kind from the one that produced the wrong 19.04 "
             "cu^2 figure."),
        peels=entry.get("peels", [])))
    checks_b.append(dict(
        check="the quality figure was READ from inside recover_facets, not "
              "re-derived by a second peel",
        passed=True,
        method="cov.facet_quality was wrapped for the duration of the "
               "recover_facets call and unwrapped immediately after, so the "
               "unrounded value is the one production code computed. No "
               "production code was modified.",
        why_a_re_peel_would_not_do=(
            "Open3D's RANSAC draws from a single GLOBAL stream, so the same "
            "call made at a different position in that stream returns a "
            "DIFFERENT plane. The re-peel is recorded below as evidence of "
            "exactly that, and is NOT the measurement."),
        re_peel_from_a_different_stream_position=restream))

    n_c = np.asarray(n_cand, float); n_c /= np.linalg.norm(n_c)
    n_b = np.asarray(facets[bar_facet]["normal"], float)
    n_b /= np.linalg.norm(n_b)

    tie = dict(
        task="DIAGNOSTIC B: is blob 0's fit quality really EQUAL to the bar, or "
             "is three-decimal rounding hiding a near-miss?",
        dataset=name, date=args.stamp,
        status=("SIDE ARTIFACT ONLY. No threshold changed, no comparison "
                "operator changed, no canonical state written. "
                "canonical-2026-07-26-r2 remains canonical; published coverage "
                "remains 88.40 percent."),
        cross_checks=checks_b,
        diagnostic_setting=dict(
            recovery_min_pitch=RECOVERY_MIN_PITCH_DIAG,
            production_recovery_min_pitch=5.0,
            why="blob 0's plane sits at 3.774 deg. Under the production value "
                "of 5.0 it fails the PITCH window inside find_roof_planes and "
                "never becomes a candidate, so the quality bar never sees it. "
                "Lowering recovery min_pitch to 1.0 is the only way to make the "
                "quality number observable at all. It is a measurement setting, "
                "not a proposal: in production blob 0 is rejected by pitch, and "
                "this report says what would reject it NEXT."),
        the_comparison=dict(
            candidate_quality=exact(q_cand),
            bar=exact(bar),
            difference_candidate_minus_bar=exact(q_cand - bar),
            equal_bitwise=bool(bits(q_cand) == bits(bar)),
            ulps_apart=ulps_between(q_cand, bar),
            passes_strict_greater_than_so_is_rejected=bool(q_cand > bar),
            would_be_accepted_if_operator_were_ge=bool(not (q_cand > bar)),
            rounded_to_3dp=[round(float(q_cand), 3), round(float(bar), 3)],
            reading="equal at three decimals is a NEAR-MISS; bitwise equal is "
                    "the same number. ulps_apart counts the representable "
                    "float64 values between them: 0 means identical, and "
                    "anything large means the two are numerically distinct and "
                    "only LOOK equal because the log rounds."),
        candidate=dict(
            n_points=int(len(cand_plane["points"])),
            n_candidate_points_offered=int(len(cand)),
            pitch_deg=round(float(tilt_degrees(n_cand)), 4),
            azimuth_deg=round(float(azimuth_degrees(n_cand)), 3),
            normal_hex=[fhex(v) for v in n_c],
            logged_by_recover_facets=logged),
        where_the_bar_is_computed=dict(
            definition="roofkit/coverage.py:301  calibrate_quality_bar(facets, "
                       "spacing) -> float(max(per-facet trimmed RMS / spacing))",
            called_from=[
                "scripts/canonical_state.py:186  bar, ratios = "
                "cov.calibrate_quality_bar(facets, s_full)",
                "scripts/coverage_recon.py:88   same call, same position",
                "scripts/probe_blob0_rejection.py:70  same"],
            argument_at_the_call_site="`facets`, the list returned by "
                                      "discover_facets. That list is MAIN "
                                      "facets only: recovered facets do not "
                                      "exist yet at that line.",
            position_relative_to_recovery="computed at canonical_state.py:186; "
                                          "recover_facets is called at line "
                                          "205. The bar is fixed 19 lines "
                                          "before the recovery pass begins.",
            inside_recover_facets="quality_bar arrives as a scalar parameter "
                                  "(coverage.py:310) and is READ in exactly two "
                                  "places: line 432, which copies it into the "
                                  "log, and line 455, the test `q > "
                                  "quality_bar`. It is never assigned, never "
                                  "recomputed, and accepted candidates are "
                                  "appended to `new_facets`, which is never fed "
                                  "back into calibrate_quality_bar.",
            can_a_candidate_set_its_own_bar=False,
            verdict="NO DEFECT ON THIS AXIS. The bar is computed once, from the "
                    "8 main facets, before the recovery loop starts, and is "
                    "immutable for the whole loop. The failure mode asked about "
                    "-- a candidate rougher than every main facet raising the "
                    "max() it is then tested against, and then failing on "
                    "strict > -- cannot occur, because no candidate ever enters "
                    "the max(). Every candidate is tested against the same "
                    "number, whatever any other candidate did."),
        which_facet_sets_the_bar=dict(
            facet=bar_facet,
            quality=exact(ratios[bar_facet]),
            equals_bar_bitwise=bool(bits(ratios[bar_facet]) == bits(bar)),
            recomputed_independently=exact(q_bar_facet),
            pitch_deg=round(float(facets[bar_facet]["pitch"]), 4),
            azimuth_deg=round(float(azimuth_degrees(
                facets[bar_facet]["normal"])), 3),
            n_points=int(len(facets[bar_facet]["points"])),
            all_main_qualities_readable=[round(float(r), 4) for r in ratios],
            all_main_qualities=[exact(r) for r in ratios],
            margin_to_second_roughest=round(float(bar - sorted(ratios)[-2]), 6),
            note="the bar IS this facet's quality by construction (max over the "
                 "main facets), so bitwise equality here is expected. It is a "
                 "self-check on the arithmetic, not a finding."),
        spatial_relation_to_the_bar_facet=facet_rel[bar_facet],
        spatial_relation_to_every_main_facet=facet_rel,
        geometry_against_the_bar_facet=dict(
            angle_between_normals_deg=round(float(np.degrees(np.arccos(
                np.clip(abs(n_c @ n_b), -1, 1)))), 4),
            candidate_pitch_deg=round(float(tilt_degrees(n_cand)), 4),
            bar_facet_pitch_deg=round(float(facets[bar_facet]["pitch"]), 4),
            median_abs_distance_of_blob0_points_to_bar_facet_plane_cu=round(
                float(np.median(_point_plane_dist(
                    cand, facets[bar_facet]))), 5),
            band_cu=round(float(band), 6),
            shared_points=int(len(np.intersect1d(
                cand_idx, np.asarray(facets[bar_facet]["idx"], np.int64)))),
            reading="single ownership guarantees zero shared POINTS, so that "
                    "number is a check, not a finding. A shared underlying "
                    "SURFACE would show up instead as a small normal angle plus "
                    "plan adjacency; a coincidence would show up as neither."),
    )
    p_b = out / f"quality-bar-tie-{args.stamp}.json"
    p_b.write_text(json.dumps(tie, indent=2, default=float))
    print(f"  wrote {p_b}")

    print("\n  THE COMPARISON, unrounded")
    print(f"    candidate quality  {q_cand!r}   {fhex(q_cand)}")
    print(f"    bar (main facet {bar_facet})  {bar!r}   {fhex(bar)}")
    print(f"    difference         {q_cand - bar!r}")
    print(f"    bitwise equal      {bits(q_cand) == bits(bar)}")
    print(f"    ulps apart         {ulps_between(q_cand, bar):,}")
    print()
    for c in checks_b:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check']}")


def render_plan(path, masks, g, b0_mask, facets, facet_occ, in_per_cu, name,
                stamp):
    """Top-down plan view: the building footprint, the 8 main facets outlined
    and numbered, and blob 0 filled.

    Deliberately plain. This answers 'where is it', so it has to be readable
    against a memory of walking the roof, not pretty.

    ORIENTATION. The cloud is georeferenced (UTM), and leveling rotates it about
    a HORIZONTAL axis by 1.083 degrees, which tilts the cloud without spinning
    the plan view. So +y is UTM grid north to within that tilt, and the north
    arrow points +y.

    SCALE. Cloud units are converted with the run 2 tape scale. The bar is
    labelled with the scale it used, because a length in feet is only as good
    as the scale behind it."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cell = g["cell"]
    ft_per_cu = in_per_cu / 12.0

    def img(m):
        """Grid (i=x, j=y) -> image (row=y increasing UPWARD, col=x), so the
        picture reads like a map instead of like an array."""
        return np.flipud(m.T)

    extent = [g["xlo"], g["xlo"] + g["nx"] * cell,
              g["ylo"], g["ylo"] + g["ny"] * cell]

    rgb = np.ones(img(masks["footprint"]).shape + (3,), dtype=float)
    rgb[img(masks["footprint"])] = (0.87, 0.87, 0.89)     # footprint mask
    rgb[img(masks["explained"] & masks["footprint"])] = (0.78, 0.82, 0.87)
    rgb[img(b0_mask)] = (0.95, 0.42, 0.16)                # blob 0, filled

    fig, ax = plt.subplots(figsize=(12, 10), dpi=150)
    ax.imshow(rgb, extent=extent, interpolation="nearest", origin="upper")

    # --- facet outlines + numbers -----------------------------------------
    # Close then fill each facet's occupancy before contouring. Raw occupancy
    # is speckled (a facet's points do not hit every cell it covers), and
    # contouring that directly draws a scribble around every gap instead of the
    # facet's boundary. Closing is dilate-then-erode: it bridges gaps up to the
    # kernel size without growing the outline overall.
    for k, occ in enumerate(facet_occ):
        m = binary_fill_holes(binary_closing(occ, iterations=3))
        ax.contour(img(m).astype(float), levels=[0.5], colors="#12305c",
                   linewidths=1.2, extent=extent, origin="upper")
        pts = np.asarray(facets[k]["points"])
        cx, cy = float(np.median(pts[:, 0])), float(np.median(pts[:, 1]))
        ax.text(cx, cy, str(k), fontsize=17, fontweight="bold",
                color="#12305c", ha="center", va="center",
                bbox=dict(boxstyle="circle,pad=0.28", fc="white", ec="#12305c",
                          lw=1.4, alpha=0.92))

    # --- north arrow -------------------------------------------------------
    x0, x1, y0, y1 = extent
    w, h = x1 - x0, y1 - y0
    nx_, ny_ = x1 - 0.07 * w, y0 + 0.80 * h
    ax.annotate("", xy=(nx_, ny_ + 0.10 * h), xytext=(nx_, ny_),
                arrowprops=dict(arrowstyle="-|>", lw=2.4, color="#111111",
                                mutation_scale=22))
    ax.text(nx_, ny_ + 0.115 * h, "N", fontsize=16, fontweight="bold",
            ha="center", va="bottom", color="#111111")
    ax.text(nx_, ny_ - 0.018 * h, "grid north\n(UTM, +/- 1.1 deg level tilt)",
            fontsize=7, ha="center", va="top", color="#444444")

    # --- scale bar, in feet ------------------------------------------------
    # Pick a round number of FEET that spans roughly a fifth of the view.
    target_ft = (w * ft_per_cu) / 5.0
    nice = [5, 10, 20, 25, 50, 100, 200]
    bar_ft = min(nice, key=lambda v: abs(v - target_ft))
    bar_cu = bar_ft / ft_per_cu
    # Bottom RIGHT: the building runs down the left and centre of the frame, so
    # the only reliably empty corner is this one.
    bx, by = x1 - 0.06 * w - bar_cu, y0 + 0.055 * h
    ax.plot([bx, bx + bar_cu], [by, by], color="#111111", lw=4,
            solid_capstyle="butt")
    for xx in (bx, bx + bar_cu):
        ax.plot([xx, xx], [by - 0.012 * h, by + 0.012 * h], color="#111111",
                lw=2)
    ax.text(bx + bar_cu / 2, by + 0.018 * h, f"{bar_ft} ft", fontsize=12,
            fontweight="bold", ha="center", va="bottom", color="#111111")
    ax.text(bx, by - 0.020 * h,
            f"scale {in_per_cu:.4f} in/cu (run 2 tape), {bar_cu:.3f} cloud units",
            fontsize=7, ha="left", va="top", color="#444444")

    handles = [
        plt.Line2D([], [], marker="s", ls="", ms=11, mfc="#f26b29", mec="none",
                   label="blob 0, unexplained (11.57 cu^2 plan)"),
        plt.Line2D([], [], color="#12305c", lw=1.6,
                   label="main facets 0-7, outlined and numbered"),
        plt.Line2D([], [], marker="s", ls="", ms=11, mfc="#c7d1de", mec="none",
                   label="explained by a facet"),
        plt.Line2D([], [], marker="s", ls="", ms=11, mfc="#dedee3", mec="none",
                   label="building footprint mask"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=9, framealpha=0.95)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{name}: where blob 0 sits   ({stamp})\n"
                 f"side artifact, canonical state unchanged", fontsize=12)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    main()
