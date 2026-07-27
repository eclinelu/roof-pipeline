# VISUAL REVIEW RENDERER. Draws the pipeline's answer on top of a photograph
# of the roof, so Emmett can judge it by eye.
#
#   .venv/Scripts/python.exe -u scripts/review_render.py C:/odm/datasets/big_house
#
# Writes (standing rule R2):
#   reports/big_house/review/<stamp>/overview.png        whole building
#   reports/big_house/review/<stamp>/facet-NN.png        one per facet
#   reviews/big_house/review-<stamp>.json                the verdict template
#
# SIDE ARTIFACTS ONLY. This module reads the canonical state and draws it. It
# fits nothing, changes no threshold, and writes nothing the pipeline reads.
# canonical-2026-07-26-r2 remains canonical; published coverage remains 88.40 pct.
#
# ---------------------------------------------------------------------------
# WHY THE BACKGROUND IS THE POINT CLOUD'S OWN COLOUR AND NOT AN ORTHOPHOTO
# (decision 2026-07-27, Emmett)
#
# ODM never produced an orthophoto for this dataset: the pipeline stops at
# odm_georeferencing, and odm_orthophoto runs after that. The two ways to get a
# photographic base were to re-run ODM through the orthophoto stage, or to
# rasterise the colour the point cloud already carries.
#
# The cloud's own colour wins, and the reason is registration. An orthophoto
# arrives in UTM; every facet number in this project lives in the LEVELED frame,
# which is UTM rotated by 1.083 degrees. Aligning the two is a step that can be
# wrong, and a background that is subtly misaligned would make correct facets
# look wrong and wrong facets look right. The reviewer would be reviewing the
# overlay instead of the roof. Rasterising the cloud's own colour and levelling
# it with the SAME rotation applied to the points means the background and the
# outlines are the same data in the same frame BY CONSTRUCTION. There is nothing
# to align and therefore nothing to misalign.
#
# The cost is that capture holes read as holes rather than being interpolated
# away. For this purpose that is information: a hole is the pipeline showing
# where it had nothing to work with.
#
# WHAT IS DRAWN, AND WHY EACH THING IS THERE
#   facet outlines, numbered, with pitch and plan area   what the pipeline claims
#   ridge / valley / hip lines from plane intersections  whether the claimed
#                                                        surfaces meet where the
#                                                        real roof creases
#   eave: free boundary with no neighbouring facet       where the roof is
#                                                        claimed to end
#   footprint cells no facet explains                    THE PIPELINE SAYING
#                                                        WHERE IT FAILED. This is
#                                                        the layer that found the
#                                                        blob 0 fringe.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.ndimage import (binary_dilation, binary_erosion, binary_fill_holes,
                           label)

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                            # noqa: E402
from canonical import load_canonical, scalar                      # noqa: E402
from roofkit.io import load_xyz_rgb                               # noqa: E402
from roofkit.segment import level_cloud                           # noqa: E402
from roofkit.measure import up_from_tilt, plane_intersection      # noqa: E402
from roofkit import coverage as cov                               # noqa: E402
from review_ui import build_review_html                           # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"
RASTER_MULT = 2.0        # colour raster cell = RASTER_MULT x point spacing
NEAR_CELLS = 3           # facets this close in plan count as neighbours
RIDGE_MAX_TILT_DEG = 12.0   # an intersection line flatter than this is a ridge
                            # or valley; steeper is a hip or a rake

# Colours chosen to sit on a photograph: saturated, and none of them roof-brown.
C_OUTLINE = "#00e5ff"
# Two failure layers, deliberately different in hue as well as in lightness so
# they are distinguishable at a glance and in greyscale. Both are drawn UNDER
# the outlines and kept light: on the first render a single layer at 0.55 alpha
# made close-ups read as mostly magenta.
C_SEG_GAP = (1.0, 0.10, 0.50)      # segmentation: real roof, no facet
A_SEG_GAP = 0.38
C_CAP_GAP = (0.20, 0.65, 1.0)      # capture: nothing could have been fitted
A_CAP_GAP = 0.22
C_RIDGE = "#ffd400"
C_VALLEY = "#00ff88"
C_HIP = "#ff8c00"
C_EAVE = "#ffffff"


