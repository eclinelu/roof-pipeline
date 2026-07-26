# THROWAWAY DIAGNOSTIC (scripts/, not roofkit/). Answers the two questions
# that must be settled before any coverage code is written:
#
#   Task 1  point spacing on the main roof surface  -> sets the coverage
#           cell size. We refuse to hardcode a cell size before this exists.
#   Task 2  the dormer fork. Do the dormer surfaces exist in the RAW cloud
#           (segmentation dropped them) or were they never reconstructed
#           (a capture problem, not an algorithm problem)?
#
# It reuses the REAL pipeline filters from roofkit so the per-stage point
# counts are identical to what production does, not a re-implementation.
#
# Run:
#   python scripts/diag_coverage.py <dataset> --mode explore
#   python scripts/diag_coverage.py <dataset> --mode spacing
#   python scripts/diag_coverage.py <dataset> --mode dormer
import argparse
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")  # no display; we save PNGs
import matplotlib.pyplot as plt
from scipy.ndimage import binary_fill_holes, binary_erosion, label

from dataset_config import load_config
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box
from roofkit.isolate import height_cutoff, color_filter, planarity_filter
from roofkit.stats import median_nn_spacing

OUT = Path(r"C:\Users\eclin\AppData\Local\Temp\claude\C--dev-roof-pipeline"
           r"\cd956c9e-39fa-4e2e-825a-90eff394c259\scratchpad")

# A clean rectangle of single-surface main roof, chosen by eye from the plan
# view, away from any dormer hole, ridge, or eave edge. Used as the density
# BASELINE (Task 2) and the spacing sample (Task 1). Actual coordinates.
# (from the Task 1 tile scan: this region is one planar facet, RMS ~0.004 cu)
CLEAN_BOX = ((553484.0, 4543299.0), (553490.0, 4543305.0))  # (xlo,ylo),(xhi,yhi)


def in_box(p, box):
    """Boolean mask: which rows of p fall inside the XY box (ignores Z)."""
    (xlo, ylo), (xhi, yhi) = box
    return ((p[:, 0] >= xlo) & (p[:, 0] <= xhi) &
            (p[:, 1] >= ylo) & (p[:, 1] <= yhi))


def plane_rms(p):
    """Fit a least-squares plane to p and return the RMS off-plane distance.
    A clean single roof surface has RMS ~ point spacing; a patch straddling a
    ridge or holding clutter has RMS many times larger."""
    c = p.mean(axis=0)
    q = p - c
    # smallest-eigenvector of the covariance is the plane normal
    _, _, Vt = np.linalg.svd(q, full_matrices=False)
    n = Vt[-1]
    d = q @ n
    return float(np.sqrt(np.mean(d ** 2)))


def bounds(name, p):
    print(f"{name}: {len(p):,} pts")
    if len(p):
        print(f"    X [{p[:,0].min():.2f}, {p[:,0].max():.2f}]  "
              f"Y [{p[:,1].min():.2f}, {p[:,1].max():.2f}]  "
              f"Z [{p[:,2].min():.2f}, {p[:,2].max():.2f}]")


# --------------------------------------------------------------------------
# Task 1: spacing histogram on the main roof surface
# --------------------------------------------------------------------------
def plane_rms_trimmed(p, trim=3.0, iters=3):
    """Plane RMS after iteratively dropping points beyond trim*RMS, so a few
    stray off-roof points do not brand a genuinely flat patch as non-planar."""
    for _ in range(iters):
        c = p.mean(axis=0); q = p - c
        _, _, Vt = np.linalg.svd(q, full_matrices=False)
        d = q @ Vt[-1]
        rms = np.sqrt(np.mean(d ** 2))
        keep = np.abs(d) <= trim * rms
        if keep.all():
            break
        p = p[keep]
    return rms, len(p)


