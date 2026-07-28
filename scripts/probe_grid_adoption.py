# THE EVIDENCE PACKAGE FOR ADOPTING exact_pitch AND THE DECLARED LATTICE ORIGIN.
#
#   .venv/Scripts/python.exe scripts/probe_grid_adoption.py C:/odm/datasets/big_house
#
# Writes reports/big_house/grid-adoption-<date>.json      (standing rule R2)
#
# READ ONLY on the canonical state. Fits nothing. Writes no facet state.
#
# ---------------------------------------------------------------------------
# WHAT IT ESTABLISHES, in the order the adoption decision needs it
#
#   1. THE OLD PATH STILL REPRODUCES THE PUBLISHED NUMBER. anchor="extent" plus
#      exact_pitch=False must give exactly 88.40 pct and 299.654 cu^2. If the
#      superseded configuration cannot be recomputed, then "supersede, never
#      overwrite" is a slogan rather than a property.
#   2. THE TWO FIXES DECOMPOSED. What the pitch fix costs, what the origin fix
#      costs, and what they cost together. A single combined number would hide
#      which change did what.
#   3. THE INVARIANCE CLAIM THAT JUSTIFIES THE LATTICE ORIGIN, TESTED.
#   4. THE NEW STABILITY CLAIM: phase spread under the adopted configuration.
#
# ---------------------------------------------------------------------------
# ON POINT 3, WHICH IS THE ONLY PART THAT IS SUBTLE
#
# `lattice_origin` is floor(x.min() / cell) * cell, so it still READS x.min().
# It would be wrong to claim it is independent of the data. The claim is
# narrower and is the one that matters:
#
#   under anchor="extent", a change in x.min() moves the origin by an ARBITRARY
#   SUB-CELL AMOUNT, which changes which points share a cell;
#
#   under anchor="lattice", a change in x.min() can only move the origin by a
#   WHOLE NUMBER OF CELLS, which is a relabelling. Which points share a cell is
#   unchanged.
#
# So the test is not "the origin never moves". It is "the PARTITION never
# changes", and it is checked by comparing the occupancy pattern up to an
# integer shift. The perturbation used is deleting the extreme points, because
# that is exactly what a membership filter does and it is what made the M1a
# verifier disagree with the M1a filter in the first place.
#
# INDEPENDENT ASSERTIONS (standing rule 2026-07-27-silent-failure-standing-rule
# and its anti-null extension):
#   - the old configuration reproduces the committed canonical numbers exactly
#   - ANTI-NULL: the perturbation must actually move x.min() by a sub-cell
#     amount, or the invariance test proves nothing. This is the trap that
#     produced silent failures 7 and 8; the amount moved is reported.
#   - under anchor="extent" the SAME perturbation must CHANGE the partition.
#     Without this the invariance result could be vacuous, e.g. if the
#     perturbation happened to be too small to matter for either anchor.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar                      # noqa: E402
from roofkit import coverage as cov                               # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"
PHASE_OFFSETS = [(0.0, 0.0), (0.25, 0.0), (0.5, 0.0), (0.75, 0.0),
                 (0.0, 0.5), (0.5, 0.5), (0.33, 0.66), (0.66, 0.33)]


def readout(points, facets, band, cell, **kw):
    m, g, _, _ = cov.coverage_masks(points, facets, band, cell, **kw)
    s = cov.split_coverage(m, cell)
    f = cov.footprint_three_ways(m, cell)
    return dict(facet_coverage_pct=s["facet_coverage"]["pct"],
                density_testable_pct=s["density_testable_fraction"]["pct"],
                footprint_raw_cu2=f["raw_cu2"],
                footprint_filled_cu2=f["filled_cu2"],
                footprint_eroded_cu2=f["eroded_cu2"],
                nx=int(g["nx"]), ny=int(g["ny"]),
                xlo=float(g["xlo"]), ylo=float(g["ylo"]))