def leveled_rgb_raster(cfg, doc, spacing, pad=1.0):
    """Top-down colour image of the roof, from the point cloud's own RGB.

    Highest point per cell wins, which is what a camera looking straight down
    would see. Built in the LEVELED frame, using the same rotation applied to
    the analysis points, so it needs no registration to the facets."""
    pts, cols = load_xyz_rgb(cfg["cloud_path"])
    lo = np.asarray(cfg["crop_min"], float) - pad
    hi = np.asarray(cfg["crop_max"], float) + pad
    m = np.all((pts >= lo) & (pts <= hi), axis=1)
    pts, cols = pts[m], cols[m]
    if cfg["level_tilt_deg"] is not None:
        pts = level_cloud(pts, up_from_tilt(cfg["level_tilt_deg"],
                                            cfg["level_uphill_az_deg"]))
    cell = RASTER_MULT * spacing
    xlo, ylo = pts[:, 0].min(), pts[:, 1].min()
    nx = int((pts[:, 0].max() - xlo) / cell) + 1
    ny = int((pts[:, 1].max() - ylo) / cell) + 1
    i = np.clip(((pts[:, 0] - xlo) / cell).astype(np.int64), 0, nx - 1)
    j = np.clip(((pts[:, 1] - ylo) / cell).astype(np.int64), 0, ny - 1)
    # Sort by height ASCENDING and scatter: the last write into each cell is
    # the highest point, so the top surface wins without a per-cell loop.
    order = np.argsort(pts[:, 2], kind="stable")
    img = np.zeros((nx, ny, 3), dtype=np.float32)
    hit = np.zeros((nx, ny), dtype=bool)
    img[i[order], j[order]] = cols[order]
    hit[i[order], j[order]] = True
    return dict(img=img, hit=hit, xlo=float(xlo), ylo=float(ylo),
                cell=float(cell), nx=nx, ny=ny, n_points=int(len(pts)))


def to_image(arr):
    """Grid indexed (i=x, j=y) -> image (row = y increasing UP, col = x), so
    the picture reads like a map."""
    return np.flipud(np.swapaxes(arr, 0, 1))


def extent_of(r):
    return [r["xlo"], r["xlo"] + r["nx"] * r["cell"],
            r["ylo"], r["ylo"] + r["ny"] * r["cell"]]


def facet_occupancy(pts_xy, g):
    H, _, _ = np.histogram2d(
        pts_xy[:, 0], pts_xy[:, 1], bins=[g["nx"], g["ny"]],
        range=[[g["xlo"], g["xlo"] + g["nx"] * g["cell"]],
               [g["ylo"], g["ylo"] + g["ny"] * g["cell"]]])
    # Fill holes for the OUTLINE only. Sparse capture leaves a facet's mask
    # speckled, and contouring that draws a scribble around every gap instead
    # of the facet's boundary. This is display only; no area is taken from it
    # without saying so (and the hole-filling rule is the same one the
    # footprint denominator uses, decision 2026-07-26).
    return binary_fill_holes(H >= 1)


def classify_intersection(fa, fb, seg_pts):
    """Ridge, valley or hip, from geometry rather than from a label somebody
    typed. At a point on the shared line, step a little way into each facet
    and ask whether that facet's surface goes DOWN (the line is a local high:
    a ridge) or UP (a local low: a valley). The line's tilt then separates a
    level ridge from a sloping hip."""
    p0 = seg_pts.mean(axis=0)
    d = seg_pts[-1] - seg_pts[0]
    d = d / max(np.linalg.norm(d), 1e-12)
    tilt = abs(np.degrees(np.arcsin(np.clip(d[2], -1, 1))))
    downs = []
    for f in (fa, fb):
        n = np.asarray(f["normal"], float); n = n / np.linalg.norm(n)
        if n[2] < 0:
            n = -n
        c = f["points"].mean(axis=0)
        # step into this facet, perpendicular to the line, in plan
        toward = c - p0
        toward[2] = 0.0
        perp = toward - (toward @ d) * d
        ln = np.linalg.norm(perp)
        if ln < 1e-9:
            return None
        perp = perp / ln
        step = p0 + perp * (5.0 * np.linalg.norm(seg_pts[-1] - seg_pts[0]) / 100.0
                            + 1e-6)
        z_here = c[2] - (n[0] * (p0[0] - c[0]) + n[1] * (p0[1] - c[1])) / n[2]
        z_step = c[2] - (n[0] * (step[0] - c[0]) + n[1] * (step[1] - c[1])) / n[2]
        downs.append(z_step < z_here)
    if all(downs):
        return "hip" if tilt > RIDGE_MAX_TILT_DEG else "ridge"
    if not any(downs):
        return "valley"
    return None            # one up one down: a step or a shed junction