def mode_spacing(cfg, roof, s):
    from scipy.spatial import cKDTree
    # Auto-scan: tile the footprint into 2x2 cu boxes, keep only tiles that
    # are a single planar surface (trimmed plane RMS < 8x spacing) with plenty
    # of points. Pick the flattest as THE main-roof sample, and also aggregate
    # spacing across the flattest handful, so the number is not one lucky box.
    tile = 2.0
    x, y = roof[:, 0], roof[:, 1]
    xs = np.arange(x.min(), x.max() - tile, tile)
    ys = np.arange(y.min(), y.max() - tile, tile)
    cand = []
    for x0 in xs:
        for y0 in ys:
            box = ((x0, y0), (x0 + tile, y0 + tile))
            pts = roof[in_box(roof, box)]
            if len(pts) < 20000:
                continue
            rms, _ = plane_rms_trimmed(pts)
            cand.append((rms, len(pts), box))
    cand.sort(key=lambda t: t[0])
    flat = [c for c in cand if c[0] < 8 * s][:8]
    print(f"\n=== Task 1: spacing on the main roof surface ===")
    print(f"scanned {len(cand)} tiles; {len(flat)} are single-surface "
          f"(trimmed plane RMS < 8x spacing = {8*s:.4f} cu):")
    for rms, n, box in flat:
        (x0, y0), _ = box
        print(f"    tile @X{x0:.1f} Y{y0:.1f}: {n:,} pts, RMS {rms:.4f} cu")
    best_rms, best_n, best_box = flat[0]
    patch = roof[in_box(roof, best_box)]
    print(f"\nflattest tile {best_box}: {len(patch):,} pts, RMS {best_rms:.4f} cu")
    # full nearest-neighbor distances within the flattest patch (k=2: skip self)
    tree = cKDTree(patch)
    d, _ = tree.query(patch, k=2)
    nn = d[:, 1]
    pcts = np.percentile(nn, [5, 10, 25, 50, 75, 90, 95])
    print(f"  NN distance median : {np.median(nn):.4f} cu")
    print(f"  NN distance mean   : {nn.mean():.4f} cu")
    print(f"  NN distance std    : {nn.std():.4f} cu")
    print(f"  IQR (p25..p75)     : {pcts[2]:.4f} .. {pcts[4]:.4f} cu "
          f"(spread {pcts[4]-pcts[2]:.4f})")
    print(f"  percentiles p5/10/25/50/75/90/95: "
          + " ".join(f"{v:.4f}" for v in pcts))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(nn, bins=120, range=(0, np.percentile(nn, 99.5)), color="steelblue")
    ax.axvline(np.median(nn), color="k", ls="--", label=f"median {np.median(nn):.4f}")
    ax.set_xlabel("nearest-neighbor distance (cloud units)")
    ax.set_ylabel("point count")
    ax.set_title(f"Task 1: NN spacing on clean main-roof patch ({len(patch):,} pts)")
    ax.legend()
    fig.tight_layout()
    p = OUT / "task1_spacing_hist.png"
    fig.savefig(p, dpi=110)
    print(f"  wrote {p}")


# --------------------------------------------------------------------------
# Task 2: locate the dormer holes, then the dormer fork
# --------------------------------------------------------------------------
def detect_holes(roof, s, occ_cell_mult=4.0, occ_min_pts=2, min_area_cu2=0.10):
    """Find enclosed empty regions (holes) in roof.npy's plan view.

    This is DIAGNOSTIC hole-finding, not the proposed coverage algorithm:
    no plane is fitted, nothing is relabelled. We only ask 'where is roof.npy
    empty in a spot the roof surrounds?' to locate the dormers automatically.
    """
    cell = occ_cell_mult * s
    x, y = roof[:, 0], roof[:, 1]
    xlo, xhi, ylo, yhi = x.min(), x.max(), y.min(), y.max()
    nx = int((xhi - xlo) / cell) + 1
    ny = int((yhi - ylo) / cell) + 1
    H, xe, ye = np.histogram2d(x, y, bins=[nx, ny],
                              range=[[xlo, xhi], [ylo, yhi]])
    occ = H >= occ_min_pts                    # occupied cells
    filled = binary_fill_holes(occ)            # occupied + enclosed empties
    holes = filled & ~occ                      # the enclosed empties only
    lab, n = label(holes)
    results = []
    for i in range(1, n + 1):
        cells = np.argwhere(lab == i)          # (row=x-bin, col=y-bin)
        area = len(cells) * cell * cell
        if area < min_area_cu2:
            continue
        # drop blobs touching the grid border ring (perimeter fringe artifact)
        if (cells[:, 0].min() == 0 or cells[:, 1].min() == 0 or
                cells[:, 0].max() == nx - 1 or cells[:, 1].max() == ny - 1):
            continue
        bx0 = xlo + cells[:, 0].min() * cell
        bx1 = xlo + (cells[:, 0].max() + 1) * cell
        by0 = ylo + cells[:, 1].min() * cell
        by1 = ylo + (cells[:, 1].max() + 1) * cell
        results.append({"area_cu2": area, "box": ((bx0, by0), (bx1, by1)),
                        "ncells": len(cells)})
    results.sort(key=lambda r: -r["area_cu2"])
    return results, cell