def partition_signature(xy, cell, anchor):
    """Which points share a cell, expressed so that an INTEGER shift of the
    origin does not change it. Cell indices are re-based to their own minimum,
    which removes any whole-cell offset and leaves only the phase."""
    if anchor == "lattice":
        lo = cov.lattice_origin(xy, cell)
    else:
        lo = xy.min(axis=0)
    i = np.floor((xy[:, 0] - lo[0]) / cell).astype(np.int64)
    j = np.floor((xy[:, 1] - lo[1]) / cell).astype(np.int64)
    return np.stack([i - i.min(), j - j.min()], axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    doc, points, facets, cfg = load_canonical(args.dataset, CANONICAL_STAMP)
    band = scalar(doc, "band_cu")
    cell = scalar(doc, "cell_cu")
    checks = []

    # ---- 1 + 2: decomposition -------------------------------------------
    configs = {
        "old_extent_loose_PUBLISHED": dict(anchor="extent", exact_pitch=False),
        "pitch_fix_only": dict(anchor="extent", exact_pitch=True),
        "origin_fix_only": dict(anchor="lattice", exact_pitch=False),
        "adopted_lattice_exact": dict(anchor="lattice", exact_pitch=True),
    }
    table = {k: readout(points, facets, band, cell, **v)
             for k, v in configs.items()}
    old = table["old_extent_loose_PUBLISHED"]
    pub_cov = doc["coverage"]["facet_coverage"]["pct"]
    pub_raw = doc["footprint"]["raw_cu2"]
    checks.append(dict(
        check="the SUPERSEDED configuration still reproduces the committed "
              "canonical numbers exactly, so superseded numbers can be "
              "recomputed rather than merely quoted",
        passed=bool(abs(old["facet_coverage_pct"] - pub_cov) < 1e-9
                    and abs(old["footprint_raw_cu2"] - pub_raw) < 1e-9),
        detail=dict(published_coverage=pub_cov,
                    recomputed_coverage=old["facet_coverage_pct"],
                    published_raw_cu2=pub_raw,
                    recomputed_raw_cu2=old["footprint_raw_cu2"])))

    adopted = table["adopted_lattice_exact"]
    decomposition = dict(
        published_coverage_pct=old["facet_coverage_pct"],
        pitch_fix_only_pct=table["pitch_fix_only"]["facet_coverage_pct"],
        origin_fix_only_pct=table["origin_fix_only"]["facet_coverage_pct"],
        adopted_pct=adopted["facet_coverage_pct"],
        delta_pitch_fix=round(table["pitch_fix_only"]["facet_coverage_pct"]
                              - old["facet_coverage_pct"], 4),
        delta_origin_fix=round(table["origin_fix_only"]["facet_coverage_pct"]
                               - old["facet_coverage_pct"], 4),
        delta_combined=round(adopted["facet_coverage_pct"]
                             - old["facet_coverage_pct"], 4),
        note="the two deltas do not add. They act on the same marginal cells, "
             "so the combined effect is slightly less than the sum.")

    # ---- 3: the invariance claim, tested --------------------------------
    # Perturbation: delete the extreme points, which is exactly what a
    # membership filter does. Use the largest facet's plan coordinates.
    xy = np.asarray(facets[0]["points"], float)[:, :2]
    keep = ((xy[:, 0] > np.percentile(xy[:, 0], 0.05)) &
            (xy[:, 1] > np.percentile(xy[:, 1], 0.05)))
    xy2 = xy[keep]
    dmin = np.array([xy2[:, 0].min() - xy[:, 0].min(),
                     xy2[:, 1].min() - xy[:, 1].min()])
    subcell = np.abs(dmin / cell - np.round(dmin / cell))
    checks.append(dict(
        check="ANTI-NULL: the perturbation actually moves x.min()/y.min() by a "
              "SUB-CELL amount. If it moved by whole cells only, the "
              "invariance test would be vacuous (silent failures 7 and 8).",
        passed=bool(subcell.max() > 0.05),
        detail=dict(min_moved_cu=[float(dmin[0]), float(dmin[1])],
                    min_moved_cells=[float(dmin[0] / cell), float(dmin[1] / cell)],
                    sub_cell_fraction=[float(subcell[0]), float(subcell[1])])))

    sig_lat_a = partition_signature(xy, cell, "lattice")[keep]
    sig_lat_b = partition_signature(xy2, cell, "lattice")
    lat_same = bool(np.array_equal(sig_lat_a - sig_lat_a.min(axis=0),
                                   sig_lat_b - sig_lat_b.min(axis=0)))
    sig_ext_a = partition_signature(xy, cell, "extent")[keep]
    sig_ext_b = partition_signature(xy2, cell, "extent")
    ext_same = bool(np.array_equal(sig_ext_a - sig_ext_a.min(axis=0),
                                   sig_ext_b - sig_ext_b.min(axis=0)))
    checks.append(dict(
        check="under anchor='lattice', deleting the extreme points leaves the "
              "cell PARTITION unchanged up to an integer relabelling",
        passed=lat_same))
    checks.append(dict(
        check="under anchor='extent', the SAME perturbation CHANGES the "
              "partition. Without this the result above could be vacuous.",
        passed=bool(not ext_same),
        detail=dict(extent_partition_changed=not ext_same,
                    n_points_differing=int(
                        (sig_ext_a - sig_ext_a.min(axis=0)
                         != sig_ext_b - sig_ext_b.min(axis=0)).any(1).sum()))))

    # ---- 4: the new stability claim -------------------------------------
    base_origin = cov.lattice_origin(points, cell)
    phase_rows = []
    for (ox, oy) in PHASE_OFFSETS:
        org = base_origin - np.array([ox * cell, oy * cell])
        r = readout(points, facets, band, cell, origin=org, exact_pitch=True)
        r["offset_cells"] = [ox, oy]
        phase_rows.append(r)
    keys = ["facet_coverage_pct", "density_testable_pct", "footprint_raw_cu2",
            "footprint_filled_cu2", "footprint_eroded_cu2"]
    stability = {k: dict(min=min(r[k] for r in phase_rows),
                         max=max(r[k] for r in phase_rows),
                         spread=round(max(r[k] for r in phase_rows)
                                      - min(r[k] for r in phase_rows), 6))
                 for k in keys}

    docout = dict(
        task="evidence package for adopting exact_pitch and the declared "
             "lattice raster origin",
        dataset=name, date=args.stamp,
        status="READ ONLY on canonical-2026-07-26-r2. No facet state written.",
        provenance="the bin-pitch defect and the unchosen origin were found "
                   "while auditing the raster behaviour of a connectivity "
                   "filter that was REJECTED for lack of a plateau. They were "
                   "not found while looking for a way to raise coverage. The "
                   "audit was ordered before the next mechanism pass, on the "
                   "grounds that a phase-dependent coverage number cannot "
                   "serve as a cross-pass detector.",
        scalars=dict(cell_cu=round(float(cell), 10),
                     band_cu=round(float(band), 10),
                     lattice_origin=[float(base_origin[0]),
                                     float(base_origin[1])],
                     extent_origin=[float(points[:, 0].min()),
                                    float(points[:, 1].min())]),
        configurations=table,
        decomposition=decomposition,
        new_stability_claim=dict(
            what="spread of each reported quantity over eight sub-cell raster "
                 "phase offsets, under the ADOPTED configuration",
            spread=stability,
            rows=phase_rows,
            reading="facet coverage is the quantity the pitch fix stabilises. "
                    "The footprint residue is NOT fixed by either change: it "
                    "is discretisation sensitivity from min_pts=2 on a cloud "
                    "with 249,745 one-point cells, and it is a permanent "
                    "property of the measure, not a defect."),
        cross_checks=checks)
    p = out / f"grid-adoption-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2, default=float))

    print(f"\n{'configuration':<30}{'coverage':>10}{'dens-test':>11}"
          f"{'raw':>10}{'filled':>10}{'eroded':>10}")
    for k, r in table.items():
        print(f"{k:<30}{r['facet_coverage_pct']:>10.2f}"
              f"{r['density_testable_pct']:>11.2f}{r['footprint_raw_cu2']:>10.3f}"
              f"{r['footprint_filled_cu2']:>10.3f}{r['footprint_eroded_cu2']:>10.3f}")
    d = decomposition
    print(f"\n  pitch fix alone   {d['delta_pitch_fix']:+.2f} points")
    print(f"  origin fix alone  {d['delta_origin_fix']:+.2f} points")
    print(f"  combined          {d['delta_combined']:+.2f} points  "
          f"({d['published_coverage_pct']:.2f} -> {d['adopted_pct']:.2f})")
    print("\n  NEW STABILITY CLAIM, spread over raster phase:")
    for k in keys:
        print(f"    {k:<26} {stability[k]['spread']:>10.4f}")
    print()
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check'][:86]}")
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