def build_lines(facets, occ, g, spacing):
    """Every pair of facets that are adjacent IN PLAN gets its plane
    intersection computed, clipped to the stretch where both facets actually
    have points, and classified."""
    lines = []
    dil = [binary_dilation(o, iterations=NEAR_CELLS) for o in occ]
    for a in range(len(facets)):
        for b in range(a + 1, len(facets)):
            if not (dil[a] & dil[b]).any():
                continue
            fa, fb = facets[a], facets[b]
            r = plane_intersection(fa["normal"], fa["points"].mean(axis=0),
                                   fb["normal"], fb["points"].mean(axis=0))
            if r is None:
                continue
            p0, d = r
            # Sample the line and keep only where BOTH facets are present, so
            # the drawn segment is the crease that exists rather than the
            # infinite line where two planes happen to meet.
            #
            # span must be a PER-AXIS extent. np.ptp over an (N, 2) block
            # returns the range across BOTH columns at once, and in UTM that is
            # northing minus easting, about 4 million cloud units. Sampling
            # +/- that put every sample off the building and produced zero
            # lines on the first run.
            span = max(np.ptp(f["points"][:, ax])
                       for f in (fa, fb) for ax in (0, 1))
            t = np.linspace(-span, span, 2400)
            P = p0[None, :] + t[:, None] * d[None, :]
            i = np.clip(((P[:, 0] - g["xlo"]) / g["cell"]).astype(np.int64),
                        0, g["nx"] - 1)
            j = np.clip(((P[:, 1] - g["ylo"]) / g["cell"]).astype(np.int64),
                        0, g["ny"] - 1)
            ok = dil[a][i, j] & dil[b][i, j]
            if ok.sum() < 10:
                continue
            # longest contiguous run of ok, so two facets meeting in two
            # separate places do not get one line drawn across the gap
            lab, n = label(ok)
            if n == 0:
                continue
            sizes = np.bincount(lab)[1:]
            k = int(np.argmax(sizes)) + 1
            seg = P[lab == k]
            if len(seg) < 10:
                continue
            kind = classify_intersection(fa, fb, seg)
            if kind is None:
                continue
            lines.append(dict(a=a, b=b, kind=kind,
                              xy=seg[:, :2], length_cu=float(
                                  np.linalg.norm(seg[-1] - seg[0]))))
    return lines


def eave_cells(occ, g):
    """Boundary cells of each facet with no other facet nearby: the outer edge
    of the roof as the pipeline understands it."""
    dil = [binary_dilation(o, iterations=NEAR_CELLS) for o in occ]
    others = np.zeros_like(occ[0])
    out = []
    for k, o in enumerate(occ):
        others[:] = False
        for m, dm in enumerate(dil):
            if m != k:
                others |= dm
        bd = o & ~binary_erosion(o, iterations=1)
        out.append(bd & ~others)
    return out


def scale_bar(ax, extent, ft_per_cu, in_per_cu, frac=0.18):
    x0, x1, y0, y1 = extent
    w, h = x1 - x0, y1 - y0
    target = (w * ft_per_cu) * frac
    bar_ft = min([1, 2, 5, 10, 20, 25, 50, 100],
                 key=lambda v: abs(v - target))
    bar_cu = bar_ft / ft_per_cu
    bx, by = x1 - 0.05 * w - bar_cu, y0 + 0.045 * h
    ax.plot([bx, bx + bar_cu], [by, by], color="white", lw=6,
            solid_capstyle="butt", zorder=20)
    ax.plot([bx, bx + bar_cu], [by, by], color="black", lw=3,
            solid_capstyle="butt", zorder=21)
    ax.text(bx + bar_cu / 2, by + 0.015 * h, f"{bar_ft} ft", ha="center",
            va="bottom", fontsize=13, fontweight="bold", color="white",
            zorder=22,
            path_effects=_stroke())


def north_arrow(ax, extent):
    x0, x1, y0, y1 = extent
    w, h = x1 - x0, y1 - y0
    nx_, ny_ = x1 - 0.045 * w, y1 - 0.20 * h
    ax.annotate("", xy=(nx_, ny_ + 0.10 * h), xytext=(nx_, ny_),
                arrowprops=dict(arrowstyle="-|>", lw=3, color="white",
                                mutation_scale=24), zorder=20)
    ax.text(nx_, ny_ + 0.115 * h, "N", fontsize=17, fontweight="bold",
            ha="center", va="bottom", color="white", zorder=21,
            path_effects=_stroke())


def _stroke(lw=3):
    import matplotlib.patheffects as pe
    return [pe.withStroke(linewidth=lw, foreground="black")]