def count_stages(cfg, s):
    """Replay the REAL pipeline stages on the full raw cloud and return each
    stage's point array, so we can count how many land in any box at each
    stage and see exactly where the dormer points die."""
    raw, colors = load_xyz_rgb(cfg["cloud_path"])
    stages = {"raw": raw}
    p, m = crop_box(raw, cfg["crop_min"], cfg["crop_max"]); c = colors[m]
    stages["crop"] = p
    p2, m2 = height_cutoff(p, cfg["z_min"]); c = c[m2]
    stages["height"] = p2
    p3, m3 = color_filter(p2, c, exg_max=cfg["exg_max"]); c = c[m3]
    stages["color"] = p3
    radius = cfg["radius_mult"] * s
    p4, m4 = planarity_filter(p3, radius=radius, score_max=cfg["score_max"])
    stages["planarity"] = p4
    return stages


def mode_dormer(cfg, roof, s):
    print(f"\n=== Task 2: dormer fork ===")
    holes, cell = detect_holes(roof, s)
    print(f"hole-detection occupancy cell = {cell:.4f} cu; "
          f"{len(holes)} enclosed holes above 0.10 cu^2:")
    for i, h in enumerate(holes):
        (bx0, by0), (bx1, by1) = h["box"]
        print(f"  hole {i}: area {h['area_cu2']:.3f} cu^2  "
              f"X[{bx0:.2f},{bx1:.2f}] Y[{by0:.2f},{by1:.2f}]")

    # roof Z band we treat as 'the roof surface' in the raw cloud
    zlo, zhi = cfg["z_min"], cfg["crop_max"][2]

    # Replay the real pipeline once; count in each hole box + the clean box.
    stages = count_stages(cfg, s)
    roof_band = stages["raw"][(stages["raw"][:, 2] >= zlo) &
                              (stages["raw"][:, 2] <= zhi)]

    def density(p, box):
        (xlo, ylo), (xhi, yhi) = box
        area = (xhi - xlo) * (yhi - ylo)
        n = int(in_box(p, box).sum())
        return n, area, (n / area if area else 0.0)

    # baseline: clean main-roof patch density in the RAW roof band
    n_c, a_c, dens_c = density(roof_band, CLEAN_BOX)
    print(f"\nRAW roof-band density on CLEAN main-roof patch: "
          f"{n_c:,} pts / {a_c:.3f} cu^2 = {dens_c:,.0f} pts/cu^2")

    print(f"\nper-dormer RAW roof-band density vs clean patch:")
    print(f"{'hole':>4} {'area_cu2':>9} {'raw_pts':>9} {'dens':>10} {'ratio_to_clean':>15}")
    for i, h in enumerate(holes):
        n_d, a_d, dens_d = density(roof_band, h["box"])
        print(f"{i:>4} {h['area_cu2']:>9.3f} {n_d:>9,} {dens_d:>10,.0f} "
              f"{dens_d/dens_c if dens_c else 0:>15.3f}")

    # per-stage loss trace: for each hole box, how many points survive each
    # pipeline stage. The stage where the count collapses is where the dormer
    # surface is lost.
    print(f"\nper-stage point counts inside each hole box "
          f"(raw counts use the roof Z band):")
    hdr = f"{'hole':>4} " + " ".join(f"{k:>10}" for k in
            ["raw_band", "crop", "height", "color", "planarity", "roof.npy"])
    print(hdr)
    for i, h in enumerate(holes):
        row = [int(in_box(roof_band, h["box"]).sum())]
        for k in ["crop", "height", "color", "planarity"]:
            row.append(int(in_box(stages[k], h["box"]).sum()))
        row.append(int(in_box(roof, h["box"]).sum()))
        print(f"{i:>4} " + " ".join(f"{v:>10,}" for v in row))

    # same trace for the clean patch, as the 'healthy surface' control
    print(f"\nsame trace for the CLEAN patch (control, should stay dense):")
    row = [int(in_box(roof_band, CLEAN_BOX).sum())]
    for k in ["crop", "height", "color", "planarity"]:
        row.append(int(in_box(stages[k], CLEAN_BOX).sum()))
    row.append(int(in_box(roof, CLEAN_BOX).sum()))
    print(f"{'clean':>4} " + " ".join(f"{v:>10,}" for v in row))


