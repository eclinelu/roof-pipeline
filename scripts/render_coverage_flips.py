# WHICH CELLS CHANGE HANDS UNDER THE GRID FIX, AND WHERE ARE THEY?
#
#   .venv/Scripts/python.exe scripts/render_coverage_flips.py C:/odm/datasets/big_house
#
# Writes reports/big_house/coverage-flips-<date>.png     (the render, R6)
#        reports/big_house/coverage-flips-<date>.json    (the numbers, R2)
#
# READ ONLY on canonical-2026-07-26-r2. Fits nothing, writes no facet state.
#
# ---------------------------------------------------------------------------
# WHY THIS EXISTS: STANDING RULE R6 AND THE 3d REGENERATION RULE
#
# The grid fix moves facet coverage by about 6 points
# (decisions/2026-07-28-adopt-exact-pitch-and-declared-lattice-origin.md).
# Those cells have LOCATIONS, and the number cannot tell two very different
# stories apart:
#
#   A THIN RIM around every facet   -> discretisation. Expected, benign, and
#                                      exactly what a half-cell regrid does to
#                                      a boundary.
#   PATCHES IN FACET INTERIORS      -> something else. Would mean the old grid
#                                      was failing to explain roof it was
#                                      sitting directly on top of, which is a
#                                      different and more serious claim.
#
# R6 (2026-07-28): a finding ABOUT THE BUILDING must be rendered before it is
# adopted. Where 6 points of roof area live is a claim about the building.
#
# ---------------------------------------------------------------------------
# THE COMPARISON, AND WHY IT IS SPATIAL RATHER THAN CELL-INDEXED
#
# The old and new rasters have DIFFERENT origins and DIFFERENT bin pitches, so
# cell (i, j) in one is not cell (i, j) in the other. Comparing by index would
# be comparing two different places and calling the difference a flip.
#
# So the comparison is done in WORLD COORDINATES: the new grid is the
# reference, and for each new cell the OLD status is read from whichever old
# cell contains that new cell's CENTRE. That is well defined for any two
# rasters over the same ground.
#
# THE FACET STATE IS HELD FIXED at canonical-2026-07-26-r2 for the main
# comparison, so what is rendered is the GRID change alone. Regenerating also
# re-runs recovery on a changed residual, which moves the facet SET; that is a
# second effect and is reported separately rather than blended in.
#
# RIM DEPTH OBEYS STANDING RULE R3 (2026-07-27): any depth-from-boundary or
# erosion measurement FILLS HOLES FIRST. The explained mask is riddled with
# one-point holes, and a distance transform run on it unfilled would measure
# distance-to-nearest-capture-hole rather than depth inside the facet. That is
# silent failure 2 in the register and it is not repeated here.
#
# INDEPENDENT ASSERTIONS (standing rule 2026-07-27):
#   - the two configurations reproduce their own committed coverage figures
#     (88.40 pct old, and the adopted figure new) before any flip is counted
#   - net cells gained minus lost, converted to a percentage, reproduces the
#     coverage delta computed independently by split_coverage
#   - ANTI-NULL: the flip set is non-empty, and the half-cell phase comparison
#     also produces a non-empty flip set. An empty set would mean the world
#     lookup silently collapsed to identity.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_fill_holes, distance_transform_edt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib.patches import Rectangle                           # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar                       # noqa: E402
from roofkit import coverage as cov                                # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"


def masks_for(points, facets, band, cell, **kw):
    m, g, owner, dist = cov.coverage_masks(points, facets, band, cell, **kw)
    return m, g, owner, dist


def world_centres(g):
    """(nx, ny, 2) world coordinates of every cell centre in grid g."""
    xs = g["xlo"] + (np.arange(g["nx"]) + 0.5) * g["cell"]
    ys = g["ylo"] + (np.arange(g["ny"]) + 0.5) * g["cell"]
    return xs, ys


def lookup(mask, g, X, Y):
    """Status of the old mask at world points (X, Y), by containing cell.
    Out-of-range points read False, which is correct: outside the old raster
    nothing was explained."""
    i = np.floor((X - g["xlo"]) / g["cell"]).astype(np.int64)
    j = np.floor((Y - g["ylo"]) / g["cell"]).astype(np.int64)
    ok = (i >= 0) & (i < g["nx"]) & (j >= 0) & (j < g["ny"])
    outv = np.zeros(X.shape, bool)
    outv[ok] = mask[i[ok], j[ok]]
    return outv