def prepare_overlays(occ, eaves, seg_gap, cap_gap, raster, g):
    """Build every layer ONCE, in world coordinates, so each of the 30 figures
    only has to plot arrays.

    This is not a micro-optimisation. The first version rebuilt a 190 MB RGBA
    overlay and ran 29 contour calls over a 6-million-cell grid inside EVERY
    figure, 30 times over, and the run died with a MemoryError partway through
    the close-ups. Contours and masks do not change between figures, so they
    are computed here and reused."""
    import matplotlib.pyplot as plt
    gext = [g["xlo"], g["xlo"] + g["nx"] * g["cell"],
            g["ylo"], g["ylo"] + g["ny"] * g["cell"]]

    # facet outlines, extracted once as polylines in world coordinates
    scratch = plt.figure()
    sax = scratch.add_subplot(111)
    outlines = []
    for o in occ:
        cs = sax.contour(to_image(o).astype(np.float32), levels=[0.5],
                         extent=gext, origin="upper")
        segs = [np.asarray(p.vertices) for c in cs.collections
                for p in c.get_paths()] if hasattr(cs, "collections") \
            else [np.asarray(v) for v in cs.allsegs[0]]
        outlines.append(segs)
        sax.clear()
    plt.close(scratch)

    # Both failure layers in one RGBA image: they are disjoint by
    # construction, so one array holds both and costs one imshow.
    sg, cg = to_image(seg_gap), to_image(cap_gap)
    rgba = np.zeros(sg.shape + (4,), dtype=np.float32)
    rgba[cg] = (*C_CAP_GAP, A_CAP_GAP)
    rgba[sg] = (*C_SEG_GAP, A_SEG_GAP)

    eave_xy = []
    for e in eaves:
        ij = np.argwhere(e)
        eave_xy.append(np.column_stack([
            g["xlo"] + (ij[:, 0] + 0.5) * g["cell"],
            g["ylo"] + (ij[:, 1] + 0.5) * g["cell"]]) if len(ij)
            else np.zeros((0, 2)))

    img = to_image(raster["img"]).copy()
    img[to_image(~raster["hit"])] = 0.10          # no data reads as near-black
    return dict(gext=gext, outlines=outlines, rgba=rgba, eave_xy=eave_xy,
                img=np.clip(img, 0, 1), ext=extent_of(raster))