# --------------------------------------------------------------------------
# Task 2 (clean version): isolate the TRUE dormer footprints via the real
# segmentation residual, then the dormer fork.
# --------------------------------------------------------------------------
def mode_residual(cfg, roof, s):
    # add scripts/ import path for recon_common (same dir as this file)
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from recon_common import discover_facets
    from roofkit.segment import assign_to_planes

    print(f"\n=== Task 2 (residual): true dormer footprints ===")
    facets, band, s_full = discover_facets(roof, cfg)
    print(f"segmentation: {len(facets)} accepted facets, band {band:.4f} cu")
    owner, dist = assign_to_planes(roof, facets, max_dist=np.inf)
    residual = roof[dist > band]  # roof points no accepted facet explains
    print(f"residual (roof.npy points beyond band of every accepted facet): "
          f"{len(residual):,} pts = {100*len(residual)/len(roof):.1f}% of roof.npy")
    print("  (these points ARE in roof.npy by construction -> they survived "
          "crop/height/color/planarity; only segmentation dropped them)")

    # grid both roof.npy and the residual to the coverage cell size
    cell = 2.5 * s_full
    x, y = roof[:, 0], roof[:, 1]
    xlo, xhi, ylo, yhi = x.min(), x.max(), y.min(), y.max()
    nx = int((xhi - xlo) / cell) + 1
    ny = int((yhi - ylo) / cell) + 1
    rng = [[xlo, xhi], [ylo, yhi]]
    Hall, xe, ye = np.histogram2d(x, y, bins=[nx, ny], range=rng)
    Hres, _, _ = np.histogram2d(residual[:, 0], residual[:, 1],
                               bins=[nx, ny], range=rng)
    building = Hall >= 2
    interior = binary_erosion(building, iterations=1)   # kill perimeter fringe
    res_cells = (Hres >= 2) & interior                  # dormer/clutter cells
    print(f"coverage cell {cell:.4f} cu; building cells {building.sum():,}; "
          f"interior residual cells {int(res_cells.sum()):,}")

    # connected residual blobs = candidate dormers
    lab, n = label(res_cells)
    blobs = []
    for i in range(1, n + 1):
        cells = np.argwhere(lab == i)
        area = len(cells) * cell * cell
        if area < 0.15:                                 # ignore thin edge lines
            continue
        bx0 = xlo + cells[:, 0].min() * cell; bx1 = xlo + (cells[:, 0].max()+1)*cell
        by0 = ylo + cells[:, 1].min() * cell; by1 = ylo + (cells[:, 1].max()+1)*cell
        blobs.append({"area": area, "cells": cells,
                     "box": ((bx0, by0), (bx1, by1))})
    blobs.sort(key=lambda b: -b["area"])
    print(f"{len(blobs)} interior residual blobs above 0.15 cu^2 (dormers):")
    for i, b in enumerate(blobs):
        (bx0, by0), (bx1, by1) = b["box"]
        print(f"  blob {i}: area {b['area']:.2f} cu^2  "
              f"X[{bx0:.1f},{bx1:.1f}] Y[{by0:.1f},{by1:.1f}]")

    # RAW roof-band density, computed on the ACTUAL residual cells (not a
    # bounding box), vs the covered main-roof cells. This is the fork test.
    raw, _ = load_xyz_rgb(cfg["cloud_path"])
    zlo, zhi = cfg["z_min"], cfg["crop_max"][2]
    band_pts = raw[(raw[:, 2] >= zlo) & (raw[:, 2] <= zhi)]
    Hraw, _, _ = np.histogram2d(band_pts[:, 0], band_pts[:, 1],
                               bins=[nx, ny], range=rng)
    covered = building & interior & ~(Hres >= 2)        # healthy main roof
    dorm_cell_raw = Hraw[res_cells]                      # per-cell raw counts
    clean_cell_raw = Hraw[covered]
    print(f"\nFORK TEST  RAW roof-band points per {cell:.4f} cu cell:")
    print(f"  dormer (residual) cells : median {np.median(dorm_cell_raw):.0f}, "
          f"mean {dorm_cell_raw.mean():.0f}  ({int(res_cells.sum()):,} cells)")
    print(f"  clean main-roof cells   : median {np.median(clean_cell_raw):.0f}, "
          f"mean {clean_cell_raw.mean():.0f}  ({int(covered.sum()):,} cells)")
    print(f"  density ratio (dormer/clean, medians): "
          f"{np.median(dorm_cell_raw)/max(np.median(clean_cell_raw),1):.2f}")

    # per-blob raw density
    print(f"\nper-dormer-blob RAW roof-band density vs clean median:")
    clean_med = np.median(clean_cell_raw)
    for i, b in enumerate(blobs):
        cc = b["cells"]
        vals = Hraw[cc[:, 0], cc[:, 1]]
        print(f"  blob {i}: area {b['area']:.2f} cu^2  raw/cell median "
              f"{np.median(vals):.0f}  ratio {np.median(vals)/max(clean_med,1):.2f}")

    # plan-view: gray = covered main roof, red = residual dormer cells
    img = np.zeros((nx, ny, 3))
    img[covered] = [0.6, 0.6, 0.6]
    img[res_cells] = [0.9, 0.1, 0.1]
    fig, ax = plt.subplots(figsize=(9, 11))
    ax.imshow(np.transpose(img, (1, 0, 2)), origin="lower",
              extent=[xlo, xhi, ylo, yhi], aspect="equal")
    ax.set_title("segmentation residual (red) over covered main roof (gray)")
    ax.set_xlabel("X (cu)"); ax.set_ylabel("Y (cu)")
    ax.set_xticks(np.arange(np.ceil(xlo), xhi, 1.0))
    ax.set_yticks(np.arange(np.ceil(ylo), yhi, 1.0))
    ax.grid(True, color="white", alpha=0.3, linewidth=0.3)
    fig.tight_layout(); p = OUT / "task2_residual_map.png"
    fig.savefig(p, dpi=120); print(f"\n  wrote {p}")