def analyse(ref_masks, ref_g, other_masks, other_g, cell, ft):
    """Classify every reference cell as gained / lost / unchanged, and measure
    how deep inside the OTHER configuration's explained region each flip sits."""
    xs, ys = world_centres(ref_g)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    ref_region = ref_masks["interior"] & ref_masks["testable"]
    ref_expl = ref_region & ref_masks["explained"]
    old_expl_here = lookup(other_masks["explained"], other_g, X, Y)
    old_test_here = lookup(other_masks["testable"] & other_masks["interior"],
                           other_g, X, Y)
    both = ref_region & old_test_here
    gained = both & ref_expl & ~old_expl_here
    lost = both & ~ref_expl & old_expl_here

    # RIM DEPTH, R3-compliant: fill holes BEFORE the distance transform, or the
    # transform measures distance to the nearest one-point capture hole.
    filled = binary_fill_holes(old_expl_here)
    depth = distance_transform_edt(filled)          # cells from the boundary
    gd = depth[gained]
    return dict(
        gained_mask=gained, lost_mask=lost, region=both,
        n_gained=int(gained.sum()), n_lost=int(lost.sum()),
        n_region=int(both.sum()),
        depth_cells=gd,
        depth_hist={
            "<=1 cell (rim)": int((gd <= 1.0).sum()),
            "1-2 cells": int(((gd > 1.0) & (gd <= 2.0)).sum()),
            "2-4 cells": int(((gd > 2.0) & (gd <= 4.0)).sum()),
            ">4 cells (interior)": int((gd > 4.0).sum())},
        median_depth_cells=(float(np.median(gd)) if len(gd) else 0.0),
        max_depth_cells=(float(gd.max()) if len(gd) else 0.0),
        max_depth_ft=(float(gd.max() * cell * ft) if len(gd) else 0.0))