def draw(ax, ov, lines, facets, rows, label_ids, highlight=None,
         label_lines=True):
    """One panel: photo, then every prebuilt overlay on top of it."""
    ax.imshow(ov["img"], extent=ov["ext"], interpolation="nearest",
              origin="upper", zorder=0)
    # the pipeline's own failure map, first so outlines sit on top of it
    ax.imshow(ov["rgba"], extent=ov["gext"], interpolation="nearest",
              origin="upper", zorder=2)
    for k, segs in enumerate(ov["outlines"]):
        hl = (highlight is not None and k == highlight)
        for s in segs:
            ax.plot(s[:, 0], s[:, 1], "-",
                    color="#ff2d95" if hl else C_OUTLINE,
                    lw=3.2 if hl else 1.6, zorder=8 if hl else 4)
    for xy in ov["eave_xy"]:
        if len(xy):
            ax.plot(xy[:, 0], xy[:, 1], ".", color=C_EAVE, ms=0.7, zorder=5,
                    alpha=0.6)
    for ln in lines:
        c = dict(ridge=C_RIDGE, valley=C_VALLEY, hip=C_HIP)[ln["kind"]]
        ax.plot(ln["xy"][:, 0], ln["xy"][:, 1], "-", color=c, lw=2.6, zorder=6,
                path_effects=_stroke(4.5))
        if label_lines:
            # An id at the line's midpoint. Without it a line cannot be given
            # a verdict: "line 7 is misplaced" needs a 7 on the picture.
            mid = ln["xy"][len(ln["xy"]) // 2]
            ax.text(mid[0], mid[1], f"L{ln['id']}", fontsize=8.5,
                    fontweight="bold", color=c, ha="center", va="center",
                    zorder=11, path_effects=_stroke(3),
                    bbox=dict(boxstyle="round,pad=0.18", fc="#000000bb",
                              ec=c, lw=1.0))

    if True:
        # The 8 main facets are large and have room for the full label. The 21
        # recovered facets are small and clustered along the ridge line, and
        # three-line labels on them collided into an unreadable pile on the
        # first run. They get a number badge; their pitch and area are in the
        # table beside the map and in their own close-up.
        for k in label_ids:
            r = rows[k]
            c = facets[k]["points"].mean(axis=0)
            big = r["kind"] == "main" or len(label_ids) == 1
            txt = (f"{k}\n{r['pitch_deg']:.1f}\u00b0\n{r['plan_ft2']:.0f} ft\u00b2"
                   if big else f"{k}")
            ax.text(c[0], c[1], txt, ha="center", va="center",
                    fontsize=10 if big else 9, fontweight="bold",
                    color="white", zorder=10, linespacing=1.15,
                    bbox=dict(boxstyle="round,pad=0.30" if big
                              else "circle,pad=0.22", fc="#000000cc",
                              ec=C_OUTLINE, lw=1.4))
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_aspect("equal")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name / "review" / args.stamp
    out.mkdir(parents=True, exist_ok=True)
    rev_dir = REPO / "reviews" / name
    rev_dir.mkdir(parents=True, exist_ok=True)

    doc, points, facets, cfg = load_canonical(args.dataset, CANONICAL_STAMP)
    spacing = scalar(doc, "spacing_cu")
    band = scalar(doc, "band_cu")
    cell = scalar(doc, "cell_cu")
    in_per_cu = 40.4541
    sc = REPO / "reports" / name / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])
    ft_per_cu = in_per_cu / 12.0
    ft2_per_cu2 = ft_per_cu ** 2
    n_main = doc["counts"]["n_main"]
    print(f"  {len(facets)} facets ({n_main} main), spacing {spacing:.6f} cu, "
          f"scale {in_per_cu} in/cu")

    # The colour raster costs a 21-million-point LAZ read and about five
    # minutes. It is a pure function of the cloud and the leveling, so it is
    # cached: re-running to adjust the DRAWING should not re-read the cloud.
    cache = REPO / "reports" / name / "review" / "rgb-raster.npz"
    if cache.exists():
        z = np.load(cache)
        raster = dict(img=z["img"], hit=z["hit"], xlo=float(z["xlo"]),
                      ylo=float(z["ylo"]), cell=float(z["cell"]),
                      nx=int(z["nx"]), ny=int(z["ny"]),
                      n_points=int(z["n_points"]))
        print(f"  colour raster loaded from cache ({cache.name})")
    else:
        print("  rasterising the cloud's own colour ...")
        raster = leveled_rgb_raster(cfg, doc, spacing)
        np.savez_compressed(cache, **raster)
        print(f"  cached to {cache.name}")
    print(f"    {raster['n_points']:,} coloured points -> "
          f"{raster['nx']} x {raster['ny']} cells at "
          f"{raster['cell']*in_per_cu:.2f} in/cell")

    # masks over ALL 29 facets: "unexplained" means no facet explains it
    masks, g, _, _ = cov.coverage_masks(points, facets, band, cell)

    # ---- THE MAGENTA SPLIT ------------------------------------------------
    # The first render drew ONE magenta layer over `footprint & ~explained`,
    # and its 950 ft^2 did not match the 33.68 cu^2 coverage reports as
    # unexplained. The two numbers are computed against DIFFERENT BASES, and
    # conflating them hides the distinction that matters most for what to do
    # next:
    #
    #   NO FACET, BUT TESTABLE      real roof with enough points to test, that
    #                               no facet claims. A SEGMENTATION failure.
    #                               This is the fringe finding.
    #   NO FACET, NOT TESTABLE      fewer than 2 points in the cell, or outside
    #                               the eroded interior. Nothing could have been
    #                               fitted here. A CAPTURE failure, and the only
    #                               fix is a reflight.
    #
    # A facet ringed by the first needs a segmentation fix. A facet ringed by
    # the second needs a different flight. They call for opposite responses, so
    # they get separate layers.
    a_cu2 = cell * cell
    interior_testable = masks["interior"] & masks["testable"]
    seg_gap = interior_testable & ~masks["explained"]          # LAYER A
    all_unassigned = masks["footprint"] & ~masks["explained"]
    cap_gap = all_unassigned & ~seg_gap                        # LAYER B
    # what layer B is made of, so it is not just a residue
    holes_gap = masks["filled"] & ~masks["explained"]
    ring_gap = (masks["footprint"] & ~masks["interior"] & ~masks["explained"])

    def f2(m):
        return float(m.sum()) * a_cu2 * ft2_per_cu2

    def c2(m):
        return float(m.sum()) * a_cu2

    recon = dict(
        note="reconciles the render's magenta against the coverage report. "
             "They differ because they are computed against different bases, "
             "not because either is wrong.",
        render_layer_A_segmentation_gap=dict(
            definition="interior AND testable AND not explained",
            cu2=round(c2(seg_gap), 4), ft2=round(f2(seg_gap), 1),
            equals_coverage_unexplained="this IS the 33.682 cu^2 that "
                                        "split_coverage reports as unexplained"),
        render_layer_B_capture_gap=dict(
            definition="everything else the old single layer covered: "
                       "filled holes (under 2 points, untestable) plus the "
                       "perimeter ring outside the eroded interior",
            cu2=round(c2(cap_gap), 4), ft2=round(f2(cap_gap), 1),
            of_which_filled_holes_cu2=round(c2(holes_gap), 4),
            of_which_perimeter_ring_cu2=round(c2(ring_gap), 4)),
        old_single_layer=dict(
            definition="filled footprint AND not explained, the first render",
            cu2=round(c2(all_unassigned), 4), ft2=round(f2(all_unassigned), 1)),
        bases=dict(
            filled_footprint_cu2=362.105, eroded_interior_cu2=352.707,
            density_testable_cu2=290.256, explained_cu2=256.574,
            coverage_unexplained_cu2=33.682))
    print(f"    LAYER A segmentation gap (testable, no facet): "
          f"{c2(seg_gap):8.3f} cu^2 = {f2(seg_gap):7.1f} ft^2")
    print(f"    LAYER B capture gap (untestable / ring):       "
          f"{c2(cap_gap):8.3f} cu^2 = {f2(cap_gap):7.1f} ft^2")
    print(f"      of which filled holes {c2(holes_gap):.3f} cu^2, "
          f"perimeter ring {c2(ring_gap):.3f} cu^2")
    print(f"    old single layer:                              "
          f"{c2(all_unassigned):8.3f} cu^2 = {f2(all_unassigned):7.1f} ft^2")

    occ = [facet_occupancy(np.asarray(f["points"])[:, :2], g) for f in facets]
    rows = []
    for k, f in enumerate(facets):
        cells_n = int(occ[k].sum())
        rows.append(dict(
            facet=k, kind=f["kind"],
            pitch_deg=float(f["pitch"]),
            n_points=int(len(f["points"])),
            quality=float(f["quality"]),
            plan_cu2=round(cells_n * cell * cell, 4),
            plan_ft2=round(cells_n * cell * cell * ft2_per_cu2, 1)))

    print("  computing ridge / valley / hip lines ...")
    lines = build_lines(facets, occ, g, spacing)
    # Stable ids, assigned once and used on the render, in the JSON and in the
    # review UI. Sorted by length so the id order is reproducible rather than
    # dependent on loop order.
    lines.sort(key=lambda l: -l["length_cu"])
    for n, ln in enumerate(lines):
        ln["id"] = n
    eaves = eave_cells(occ, g)
    kinds = {}
    for ln in lines:
        kinds[ln["kind"]] = kinds.get(ln["kind"], 0) + 1
    print(f"    {len(lines)} intersection lines: {kinds}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # ---- overview ---------------------------------------------------------
    # Map on the left, the full 29-row table on the right. The table is what
    # makes number-only badges acceptable: every facet's pitch and area is
    # still on the page, just not stacked on top of its neighbour's.
    fig = plt.figure(figsize=(22, 15), dpi=150)
    gs = fig.add_gridspec(1, 2, width_ratios=[3.05, 1.0], wspace=0.02)
    ax = fig.add_subplot(gs[0, 0])
    tax = fig.add_subplot(gs[0, 1]); tax.axis("off")
    ov = prepare_overlays(occ, eaves, seg_gap, cap_gap, raster, g)
    draw(ax, ov, lines, facets, rows, range(len(facets)))
    # Crop to the building plus a margin. The cloud extends well past the roof
    # into lawn and trees, and on the first run the roof occupied about a third
    # of the frame.
    fi, fj = np.nonzero(masks["footprint"])
    bx0 = g["xlo"] + fi.min() * g["cell"]; bx1 = g["xlo"] + (fi.max() + 1) * g["cell"]
    by0 = g["ylo"] + fj.min() * g["cell"]; by1 = g["ylo"] + (fj.max() + 1) * g["cell"]
    mg = 0.09 * max(bx1 - bx0, by1 - by0)
    ext = [bx0 - mg, bx1 + mg, by0 - mg, by1 + mg]
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    north_arrow(ax, ext); scale_bar(ax, ext, ft_per_cu, in_per_cu)

    hdr = f"{'id':>3}  {'kind':<9} {'pitch':>6} {'plan ft2':>9} {'quality':>7}"
    body = [hdr, "-" * len(hdr)]
    for r in rows:
        body.append(f"{r['facet']:>3}  {r['kind']:<9} "
                    f"{r['pitch_deg']:>5.1f}° {r['plan_ft2']:>9.0f} "
                    f"{r['quality']:>7.3f}")
    body.append("-" * len(hdr))
    body.append(f"{'':>3}  {'TOTAL':<9} {'':>6} "
                f"{sum(r['plan_ft2'] for r in rows):>9.0f}")
    body.append("")
    body.append("PLAN AREA, NOT SLOPE AREA. Do not compare")
    body.append("this total against the 3,559.3 ft2")
    body.append("deliverable: that is SLOPE area over the 8")
    body.append("main facets only. Plan is the shadow the")
    body.append("roof casts; slope is the surface a roofer")
    body.append("buys material for.")
    body.append("")
    body.append("plan area = hole-filled occupied cells,")
    body.append("the CURRENT definition. The candidate")
    body.append("fringe rule is NOT applied here.")
    body.append("")
    body.append("UNASSIGNED, SPLIT INTO ITS TWO CAUSES:")
    body.append(f"  segmentation gap {f2(seg_gap):>7.0f} ft2  (pink)")
    body.append("    real roof, testable, no facet claims it")
    body.append(f"  capture gap      {f2(cap_gap):>7.0f} ft2  (blue)")
    body.append("    under 2 points per cell, or outside the")
    body.append("    eroded interior. Nothing could be fitted")
    body.append("    here; only a reflight changes it.")
    body.append("")
    body.append("RIDGE / VALLEY / HIP LABELS ARE INFERRED")
    body.append("geometry, never validated. They are part")
    body.append("of what this review is judging, not a")
    body.append("reference to judge the facets against.")
    tax.text(0.0, 1.0, "\n".join(body), va="top", ha="left", fontsize=10.5,
             family="monospace", transform=tax.transAxes)
    handles = [
        plt.Line2D([], [], color=C_OUTLINE, lw=2, label="facet outline"),
        plt.Line2D([], [], color=C_RIDGE, lw=3, label="ridge"),
        plt.Line2D([], [], color=C_HIP, lw=3, label="hip / rake"),
        plt.Line2D([], [], color=C_VALLEY, lw=3, label="valley"),
        plt.Line2D([], [], color=C_EAVE, lw=0, marker=".", ms=9,
                   label="eave (free edge, no facet beyond)"),
        plt.Line2D([], [], color=C_SEG_GAP, lw=0, marker="s", ms=10,
                   label="SEGMENTATION gap: testable roof, no facet"),
        plt.Line2D([], [], color=C_CAP_GAP, lw=0, marker="s", ms=10,
                   label="CAPTURE gap: untestable, needs a reflight"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=11, framealpha=0.85,
              facecolor="#111111", edgecolor="#666666", labelcolor="white")
    ax.set_title(f"{name}: canonical-{CANONICAL_STAMP}, {len(facets)} facets "
                 f"on the cloud's own colour   ({args.stamp})\n"
                 f"DEVELOPMENT SITE. Side artifact, nothing adopted.",
                 fontsize=14)
    fig.tight_layout()
    fig.savefig(out / "overview.png", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out / 'overview.png'}")

    # ---- per-facet close-ups ---------------------------------------------
    for k, f in enumerate(facets):
        pts = np.asarray(f["points"])
        x0, x1 = pts[:, 0].min(), pts[:, 0].max()
        y0, y1 = pts[:, 1].min(), pts[:, 1].max()
        mx = max((x1 - x0), (y1 - y0)) * 0.22 + 0.3
        fig, ax = plt.subplots(figsize=(13, 11), dpi=150)
        draw(ax, ov, lines, facets, rows, [k], highlight=k)
        ax.set_xlim(x0 - mx, x1 + mx); ax.set_ylim(y0 - mx, y1 + mx)
        north_arrow(ax, [x0 - mx, x1 + mx, y0 - mx, y1 + mx])
        scale_bar(ax, [x0 - mx, x1 + mx, y0 - mx, y1 + mx], ft_per_cu,
                  in_per_cu)
        r = rows[k]
        nb = sorted({(ln["a"] if ln["b"] == k else ln["b"], ln["kind"])
                     for ln in lines if k in (ln["a"], ln["b"])})
        ax.set_title(
            f"{name} facet {k} ({r['kind']})   pitch {r['pitch_deg']:.2f} deg   "
            f"plan {r['plan_ft2']:.0f} ft^2   {r['n_points']:,} pts   "
            f"quality {r['quality']:.3f}\n"
            f"meets: " + (", ".join(f"{o} ({kd})" for o, kd in nb) or "nothing")
            + f"    ({args.stamp}, development site)", fontsize=12)
        fig.tight_layout()
        fig.savefig(out / f"facet-{k:02d}.png", facecolor="white")
        plt.close(fig)
    print(f"  wrote {len(facets)} per-facet close-ups")

    # ---- the verdict schema ----------------------------------------------
    # IDENTITY AND BOUNDARY ARE SEPARATE AXES (schema change 2026-07-27,
    # Emmett). The first schema had one `verdict` field, and on the overview
    # pass it collapsed two things that are coming apart in the data: most
    # facets are IDENTIFIED correctly while their OUTLINES are sometimes in the
    # wrong place. Under one field that is recorded as "correct" and the
    # boundary error disappears from the record entirely.
    tmpl = dict(
        review_of=f"canonical-{CANONICAL_STAMP}",
        dataset=name, date=args.stamp, reviewer="Emmett",
        schema_version=2,
        site_role=("DEVELOPMENT site. See "
                   "decisions/2026-07-27-development-vs-validation-split.md. "
                   "No accuracy claim comes from this site. Visual review may "
                   "establish THAT something is wrong and WHAT it is "
                   "physically; it may never set a parameter value."),
        renders=str(out.relative_to(REPO)).replace("\\", "/"),
        top_level_observations=[
            dict(observation="Most facets are IDENTIFIED correctly. The errors "
                             "are in LINE PLACEMENT, and they are NOT "
                             "systematic.",
                 by="Emmett", from_="overview pass, before the per-facet pass",
                 why_it_matters="non-systematic placement error points at the "
                                "segmentation boundary rather than at a global "
                                "parameter, and it rules out a whole class of "
                                "fixes before anyone proposes one: no single "
                                "threshold, offset or erosion width can "
                                "correct an error that is not consistent.")],
        instructions=dict(
            identity=dict(
                correct="this facet corresponds to one real roof plane",
                merge="this facet and another are ONE real plane split in two",
                split="this facet is TWO real planes fitted as one",
                spurious="no real roof plane here at all",
                unsure="cannot tell from the render"),
            boundary=dict(
                tight="outline follows the real roof edge",
                short="outline stops INSIDE the real roof edge; roof continues "
                      "past it",
                over="outline extends PAST the real edge onto something that "
                     "is not this facet",
                ragged="roughly right but jagged where the real edge is straight",
                cut="outline CROSSES a real roof feature (ridge, valley, "
                    "dormer) instead of stopping at it",
                unsure="cannot tell from the render"),
            severity=dict(minor="estimated area impact under 5 pct",
                          moderate="5 to 20 pct", major="over 20 pct"),
            location="compass direction of the affected edge, per the north "
                     "arrow on the render (N, NE, E, SE, S, SW, W, NW, or "
                     "'all' / 'multiple')",
            note="free text. Say what you SAW, not what the fix should be. "
                 "A physical description travels to the next site; a suggested "
                 "threshold does not."),
        facets=[dict(facet=r["facet"], kind=r["kind"],
                     pitch_deg=round(r["pitch_deg"], 2),
                     plan_ft2=r["plan_ft2"], n_points=r["n_points"],
                     quality=round(r["quality"], 4),
                     render=f"facet-{r['facet']:02d}.png",
                     identity="", boundary="", severity="", location="",
                     note="") for r in rows],
        missing_facets=[],
        intersection_lines=[
            dict(id=ln["id"], kind=ln["kind"], between=[ln["a"], ln["b"]],
                 length_ft=round(ln["length_cu"] * ft_per_cu, 1),
                 verdict="", note="") for ln in lines],
        missing_lines=[],
        intersection_line_verdicts=dict(
            correct="the line is where the real crease is, and typed right",
            mistyped="right place, wrong type (a ridge called a valley, etc)",
            misplaced="wrong place on the roof",
            spurious="no real crease here",
            short="stops before the real crease ends",
            long="runs past where the real crease ends"),
        unassigned_footprint=dict(
            segmentation_gap=dict(
                cu2=round(c2(seg_gap), 4), ft2=round(f2(seg_gap), 1),
                colour="pink",
                meaning="real roof, enough points to test, NO facet claims it. "
                        "A segmentation failure. This is the fringe finding."),
            capture_gap=dict(
                cu2=round(c2(cap_gap), 4), ft2=round(f2(cap_gap), 1),
                colour="blue",
                meaning="under 2 points per cell, or outside the eroded "
                        "interior. Nothing could have been fitted here; only a "
                        "reflight changes it."),
            reconciliation=recon))

    data_p = out / "review-data.json"
    data_p.write_text(json.dumps(tmpl, indent=2))
    print(f"  wrote {data_p}")

    p = rev_dir / f"review-{args.stamp}.json"
    if p.exists() and any(f.get("identity") or f.get("verdict")
                          for f in json.loads(p.read_text()).get("facets", [])):
        print(f"  {p} holds a PARTLY FILLED review, NOT overwritten. "
              f"New blank schema written alongside it.")
        p = rev_dir / f"review-{args.stamp}.schema2.json"
    p.write_text(json.dumps(tmpl, indent=2))
    print(f"  wrote {p}")

    html = build_review_html(tmpl, name, args.stamp)
    (out / "review.html").write_text(html, encoding="utf-8")
    print(f"  wrote {out / 'review.html'}")
    print(f"\n  Open reports/{name}/review/{args.stamp}/review.html directly "
          f"in a browser. Progress autosaves; the last screen downloads the "
          f"completed JSON for reviews/{name}/.")


if __name__ == "__main__":
    main()