# --------------------------------------------------------------------------
# GATE (before coverage code): does dormer plan area already fall inside the
# alpha-shape surface whose area an accepted facet already sums? If yes,
# adding dormer facets double-counts and the area-ownership rule is required
# BEFORE any summation. If no, the alpha shape already leaves the holes open.
# --------------------------------------------------------------------------
def _plane_basis(normal, centroid):
    """The SAME in-plane basis roofkit.measure.project_to_plane builds, so a
    query point projects into the identical (u,v) frame as the facet points."""
    n = np.asarray(normal, float); n = n / np.linalg.norm(n)
    helper = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(n, helper); u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    return n, u, v, np.asarray(centroid, float)


def _facet_kept_alpha(pts, normal, alpha):
    """Replicate facet_area's kept-triangle set and return the Delaunay in
    (u,v), the kept-triangle mask, and the basis, so we can ask 'is this XY
    location inside the counted surface?'."""
    from scipy.spatial import Delaunay
    centroid = pts.mean(axis=0)
    n, u, v, c = _plane_basis(normal, centroid)
    uv = np.column_stack([(pts - c) @ u, (pts - c) @ v])
    tri = Delaunay(uv)
    s = tri.simplices
    a, b, cc = uv[s[:, 0]], uv[s[:, 1]], uv[s[:, 2]]
    ab, ac, bc = b - a, cc - a, cc - b
    area = np.abs(ab[:, 0]*ac[:, 1] - ab[:, 1]*ac[:, 0]) / 2.0
    la, lb, lc = (np.linalg.norm(bc, axis=1), np.linalg.norm(ac, axis=1),
                 np.linalg.norm(ab, axis=1))
    with np.errstate(divide="ignore", invalid="ignore"):
        R = np.where(area > 1e-15, la*lb*lc/(4.0*area), np.inf)
    return tri, (R <= alpha), (n, u, v, c)