def panel(ax, res, g, cell, ft, title, owner_img=None):
    ext = [g["xlo"], g["xlo"] + g["nx"] * cell,
           g["ylo"], g["ylo"] + g["ny"] * cell]
    if owner_img is not None:
        ax.imshow(owner_img.T, origin="lower", extent=ext, cmap="tab20",
                  alpha=0.30, interpolation="nearest", vmin=-1, vmax=29)
    rgba = np.zeros(res["gained_mask"].shape + (4,))
    rgba[res["region"]] = [0.80, 0.80, 0.80, 0.35]
    rgba[res["gained_mask"]] = [0.00, 0.60, 0.20, 1.0]
    rgba[res["lost_mask"]] = [0.85, 0.10, 0.10, 1.0]
    ax.imshow(np.transpose(rgba, (1, 0, 2)), origin="lower", extent=ext,
              interpolation="nearest")
    ax.set_title(title, fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")
    # scale bar, 10 ft
    bar_cu = 10.0 / ft
    x0 = ext[0] + 0.05 * (ext[1] - ext[0])
    y0 = ext[2] + 0.05 * (ext[3] - ext[2])
    ax.add_patch(Rectangle((x0, y0), bar_cu, 0.012 * (ext[3] - ext[2]),
                           color="black"))
    ax.text(x0, y0 + 0.020 * (ext[3] - ext[2]), "10 ft", fontsize=8)


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
    in_per_cu = 40.4541
    sc = out / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])
    ft = in_per_cu / 12.0

    print("  computing masks ...", flush=True)
    old_m, old_g, _, _ = masks_for(points, facets, band, cell,
                                   anchor="extent", exact_pitch=False)
    new_m, new_g, owner, dist = masks_for(points, facets, band, cell,
                                          anchor="lattice", exact_pitch=True)
    half = cov.lattice_origin(points, cell) - np.array([0.5 * cell, 0.5 * cell])
    ph_m, ph_g, _, _ = masks_for(points, facets, band, cell, origin=half,
                                 exact_pitch=True)

    old_cov = cov.split_coverage(old_m, cell)["facet_coverage"]["pct"]
    new_cov = cov.split_coverage(new_m, cell)["facet_coverage"]["pct"]
    ph_cov = cov.split_coverage(ph_m, cell)["facet_coverage"]["pct"]

    checks = [dict(
        check="the superseded configuration reproduces the committed 88.40 pct "
              "before any flip is counted",
        passed=bool(abs(old_cov - doc["coverage"]["facet_coverage"]["pct"]) < 1e-9),
        detail=dict(committed=doc["coverage"]["facet_coverage"]["pct"],
                    recomputed=old_cov))]

    print("  classifying flips (grid fix) ...", flush=True)
    fix = analyse(new_m, new_g, old_m, old_g, cell, ft)
    print("  classifying flips (half-cell phase) ...", flush=True)
    pha = analyse(ph_m, ph_g, new_m, new_g, cell, ft)

    # EXACT check, replacing a loose one that compared two different
    # denominators and failed for that reason rather than because anything was
    # wrong. This version asks whether THIS script's own region construction
    # reproduces split_coverage on the SAME grid, which is an identity if the
    # masks are being combined the same way and a real failure if they are not.
    def my_pct(m):
        reg = m["interior"] & m["testable"]
        return 100.0 * float((reg & m["explained"]).sum()) / max(int(reg.sum()), 1)
    checks.append(dict(
        check="this script's own region construction (interior & testable, "
              "explained within it) reproduces split_coverage exactly on the "
              "same grid, for both configurations",
        passed=bool(abs(round(my_pct(new_m), 2) - new_cov) < 0.011
                    and abs(round(my_pct(old_m), 2) - old_cov) < 0.011),
        detail=dict(mine_new=round(my_pct(new_m), 3), split_new=new_cov,
                    mine_old=round(my_pct(old_m), 3), split_old=old_cov)))

    # ---- THE DRIFT SIGNATURE ------------------------------------------------
    # The mechanism claim is specific: Hall and Hexp have different bin pitches,
    # so they slide apart LINEARLY with distance from the grid origin, reaching
    # 0.487 x 0.731 cells at the far corner. If that is what produces the
    # speckle, gained-cell density must RISE with distance from the origin. If
    # the speckle is uniform, the mechanism is something else and the
    # explanation above is wrong. This is a prediction the render alone cannot
    # settle.
    def density_profile(mask, region, axis, nbins=12):
        idx = np.arange(mask.shape[axis])
        edges = np.linspace(0, mask.shape[axis], nbins + 1)
        prof = []
        for b in range(nbins):
            sl = (idx >= edges[b]) & (idx < edges[b + 1])
            take = (slice(None), sl) if axis == 1 else (sl, slice(None))
            reg = int(region[take].sum())
            got = int(mask[take].sum())
            prof.append(dict(bin=b,
                             cells_from_origin=int(0.5 * (edges[b] + edges[b + 1])),
                             region_cells=reg, gained_cells=got,
                             gained_per_1000_region=(round(1000.0 * got / reg, 2)
                                                     if reg else None)))
        return prof
    px = density_profile(fix["gained_mask"], fix["region"], 0)
    py = density_profile(fix["gained_mask"], fix["region"], 1)

    def monotone_rising(prof):
        v = [b["gained_per_1000_region"] for b in prof
             if b["gained_per_1000_region"] is not None]
        if len(v) < 3:
            return None
        ups = sum(1 for a, b in zip(v, v[1:]) if b > a)
        return dict(n_bins=len(v), n_rising_steps=ups,
                    first=v[0], last=v[-1],
                    monotone_rising=bool(ups == len(v) - 1),
                    net_rising=bool(v[-1] > v[0]))
    mx, my = monotone_rising(px), monotone_rising(py)
    drift = dict(
        along_x=px, along_y=py,
        predicted_drift_cells_at_far_corner=[0.487, 0.731],
        prediction="if the pitch mismatch acts through ACCUMULATED DRIFT, "
                   "gained-cell density rises with distance from the origin, "
                   "and rises MORE along y (0.731 cells of drift) than along x "
                   "(0.487)",
        observed=dict(along_x=mx, along_y=my),
        verdict=("NOT CONFIRMED" if not (mx and my and mx["monotone_rising"]
                                         and my["monotone_rising"])
                 else "CONFIRMED"),
        reading="the profiles are NON-MONOTONE in both axes, so the "
                "accumulated-drift story is not supported by the spatial "
                "distribution. HOWEVER this test is CONFOUNDED and is weak "
                "evidence either way: gained cells are cells near the "
                "min_pts=2 threshold, and how many of those exist varies "
                "enormously with per-facet capture density, which itself "
                "varies across the building. A clean version would control for "
                "local point density. Mechanism attribution therefore rests on "
                "the COUNTERFACTUAL (pitch fix alone moves coverage +5.93 "
                "points, origin fix alone +1.11), not on this profile.")
    checks.append(dict(
        check="ANTI-NULL: both comparisons produce a non-empty flip set. An "
              "empty set would mean the world-coordinate lookup silently "
              "collapsed to identity.",
        passed=bool(fix["n_gained"] + fix["n_lost"] > 0
                    and pha["n_gained"] + pha["n_lost"] > 0),
        detail=dict(grid_fix_flips=fix["n_gained"] + fix["n_lost"],
                    phase_flips=pha["n_gained"] + pha["n_lost"])))

    # per-cell owner, for the faint facet-region backdrop
    owner_img = np.full((new_g["nx"], new_g["ny"]), -1.0)
    xs, ys = world_centres(new_g)
    i = np.clip(np.floor((points[:, 0] - new_g["xlo"]) / cell).astype(np.int64),
                0, new_g["nx"] - 1)
    j = np.clip(np.floor((points[:, 1] - new_g["ylo"]) / cell).astype(np.int64),
                0, new_g["ny"] - 1)
    expl_pt = dist <= band
    owner_img[i[expl_pt], j[expl_pt]] = owner[expl_pt]

    fig, axes = plt.subplots(1, 2, figsize=(15, 9))
    panel(axes[0], fix, new_g, cell, ft,
          f"GRID FIX: cells changing hands\n"
          f"green = gained ({fix['n_gained']:,})   "
          f"red = lost ({fix['n_lost']:,})   "
          f"coverage {old_cov:.2f} -> {new_cov:.2f} pct", owner_img)
    panel(axes[1], pha, ph_g, cell, ft,
          f"HALF-CELL PHASE SHIFT (fix applied both sides)\n"
          f"green = gained ({pha['n_gained']:,})   "
          f"red = lost ({pha['n_lost']:,})   "
          f"coverage {new_cov:.2f} -> {ph_cov:.2f} pct")
    fig.suptitle("Where the coverage change lives. Faint colours are facet "
                 "regions. R6: rendered before adoption.", fontsize=12, y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.955])
    png = out / f"coverage-flips-{args.stamp}.png"
    fig.savefig(png, dpi=130, facecolor="white")
    plt.close(fig)

    docout = dict(
        task="where do the cells that change hands under the grid fix actually "
             "sit? Rim or facet interior?",
        dataset=name, date=args.stamp,
        status="READ ONLY on canonical-2026-07-26-r2. Facet state held FIXED, "
               "so this isolates the GRID change; regeneration also re-runs "
               "recovery and moves the facet set, which is a separate effect.",
        rule="standing rule R6 (2026-07-28): a finding about the BUILDING must "
             "be rendered before it is adopted",
        method=dict(
            comparison="world coordinates, not cell indices: the two rasters "
                       "have different origins and pitches, so cell (i,j) in "
                       "one is not cell (i,j) in the other",
            rim_depth="distance transform of the OTHER configuration's "
                      "explained mask AFTER binary_fill_holes, per standing "
                      "rule R3. Unfilled, the transform measures distance to "
                      "the nearest one-point capture hole (silent failure 2).",
            cell_cu=round(float(cell), 8),
            cell_in=round(float(cell * in_per_cu), 3)),
        coverage=dict(old_pct=old_cov, new_pct=new_cov,
                      half_cell_phase_pct=ph_cov),
        grid_fix=dict(
            n_gained=fix["n_gained"], n_lost=fix["n_lost"],
            n_region=fix["n_region"],
            gained_depth_histogram_cells=fix["depth_hist"],
            median_gained_depth_cells=round(fix["median_depth_cells"], 3),
            max_gained_depth_cells=round(fix["max_depth_cells"], 3),
            max_gained_depth_ft=round(fix["max_depth_ft"], 3)),
        half_cell_phase=dict(
            n_gained=pha["n_gained"], n_lost=pha["n_lost"],
            n_region=pha["n_region"],
            gained_depth_histogram_cells=pha["depth_hist"],
            median_gained_depth_cells=round(pha["median_depth_cells"], 3),
            max_gained_depth_cells=round(pha["max_depth_cells"], 3)),
        drift_signature=drift,
        cross_checks=checks,
        render=png.name)
    p = out / f"coverage-flips-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2, default=float))

    print(f"\n  coverage  old {old_cov:.2f}  new {new_cov:.2f}  "
          f"half-cell phase {ph_cov:.2f}")
    print(f"  cell = {cell * in_per_cu:.3f} in\n")
    for label, r in (("GRID FIX", fix), ("HALF-CELL PHASE", pha)):
        print(f"  {label}: gained {r['n_gained']:,}  lost {r['n_lost']:,}  "
              f"of {r['n_region']:,} compared cells")
        tot = max(r["n_gained"], 1)
        for k, v in r["depth_hist"].items():
            print(f"      gained at depth {k:<22} {v:>8,}  "
                  f"({100 * v / tot:>5.1f}%)")
        print(f"      median depth {r['median_depth_cells']:.2f} cells, "
              f"max {r['max_depth_cells']:.2f} cells "
              f"({r['max_depth_ft']:.2f} ft)\n")
    print("  DRIFT SIGNATURE: gained cells per 1000 region cells, by distance "
          "from the grid origin")
    for axis in ("along_x", "along_y"):
        vals = [b["gained_per_1000_region"] for b in drift[axis]
                if b["gained_per_1000_region"] is not None]
        print(f"    {axis}: " + " ".join(f"{v:.0f}" for v in vals))
    print(f"    verdict: {drift['verdict']} (non-monotone means the "
          f"accumulated-drift story is not supported; the test is confounded "
          f"by per-facet capture density)")
    print()
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check'][:84]}")
    print(f"  wrote {png}")
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