def _covered_by_facet(qxy, tri, kept, basis):
    """Boolean per query XY point: does it land on a KEPT alpha triangle of
    this facet? Lift XY onto the facet plane, project to (u,v), find the
    containing simplex, check it is kept."""
    n, u, v, c = basis
    x, y = qxy[:, 0], qxy[:, 1]
    # z on the facet plane for each (x,y): n . (P - c) = 0
    z = c[2] - (n[0]*(x - c[0]) + n[1]*(y - c[1])) / n[2]
    P = np.column_stack([x, y, z]) - c
    uv = np.column_stack([P @ u, P @ v])
    simp = tri.find_simplex(uv)
    out = np.zeros(len(qxy), bool)
    inside = simp >= 0
    out[inside] = kept[simp[inside]]
    return out


def mode_doublecheck(cfg, roof, s):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from recon_common import discover_facets
    from roofkit.segment import assign_to_planes

    print(f"\n=== GATE: dormer/main-facet area double-count check ===")
    facets, band, s_full = discover_facets(roof, cfg)
    owner, dist = assign_to_planes(roof, facets, max_dist=np.inf)
    residual = roof[dist > band]

    # interior residual cells (same construction as mode_residual)
    cell = 2.5 * s_full
    x, y = roof[:, 0], roof[:, 1]
    xlo, xhi, ylo, yhi = x.min(), x.max(), y.min(), y.max()
    nx = int((xhi-xlo)/cell)+1; ny = int((yhi-ylo)/cell)+1
    rng2 = [[xlo, xhi], [ylo, yhi]]
    Hall, _, _ = np.histogram2d(x, y, bins=[nx, ny], range=rng2)
    Hres, _, _ = np.histogram2d(residual[:, 0], residual[:, 1], bins=[nx, ny], range=rng2)
    building = Hall >= 2
    interior = binary_erosion(building, iterations=1)
    res_cells = (Hres >= 2) & interior
    ij = np.argwhere(res_cells)
    qxy = np.column_stack([xlo + (ij[:, 0]+0.5)*cell, ylo + (ij[:, 1]+0.5)*cell])
    print(f"{len(qxy):,} interior residual cells "
          f"({len(qxy)*cell*cell:.1f} cu^2 plan) to test against facet extents")

    # per facet: build the kept alpha surface exactly as the area step does
    rng = np.random.default_rng(0)
    covered = np.zeros(len(qxy), bool)
    for k, f in enumerate(facets):
        pts = f["points"]
        if len(pts) > 400_000:
            pts = pts[rng.choice(len(pts), 400_000, replace=False)]
        s_f = median_nn_spacing(pts)
        tri, kept, basis = _facet_kept_alpha(pts, f["normal"], cfg["alpha_mult"]*s_f)
        covered |= _covered_by_facet(qxy, tri, kept, basis)
    frac = covered.mean()
    print(f"\ninterior residual cells inside SOME accepted facet's counted "
          f"alpha surface: {covered.sum():,} / {len(qxy):,} = {100*frac:.1f}%")
    print(f"  plan area double-counted: {covered.sum()*cell*cell:.2f} cu^2 "
          f"of {len(qxy)*cell*cell:.2f} cu^2 residual")

    # per-blob: is the OVERLAP concentrated in thin edge strips, or do the
    # real (large) dormer blobs themselves sit inside a host facet's area?
    lab, nlab = label(res_cells)
    cov_grid = np.zeros_like(res_cells)      # mark which cells came back covered
    cov_grid[ij[:, 0], ij[:, 1]] = covered
    blobs = []
    for i in range(1, nlab + 1):
        cells = np.argwhere(lab == i)
        area = len(cells) * cell * cell
        if area < 0.15:
            continue
        cov = cov_grid[cells[:, 0], cells[:, 1]].mean()
        bx0 = xlo + cells[:, 0].min()*cell; by0 = ylo + cells[:, 1].min()*cell
        blobs.append((area, cov, bx0, by0))
    blobs.sort(key=lambda b: -b[0])
    print(f"\nper interior blob (>=0.15 cu^2): overlap with host-facet area")
    print(f"{'area_cu2':>9} {'covered%':>9}  location")
    for area, cov, bx0, by0 in blobs:
        print(f"{area:>9.2f} {100*cov:>8.0f}%  X~{bx0:.0f} Y~{by0:.0f}")
    if frac < 0.05:
        print("  -> VERDICT: alpha shape already leaves dormer holes OPEN; "
              "adding dormer facets does NOT double-count.")
    elif frac > 0.5:
        print("  -> VERDICT: dormer footprints ARE inside host-facet area; "
              "the area-ownership rule is REQUIRED before summation.")
    else:
        print("  -> VERDICT: partial overlap; ownership rule needed, "
              "magnitude bounded by the number above.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--mode", default="explore",
                    choices=["explore", "spacing", "dormer", "residual",
                             "doublecheck"])
    args = ap.parse_args()
    cfg = load_config(args.dataset)

    roof = np.load(cfg["roof_path"])
    print("=== roof.npy (fully isolated roof) ===")
    bounds("roof.npy", roof)
    s = median_nn_spacing(roof)
    print(f"median nn spacing (whole roof.npy): {s:.4f} cu")

    if args.mode == "explore":
        cell = 4.0 * s
        # binary occupancy view (occupied=yellow, empty=purple) reveals holes
        x, y = roof[:, 0], roof[:, 1]
        nx = int((x.max()-x.min())/cell)+1; ny = int((y.max()-y.min())/cell)+1
        H, _, _ = np.histogram2d(x, y, bins=[nx, ny])
        fig, ax = plt.subplots(figsize=(9, 11))
        ax.imshow((H >= 2).T, origin="lower",
                  extent=[x.min(), x.max(), y.min(), y.max()],
                  aspect="equal", cmap="viridis")
        ax.set_title("roof.npy occupancy (purple = empty; dormers = interior gaps)")
        ax.set_xlabel("X (cu)"); ax.set_ylabel("Y (cu)")
        ax.set_xticks(np.arange(np.ceil(x.min()), x.max(), 1.0))
        ax.set_yticks(np.arange(np.ceil(y.min()), y.max(), 1.0))
        ax.grid(True, color="white", alpha=0.3, linewidth=0.3)
        fig.tight_layout(); p = OUT / "explore_occupancy.png"
        fig.savefig(p, dpi=120); print(f"  wrote {p}")
    elif args.mode == "spacing":
        mode_spacing(cfg, roof, s)
    elif args.mode == "dormer":
        mode_dormer(cfg, roof, s)
    elif args.mode == "residual":
        mode_residual(cfg, roof, s)
    elif args.mode == "doublecheck":
        mode_doublecheck(cfg, roof, s)


if __name__ == "__main__":
    main()
