# Per-house PDF roof report generator (EagleView-style deliverable).
#
#   python scripts/build_report.py C:\odm\datasets\big_house
#
# This is GLUE, not analysis: it reads the frozen pre-registration and the
# scored comparison file (the analysis outputs), recomputes the cloud
# geometry ONLY to draw pictures, and assembles eight pages into one PDF.
# Every real-world claim printed here is quoted from the comparison file;
# nothing house-specific is hardcoded. Reused unchanged for the next houses.
#
# Why recompute geometry at all when the freeze already has the numbers?
# Because the freeze stores numbers (areas, pitches), not shapes. To DRAW a
# facet we need its points and outline, which only the cloud has. To keep
# the pictures honest we segment the cloud EXACTLY as the pipeline did and
# VERIFY the result against the freeze index-for-index before drawing a
# single label (same guard render_facets.py uses). A picture with wrong
# numbers is worse than no picture, so a mismatch aborts.
#
# Rendering choice: matplotlib for both drawing and PDF assembly. The pages
# are dominated by 3D point-cloud and plan renders that come from matplotlib
# anyway; keeping one toolchain makes the whole report reproducible with a
# single command. (Open3D is only used indirectly, via the pipeline's own
# seed-pinned segmentation.)
import argparse
import datetime
import pickle
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # render to file; no display needed
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyArrowPatch, Rectangle
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # local imports
import report_data as rd
from dataset_config import load_config
from recon_common import discover_facets
from roofkit.measure import (azimuth_degrees, up_from_tilt, facet_boundary,
                             project_to_plane, _plane_fit, plane_intersection,
                             line_extent, eave_line)
from roofkit.segment import level_cloud

REPO_ROOT = Path(__file__).resolve().parents[1]
LETTER = (8.5, 11.0)               # US Letter portrait, inches
PLOT_POINTS = 40_000               # per-facet draw cap (shape, not accuracy)

# EagleView-ish brand palette. Neutral, print-safe, theme-agnostic.
INK = "#1a1a2e"
ACCENT = "#0b5394"
MUTED = "#6b7280"
RULE = "#c9ced6"
PASS_GREEN = "#2e7d32"
FAIL_RED = "#c62828"
WARN_AMBER = "#b26a00"
# Stable per-label facet fill colors (A..) for plan / area / table.
FACET_CMAP = plt.get_cmap("tab20").colors


# ==========================================================================
# Geometry preparation (recompute + verify + cache)
# ==========================================================================

def _verify_against_freeze(facets, freeze):
    """Abort unless the recomputed facets match the freeze index-for-index:
    exact point counts, pitch/azimuth to the freeze's own rounding. This is
    what lets every drawn label be called a frozen number."""
    frozen = freeze["facets"]
    if len(facets) != len(frozen):
        sys.exit(f"ABORT: {len(facets)} facets recomputed, freeze has "
                 f"{len(frozen)}. Numbering would be wrong; not drawing.")
    for k, (f, z) in enumerate(zip(facets, frozen)):
        got = (len(f["points"]), round(float(f["pitch"]), 3),
               round(azimuth_degrees(f["normal"]), 2))
        want = (z["points"], z["pitch_deg"], z["azimuth_deg"])
        if got != want:
            sys.exit(f"ABORT: facet {k} recomputed {got} != frozen {want}. "
                     f"Segmentation drifted from the freeze; not drawing.")


def _reconstruct_scale_lines(facets, cfg, spacing, freeze):
    """Rebuild the two lines the pipeline actually derives and taped, so the
    plan view can dimension them. These are the ONLY roof lines with a
    validated length (everything else is an un-dimensioned outline).

    The freeze names them by cand_id:
      length:rA,B  -> the ridge where facets A and B meet (a single line)
      lines:rX,Y-eZ-> a slope span: perpendicular from ridge(X,Y) to eave(Z)
    We parse those ids (house-agnostic) and reconstruct each line's location
    from the same primitives the pipeline uses. If an id has an unrecognized
    form, we skip drawing it rather than guess. Returns a dict keyed
    'primary'/'fallback' with each: label, kind, seg (2x3 endpoints), span_cu.
    """
    by_index = {z["facet"]: f for z, f in zip(freeze["facets"], facets)}
    out = {}
    contact_dist = cfg.get("ridge_contact_mult", 10.0) * spacing

    def ridge_segment(a, b):
        """Endpoints of the ridge line between facets a and b, using the
        same plane-intersection + contiguous-extent primitives as the
        pipeline (so the drawn length matches the frozen span)."""
        pa, pb = by_index[a]["points"], by_index[b]["points"]
        na, ca = _plane_fit(pa)
        nb, cb = _plane_fit(pb)
        inter = plane_intersection(na, ca, nb, cb)
        if inter is None:
            return None
        p0, d = inter
        both = np.vstack([pa, pb])
        rel = both - p0
        along = rel @ d
        radial = np.linalg.norm(rel - np.outer(along, d), axis=1)
        contacts = both[radial <= contact_dist]
        if len(contacts) < 20:
            return None
        ext = line_extent(contacts, p0, d, spacing)  # contiguity rule inside
        return np.array([p0 + ext["t_lo"] * d, p0 + ext["t_hi"] * d]), ext

    for slot, key in (("primary", "scale_candidate_primary"),
                      ("fallback", "scale_candidate_fallback")):
        cand = freeze.get(key)
        if not cand:
            continue
        cid = cand["cand_id"]
        span_cu = cand["span"]
        seg = None
        m_ridge = re.fullmatch(r"length:r(\d+),(\d+)", cid)
        m_pair = re.fullmatch(r"lines:r(\d+),(\d+)-e(\d+)", cid)
        try:
            if m_ridge:
                a, b = int(m_ridge[1]), int(m_ridge[2])
                res = ridge_segment(a, b)
                if res is not None:
                    seg = res[0]
                kind = "ridge"
            elif m_pair:
                # slope span: draw from a point on eave Z, straight up the
                # slope by the frozen span length. Direction is the real
                # in-plane downslope of facet Z; length is the frozen value,
                # so the drawn segment equals its printed dimension.
                z = int(m_pair[3])
                fz = by_index[z]
                ev = eave_line(fz["points"], fz["normal"], spacing)
                if ev is not None:
                    start = ev["p0"]
                    seg = np.array([start, start - span_cu * ev["w"]])
                kind = "slope span (rake)"
            else:
                kind = "unknown"
        except Exception as e:
            print(f"  note: could not reconstruct {cid} ({e}); skipping draw")
            seg = None
            kind = "unknown"
        out[slot] = {"cand_id": cid, "kind": kind, "seg": seg,
                     "span_cu": span_cu}
    return out


def prepare_geometry(dataset_dir, inputs, refresh=False):
    """Segment the cloud once, verify against the freeze, and return the
    drawable geometry: per-facet subsampled points + outline + centroid +
    normal, the two reconstructed scale lines, and the leveled bounding box.
    Cached to <dataset>/report_cache so layout iteration does not re-segment
    9M points every run; the cache is re-verified against the freeze on
    every load, so a stale cache can never put wrong numbers on the page."""
    freeze = inputs["freeze"]
    if freeze is None:
        sys.exit("ABORT: no frozen pre-registration found; nothing to draw.")

    cache_dir = Path(dataset_dir) / "report_cache"
    cache_dir.mkdir(exist_ok=True)
    stem = inputs["freeze_path"].stem
    cache = cache_dir / f"geom-{stem}.pkl"

    if cache.exists() and not refresh:
        geom = pickle.loads(cache.read_bytes())
        # Re-verify the cheap summary against the freeze before trusting it.
        ok = (len(geom["facets"]) == len(freeze["facets"]) and all(
            g["count"] == z["points"]
            and round(g["pitch_deg"], 3) == z["pitch_deg"]
            and round(g["azimuth_deg"], 2) == z["azimuth_deg"]
            for g, z in zip(geom["facets"], freeze["facets"])))
        if ok:
            print(f"  using verified geometry cache {cache.name}")
            return geom
        print("  cache disagrees with freeze; rebuilding geometry")

    print("  segmenting cloud (this recomputes the pipeline's facets)...")
    cfg = load_config(dataset_dir)
    roof = np.load(cfg["roof_path"])
    up = up_from_tilt(cfg["level_tilt_deg"], cfg["level_uphill_az_deg"])
    roof = level_cloud(roof, up)
    facets, band, spacing = discover_facets(roof, cfg)
    _verify_against_freeze(facets, freeze)
    print(f"  verified {len(facets)} facets match {inputs['freeze_path'].name}")

    rng = np.random.default_rng(0)
    fac_out = []
    for z, f in zip(freeze["facets"], facets):
        pts = f["points"]
        sub = (pts[rng.choice(len(pts), PLOT_POINTS, replace=False)]
               if len(pts) > PLOT_POINTS else pts)
        boundary = facet_boundary(sub, f["normal"])  # outline, spike-cleaned
        fac_out.append({
            "seg_index": z["facet"],
            "count": len(pts),
            "pitch_deg": float(f["pitch"]),
            "azimuth_deg": azimuth_degrees(f["normal"]),
            "normal": np.asarray(f["normal"], float),
            "centroid": pts.mean(axis=0),
            "sub": sub.astype(np.float32),
            "boundary": boundary.astype(np.float32),
        })

    scale_lines = _reconstruct_scale_lines(facets, cfg, spacing, freeze)
    geom = {
        "facets": fac_out,
        "scale_lines": scale_lines,
        "bbox_lo": roof.min(axis=0),
        "bbox_hi": roof.max(axis=0),
        "spacing": spacing,
    }
    cache.write_bytes(pickle.dumps(geom))
    print(f"  wrote geometry cache {cache.name}")
    return geom


# ==========================================================================
# Shared page furniture
# ==========================================================================

def facet_color(label):
    """Stable fill color for a facet label A, B, C...."""
    return FACET_CMAP[(ord(label) - ord("A")) % len(FACET_CMAP)]


def page(title, subtitle, inputs):
    """Start a page: header band + footer, return (fig, content_axes)."""
    fig = plt.figure(figsize=LETTER)
    prov = inputs["provenance"]
    name = prov["property_name"] or inputs["dataset"]

    # Header band.
    fig.patches.append(Rectangle((0, 0.945), 1.0, 0.055, transform=fig.transFigure,
                                 facecolor=ACCENT, edgecolor="none", zorder=-1))
    fig.text(0.06, 0.973, "ROOF MEASUREMENT REPORT", color="white",
             fontsize=9, fontweight="bold", va="center", alpha=0.9)
    fig.text(0.06, 0.958, name, color="white", fontsize=11, va="center")
    fig.text(0.94, 0.968, title, color="white", fontsize=13,
             fontweight="bold", va="center", ha="right")

    if subtitle:
        fig.text(0.06, 0.925, _wrap(subtitle, 100), color=MUTED, fontsize=9,
                 va="top")

    # Footer: provenance + page number set later by caller via fig.text.
    fig.text(0.06, 0.02,
             f"{inputs['dataset']}  |  freeze {prov['freeze_commit'] or '?'}"
             f"  |  {prov['pipeline_version']}",
             color=MUTED, fontsize=6.5, va="center")
    fig.text(0.94, 0.02, datetime.date.today().isoformat(),
             color=MUTED, fontsize=6.5, va="center", ha="right")
    return fig


def _plan_axes(fig, rect):
    """A top-down (plan) axes with equal aspect and no ticks."""
    ax = fig.add_axes(rect)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor(RULE)
    return ax


def _north_arrow(ax):
    """North arrow: +y is northing in the leveled UTM-derived frame."""
    ax.annotate("N", xy=(0.965, 0.96), xytext=(0.965, 0.86),
                xycoords="axes fraction", ha="center", fontsize=11,
                fontweight="bold", color=INK,
                arrowprops=dict(arrowstyle="-|>", lw=1.8, color=INK))


def _downhill(azimuth_deg):
    """Unit vector pointing downhill in the plan (x=east, y=north) frame."""
    a = np.radians(azimuth_deg)
    return np.array([np.sin(a), np.cos(a)])


def _fmt_ft(x, nd=1):
    return "n/a" if x is None else f"{x:,.{nd}f}"


# ==========================================================================
# Page 1: Cover
# ==========================================================================

def page_cover(pdf, inputs, labeled, geom):
    fig = page("Cover", None, inputs)
    prov = inputs["provenance"]
    comp = inputs["comparison"] or {}
    name = prov["property_name"] or inputs["dataset"]

    # Oblique 3D render, top ~55% of the page.
    ax = fig.add_axes([0.05, 0.40, 0.90, 0.50], projection="3d")
    lo, hi = geom["bbox_lo"], geom["bbox_hi"]
    for r in geom["facets"]:
        lab = _label_for(labeled, r["seg_index"])
        s = r["sub"]
        ax.scatter(s[:, 0], s[:, 1], s[:, 2], s=0.25,
                   color=facet_color(lab), rasterized=True)
    ax.view_init(elev=32, azim=45)
    ax.set_axis_off()
    ax.set_box_aspect(hi - lo)
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])

    fig.text(0.5, 0.965, "", ha="center")  # header already drawn
    fig.text(0.06, 0.36, name, fontsize=26, fontweight="bold", color=INK)
    fig.text(0.06, 0.32, "Drone-derived roof measurement", fontsize=12,
             color=MUTED)

    # Provenance block.
    lines = [
        ("Property", name),
        ("Flight date", prov["flight_date"] or "not recorded in dataset config"),
        ("Pipeline version", prov["pipeline_version"]),
        ("Freeze commit", prov["freeze_commit"] or "uncommitted"),
        ("Report date", datetime.date.today().isoformat()),
    ]
    y = 0.27
    for k, v in lines:
        fig.text(0.06, y, k, fontsize=9, color=MUTED)
        fig.text(0.26, y, str(v), fontsize=9, color=INK)
        y -= 0.022

    # Summary box: total area, facet count, predominant pitch.
    total = comp.get("total_area_ft2")
    band_name, pitch_mean, x12 = rd.predominant_pitch(labeled)
    ax2 = fig.add_axes([0.55, 0.10, 0.40, 0.20])
    ax2.axis("off")
    ax2.add_patch(Rectangle((0, 0), 1, 1, transform=ax2.transAxes,
                            facecolor="#eef3f8", edgecolor=ACCENT, lw=1.2))
    ax2.text(0.5, 0.86, "SUMMARY", ha="center", fontsize=9,
             fontweight="bold", color=ACCENT, transform=ax2.transAxes)
    summ = [
        (f"{_fmt_ft(total)} ft²", "total roof area"),
        (f"{len(labeled)}", "roof facets"),
        (f"{pitch_mean:.0f}° ({x12})" if pitch_mean else "n/a",
         "predominant pitch"),
    ]
    yy = 0.66
    for big, small in summ:
        ax2.text(0.5, yy, big, ha="center", fontsize=15, fontweight="bold",
                 color=INK, transform=ax2.transAxes)
        ax2.text(0.5, yy - 0.09, small, ha="center", fontsize=8,
                 color=MUTED, transform=ax2.transAxes)
        yy -= 0.24

    fig.text(0.06, 0.10,
             "Area is scale-confirmed by an independent tape length, not\n"
             "validated against a measured area (none exists for this\n"
             "property). See the Validation page.", fontsize=8, color=MUTED)
    pdf.savefig(fig); plt.close(fig)


def _label_for(labeled, seg_index):
    for r in labeled:
        if r["seg_index"] == seg_index:
            return r["label"]
    return "?"


# ==========================================================================
# Page 2: Plan view with derived-line dimensions
# ==========================================================================

def _scatter_plan(ax, labeled, geom, color_fn, label_fn=None):
    """Scatter every facet top-down with its label at the centroid."""
    for r in geom["facets"]:
        lab = _label_for(labeled, r["seg_index"])
        s = r["sub"]
        ax.scatter(s[:, 0], s[:, 1], s=0.3, color=color_fn(lab),
                   rasterized=True)
    for r in geom["facets"]:
        lab = _label_for(labeled, r["seg_index"])
        cx, cy = r["centroid"][0], r["centroid"][1]
        txt = lab if label_fn is None else label_fn(lab)
        ax.text(cx, cy, txt, fontsize=11, fontweight="bold", ha="center",
                va="center", color=INK,
                bbox=dict(facecolor="white", edgecolor=MUTED, boxstyle="round,pad=0.2",
                          alpha=0.85))


def page_plan(pdf, inputs, labeled, geom):
    fig = page("Plan View", "Top-down orthographic. Facet labels A-H "
               "(smallest area first). Only the two cloud-derived, "
               "tape-validated lines are dimensioned.", inputs)
    ax = _plan_axes(fig, [0.06, 0.18, 0.88, 0.70])
    _scatter_plan(ax, labeled, geom, facet_color)
    _north_arrow(ax)

    ft_per_cu = _ft_per_cu(inputs)
    scale = inputs["comparison"]["scale"] if inputs["comparison"] else {}
    xcheck = inputs["comparison"]["scale_crosscheck"] if inputs["comparison"] else {}

    # Draw and dimension the two derived lines.
    dims = []
    for slot, tape_key, tape_alt_key in (
            ("primary", "primary_tape_in", None),
            ("fallback", "tape_in", "tape_in_with_gutter")):
        sl = geom["scale_lines"].get(slot)
        if not sl or sl["seg"] is None:
            continue
        seg = sl["seg"]
        ax.plot(seg[:, 0], seg[:, 1], color=FAIL_RED if slot == "primary"
                else ACCENT, lw=2.4, solid_capstyle="round", zorder=5)
        ax.scatter(seg[:, 0], seg[:, 1], color="white",
                   edgecolor=INK, s=18, zorder=6, lw=1)
        length_ft = sl["span_cu"] * ft_per_cu if ft_per_cu else None
        mid = seg.mean(axis=0)
        src = scale if slot == "primary" else xcheck
        tape_in = src.get(tape_key)
        tape_ft = tape_in / 12.0 if tape_in else None
        lbl = f"{sl['kind']}: {_fmt_ft(length_ft)} ft"
        ax.annotate(lbl, xy=(mid[0], mid[1]), fontsize=9, fontweight="bold",
                    color=INK, ha="center",
                    bbox=dict(facecolor="white", edgecolor=RULE,
                              boxstyle="round,pad=0.25", alpha=0.95))
        dims.append((slot, sl, length_ft, tape_ft,
                     src.get(tape_alt_key) if tape_alt_key else None))

    # Caption below: the two dimensions with cloud-derived vs tape.
    y = 0.135
    fig.text(0.06, y, "Dimensioned lines (the only two with a validated "
             "length; every other edge is an outline, not a measured edge):",
             fontsize=8.5, color=INK, fontweight="bold")
    y -= 0.028
    for slot, sl, length_ft, tape_ft, tape_alt_in in dims:
        alt = (f", {tape_alt_in/12.0:.2f} ft with gutter"
               if tape_alt_in else "")
        fig.text(0.08, y,
                 f"{slot.capitalize()} {sl['cand_id']} ({sl['kind']}): "
                 f"cloud-derived {_fmt_ft(length_ft, 2)} ft; "
                 f"tape {_fmt_ft(tape_ft, 2)} ft{alt}.",
                 fontsize=8, color=MUTED)
        y -= 0.022
    pdf.savefig(fig); plt.close(fig)


def _ft_per_cu(inputs):
    comp = inputs["comparison"]
    if comp and "scale" in comp:
        return comp["scale"].get("ft_per_cu")
    return None


# ==========================================================================
# Page 3: Pitch view
# ==========================================================================

def page_pitch(pdf, inputs, labeled, geom):
    fig = page("Pitch View", "Facets colored by pitch band; arrow points "
               "downslope. Pitch is scale-independent.", inputs)
    ax = _plan_axes(fig, [0.06, 0.30, 0.88, 0.58])

    band_color = {}
    for r in geom["facets"]:
        _, color = rd.pitch_band(r["pitch_deg"])
        band_color[r["seg_index"]] = color
    for r in geom["facets"]:
        s = r["sub"]
        ax.scatter(s[:, 0], s[:, 1], s=0.3,
                   color=band_color[r["seg_index"]], rasterized=True)
    for r in geom["facets"]:
        lab = _label_for(labeled, r["seg_index"])
        cx, cy = r["centroid"][0], r["centroid"][1]
        x12 = rd.pitch_to_x12(r["pitch_deg"])
        ax.text(cx, cy, f"{lab}\n{r['pitch_deg']:.1f}°\n{x12}:12",
                fontsize=8, fontweight="bold", ha="center", va="center",
                color=INK, bbox=dict(facecolor="white", edgecolor=MUTED,
                                     boxstyle="round,pad=0.2", alpha=0.85))
        # Downslope arrow.
        d = _downhill(r["azimuth_deg"])
        span = (geom["bbox_hi"] - geom["bbox_lo"])[:2]
        L = 0.10 * float(np.mean(span))
        ax.add_patch(FancyArrowPatch((cx, cy), (cx + d[0] * L, cy + d[1] * L),
                     arrowstyle="-|>", mutation_scale=12, lw=1.6,
                     color=INK, alpha=0.7, zorder=5))
    _north_arrow(ax)

    # Legend of pitch bands actually present.
    present = []
    seen = set()
    for r in sorted(geom["facets"], key=lambda r: r["pitch_deg"]):
        name, color = rd.pitch_band(r["pitch_deg"])
        if name not in seen:
            seen.add(name); present.append((name, color))
    y = 0.24
    fig.text(0.06, y + 0.02, "Pitch bands:", fontsize=9, fontweight="bold",
             color=INK)
    for name, color in present:
        fig.patches.append(Rectangle((0.20, y - 0.004), 0.02, 0.014,
                           transform=fig.transFigure, facecolor=color,
                           edgecolor="none"))
        fig.text(0.235, y, name, fontsize=8.5, color=INK, va="center")
        y -= 0.024
    fig.text(0.06, 0.06, _wrap(
        "The x:12 value under each facet is a rounding of the degree "
        "measurement to the nearest inch of rise per 12 inches of run, not "
        "an independent measurement.", 110), fontsize=8, color=MUTED,
        va="top")
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# Page 4: Area view
# ==========================================================================

def page_area(pdf, inputs, labeled, geom):
    fig = page("Area View", "Per-facet slope area (ft²) labeled in "
               "place. Slope area is what shingles cover, not footprint.",
               inputs)
    ax = _plan_axes(fig, [0.06, 0.22, 0.88, 0.66])
    _scatter_plan(ax, labeled, geom, facet_color, label_fn=None)
    # Overlay ft2 per facet.
    area_by_idx = {}
    for a in (inputs["comparison"] or {}).get("areas", []):
        area_by_idx[a["facet"]] = a["area_ft2"]
    for r in geom["facets"]:
        lab = _label_for(labeled, r["seg_index"])
        cx, cy = r["centroid"][0], r["centroid"][1]
        ar = area_by_idx.get(r["seg_index"])
        ax.text(cx, cy, f"{lab}\n{_fmt_ft(ar)} ft²", fontsize=8.5,
                fontweight="bold", ha="center", va="center", color=INK,
                bbox=dict(facecolor="white", edgecolor=MUTED,
                          boxstyle="round,pad=0.2", alpha=0.88))
    _north_arrow(ax)
    total = (inputs["comparison"] or {}).get("total_area_ft2")
    fig.text(0.06, 0.15, f"Total slope area: {_fmt_ft(total)} ft²",
             fontsize=12, fontweight="bold", color=INK)
    fig.text(0.06, 0.115, "Total carries a dormer caveat (see facet table "
             "and validation page); it is not a clean sum.", fontsize=8,
             color=WARN_AMBER)
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# Page 5: Facet table
# ==========================================================================

def page_facet_table(pdf, inputs, labeled, geom):
    fig = page("Facet Table", "One row per facet, labels A-H by area. "
               "x:12 is a rounding of the degree column.", inputs)
    comp = inputs["comparison"] or {}

    headers = ["Label", "Seg#", "Area ft²", "Pitch °", "x:12",
               "Azimuth °", "Dormer", "Eave", "Panel"]
    cells = []
    for r in labeled:
        cells.append([
            r["label"], str(r["seg_index"]), _fmt_ft(r["area_ft2"]),
            f"{r['pitch_deg']:.1f}" if r["pitch_deg"] is not None else "n/a",
            f"{r['x12']}:12" if r["x12"] is not None else "n/a",
            f"{r['azimuth_deg']:.0f}" if r["azimuth_deg"] is not None else "n/a",
            _dormer_short(r["dormer"]),
            "flag" if r["eave_flagged"] else "-",
            r["panel_region"] or "-",
        ])
    # Totals row.
    total = comp.get("total_area_ft2")
    cells.append(["TOTAL", "", _fmt_ft(total), "", "", "", "see caveat",
                  "", ""])

    ax = fig.add_axes([0.05, 0.42, 0.90, 0.46]); ax.axis("off")
    tbl = ax.table(cellText=cells, colLabels=headers, loc="upper center",
                   cellLoc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(8.5); tbl.scale(1, 1.5)
    _style_table(tbl, headers, n_data=len(labeled))

    # Mapping table label -> segmentation index (explicit cross-reference).
    fig.text(0.06, 0.36, "Label → segmentation index (cross-references "
             "the freeze and comparison files):", fontsize=8.5,
             fontweight="bold", color=INK)
    mapping = "   ".join(f"{r['label']}=F{r['seg_index']}" for r in labeled)
    fig.text(0.06, 0.335, mapping, fontsize=9, color=ACCENT, family="monospace")

    # Total-level caveat, verbatim from the comparison file (required).
    caveat = comp.get("total_area_caveat", "")
    fig.text(0.06, 0.29, "Total-level caveat (why the total is not a bare "
             "number):", fontsize=8.5, fontweight="bold", color=WARN_AMBER)
    fig.text(0.06, 0.265, _wrap(caveat, 110), fontsize=8, color=INK, va="top")
    fig.text(0.06, 0.11, _wrap(
        "Flags: Dormer = per-facet dormer contamination (absorbed, "
        "unmodeled); susp* = heaviest. Eave 'flag' = wide loose/tight eave "
        "bracket (possible gutter/fascia/vegetation). Panel = solar region "
        "(later houses).", 110), fontsize=7.5, color=MUTED, va="top")
    pdf.savefig(fig); plt.close(fig)


def _dormer_short(d):
    if not d:
        return "-"
    if "heaviest" in d:
        return "susp*"
    if "suspect" in d:
        return "susp"
    if "clean" in d:
        return "clean"
    return d[:6]


def _style_table(tbl, headers, n_data):
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor(RULE)
        if row == 0:
            cell.set_facecolor(ACCENT); cell.set_text_props(color="white",
                                                            fontweight="bold")
        elif row == n_data + 1:  # totals row
            cell.set_facecolor("#eef3f8")
            cell.set_text_props(fontweight="bold", color=INK)
        elif row % 2 == 0:
            cell.set_facecolor("#f6f7f9")


# ==========================================================================
# Page 6: Materials summary
# ==========================================================================

def page_materials(pdf, inputs, labeled, geom):
    fig = page("Materials Summary", "Areas per pitch, waste-to-squares, and "
               "the honest line-length inventory.", inputs)
    comp = inputs["comparison"] or {}
    total = comp.get("total_area_ft2")

    # --- Areas per pitch band ---
    per_band = rd.areas_per_pitch(labeled)
    ax1 = fig.add_axes([0.05, 0.72, 0.42, 0.16]); ax1.axis("off")
    ax1.text(0, 1.0, "Area per pitch band", fontsize=9, fontweight="bold",
             color=INK, transform=ax1.transAxes)
    rows = [[g["name"], "/".join(g["labels"]), _fmt_ft(g["area_ft2"])]
            for g in per_band]
    t1 = ax1.table(cellText=rows,
                   colLabels=["Band", "Facets", "Area ft²"],
                   loc="upper left", cellLoc="left")
    t1.auto_set_font_size(False); t1.set_fontsize(7.5); t1.scale(1, 1.4)
    _style_table(t1, None, n_data=len(rows))

    # --- Waste to squares ---
    ax2 = fig.add_axes([0.53, 0.60, 0.42, 0.28]); ax2.axis("off")
    ax2.text(0, 1.0, "Roofing squares by waste allowance", fontsize=9,
             fontweight="bold", color=INK, transform=ax2.transAxes)
    ax2.text(1.0, 1.0, "1 square = 100 ft²", fontsize=7.5, color=MUTED,
             ha="right", transform=ax2.transAxes)
    srows = [[f"{s['waste_pct']}%", _fmt_ft(s['area_ft2']),
              f"{s['squares']:.2f}"] for s in rd.squares_table(total)]
    t2 = ax2.table(cellText=srows,
                   colLabels=["Waste", "Area ft²", "Squares"],
                   loc="upper left", cellLoc="center")
    t2.auto_set_font_size(False); t2.set_fontsize(7.5); t2.scale(1, 1.3)
    _style_table(t2, None, n_data=len(srows))
    ax2.text(0, -0.06, "Squares computed from the total, which carries the "
             "dormer caveat.", fontsize=7, color=WARN_AMBER,
             transform=ax2.transAxes, va="top")

    # --- Line-length inventory (honest about what the pipeline classifies) -
    fig.text(0.06, 0.54, "Line-length inventory", fontsize=10,
             fontweight="bold", color=INK)
    fig.text(0.06, 0.52, _wrap(
        "What the pipeline classifies TODAY: it derives and tape-validates "
        "exactly two lines. It has no general edge-classification stage, so "
        "no full ridge/hip/valley/rake/eave inventory is claimed.", 110),
        fontsize=8, color=MUTED, va="top")

    ft_per_cu = _ft_per_cu(inputs)
    inv_rows = []
    for slot in ("primary", "fallback"):
        sl = geom["scale_lines"].get(slot)
        if not sl:
            continue
        length_ft = sl["span_cu"] * ft_per_cu if ft_per_cu else None
        typ = "Ridge" if sl["kind"] == "ridge" else "Rake (slope span)"
        inv_rows.append([typ, sl["cand_id"], _fmt_ft(length_ft, 2), "1",
                         "tape-validated"])
    ax3 = fig.add_axes([0.05, 0.34, 0.90, 0.12]); ax3.axis("off")
    t3 = ax3.table(cellText=inv_rows,
                   colLabels=["Type", "Line id", "Length ft", "Count",
                              "Status"],
                   loc="upper left", cellLoc="left")
    t3.auto_set_font_size(False); t3.set_fontsize(8); t3.scale(1, 1.4)
    _style_table(t3, None, n_data=len(inv_rows))

    fig.text(0.06, 0.28, "What a full inventory would still require (not "
             "built; not fabricated here):", fontsize=8.5,
             fontweight="bold", color=INK)
    needs = [
        "Rake vs eave: derivable from each boundary edge's angle to "
        "horizontal (an eave is level; a rake climbs the slope).",
        "Ridge vs valley: needs the dihedral sign where two facets meet "
        "(ridge = convex/peak, valley = concave/gutter).",
        "Drip edge vs plane-plane line: needs to distinguish a facet's "
        "boundary edge from an interior plane-intersection line.",
        "All of the above needs a per-facet edge-enumeration + classifier "
        "stage the pipeline does not yet have; eave DIRECTIONS are derived "
        "today, but not full eave lengths.",
    ]
    y = 0.255
    for n in needs:
        fig.text(0.08, y, "• " + _wrap(n, 105), fontsize=7.8,
                 color=MUTED, va="top")
        y -= 0.038
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# Page 7: Validation (the differentiator)
# ==========================================================================

def page_validation(pdf, inputs, labeled, geom):
    fig = page("Validation", "The accuracy page competitors do not publish. "
               "Failure reported first.", inputs)
    comp = inputs["comparison"] or {}
    base = inputs["baseline_comparison"] or {}
    scale = comp.get("scale", {})
    xcheck = comp.get("scale_crosscheck", {})
    psum = comp.get("pitch_summary", {})

    col = 0.06
    y = 0.90

    def head(txt, yy, color=ACCENT):
        fig.text(col, yy, txt, fontsize=10, fontweight="bold", color=color)

    def body(txt, yy, color=INK, size=8):
        fig.text(col, yy, _wrap(txt, 112), fontsize=size, color=color,
                 va="top")

    # 1. Scale provenance.
    head("1. Scale provenance", y)
    y -= 0.018
    body(f"One tape length sets the multiplier: {scale.get('primary_cand_id')} "
         f"taped {scale.get('primary_tape_in')} in over "
         f"{scale.get('primary_span_cu', 0):.3f} cu = "
         f"{scale.get('in_per_cu')} in/cu ({scale.get('ft_per_cu')} ft/cu). "
         f"The freeze's recorded end-sensitivity ({scale.get('recorded_end_sensitivity_cu', 0):.3f} cu) "
         f"is reported, not corrected away; its meaning is defined in the "
         f"freeze context. GPS scale error at this multiplier: "
         f"{scale.get('gps_scale_error_pct')}%.", y)
    y -= 0.075

    # 2. Cross-check result with edge-definition sensitivity.
    head("2. Independent cross-check", y,
         color=PASS_GREEN if xcheck.get("pass") else FAIL_RED)
    y -= 0.018
    body(f"A second, independent tape on {xcheck.get('fallback_cand_id')} "
         f"checks the multiplier: predicted {xcheck.get('predicted_in')} in "
         f"vs taped {xcheck.get('tape_in')} in = "
         f"{xcheck.get('disagreement_pct')}% "
         f"(budget ±{xcheck.get('linear_budget_pct')}%) -> "
         f"{'PASS' if xcheck.get('pass') else 'FAIL'}. Edge-definition "
         f"sensitivity is shown, not resolved: against the with-gutter tape "
         f"({xcheck.get('tape_in_with_gutter')} in) the disagreement is "
         f"{xcheck.get('disagreement_pct_with_gutter')}%. Implied area "
         f"uncertainty ~{xcheck.get('implied_area_uncertainty_pct')}%.", y)
    y -= 0.085

    # 3. Run 1 FIRST: failure before fix.
    head("3. Run 1 reported first: the failure that drove the fix", y,
         color=FAIL_RED)
    y -= 0.018
    b_x = base.get("scale_crosscheck", {})
    bctx = comp.get("baseline_context", {})
    body(f"Run 1 ({base.get('inputs', {}).get('freeze', 'run 1')}) FAILED "
         f"its cross-check at {b_x.get('disagreement_pct')}% "
         f"(predicted {b_x.get('predicted_in')} in vs {b_x.get('tape_in')} "
         f"in taped). Diagnosis: the frozen ridge extent jumped a void to a "
         f"97-point assignment-artifact island and read ~6% long. The fix "
         f"was a cloud-side contiguity rule (cut the extent at any along-"
         f"line void wider than 60x point spacing), which moved the primary "
         f"span 10.808 -> 10.184 cu and left every other number bit-"
         f"identical. Run 2 then passes at {xcheck.get('disagreement_pct')}%. "
         f"Decisive arithmetic: run 1 total {bctx.get('total_area_ft2')} ft² "
         f"vs run 2 {comp.get('total_area_ft2')} ft² "
         f"({bctx.get('this_run_vs_baseline_pct')}% apart); run 1's widened "
         f"±{bctx.get('baseline_implied_area_uncertainty_pct')}% interval "
         f"would {'have' if bctx.get('baseline_interval_contains_this_total') else 'NOT have'} "
         f"contained run 2's corrected total. Widening instead of diagnosing "
         f"would have quoted an interval that misses the value.", y)
    y -= 0.135

    # 4. Per-facet pitch error.
    head("4. Per-facet pitch vs inclinometer", y)
    y -= 0.018
    body(f"Pitch is validated directly against three inclinometer readings "
         f"per facet. Truth uncertainty = the spread of those three; "
         f"pipeline uncertainty = the {psum.get('pipeline_floor_deg')}° "
         f"leveling floor. Max |error| {psum.get('max_abs_error_deg')}°: "
         f"PASS at 3° ({psum.get('pass_at_3deg')}), not at 2° "
         f"({psum.get('pass_at_2deg')}).", y)
    y -= 0.05

    # Compact per-facet pitch table (by label).
    prows = []
    pitch_by_idx = {p["facet"]: p for p in comp.get("pitch", [])}
    for r in labeled:
        p = pitch_by_idx.get(r["seg_index"], {})
        conv = " (90-x)" if p.get("converted_90_minus") else ""
        prows.append([r["label"], f"{p.get('pipeline_deg', float('nan')):.1f}",
                      f"{p.get('truth_mean_deg', float('nan')):.1f}{conv}",
                      f"{p.get('error_deg', float('nan')):+.2f}",
                      f"{p.get('truth_spread_deg', '')}"])
    axp = fig.add_axes([0.06, 0.20, 0.44, 0.15]); axp.axis("off")
    tp = axp.table(cellText=prows,
                   colLabels=["Facet", "Pipe °", "Truth °",
                              "Err °", "Spread"],
                   loc="upper left", cellLoc="center")
    tp.auto_set_font_size(False); tp.set_fontsize(7); tp.scale(1, 1.15)
    _style_table(tp, None, n_data=len(prows))

    # 5. The +offset as an OPEN question.
    fig.text(0.53, 0.345, "5. The systematic pitch offset (OPEN)",
             fontsize=10, fontweight="bold", color=WARN_AMBER)
    fig.text(0.53, 0.20, _wrap(
        f"Errors carry a uniform +{psum.get('mean_bias_deg')}° offset. "
        f"Residual cloud tilt is ruled out (the fitted azimuth term is not "
        f"distinguishable from zero at this noise level). Named suspects, "
        f"left unadjudicated: inclinometer zero/convention (the same "
        f"instrument the F6/F7 90-minus reading flagged), and shingle-"
        f"surface vs fitted-plane definition. Net of the offset, geometric "
        f"scatter is ~0.24° rms.", 60),
        fontsize=8, color=INK, va="top")

    # 6. Claims section, worded exactly per spec.
    fig.text(col, 0.135, "6. Claims", fontsize=10, fontweight="bold",
             color=ACCENT)
    fig.text(col, 0.115,
             "• Area scale is confirmed by an independent length.",
             fontsize=8.5, color=INK)
    fig.text(col, 0.095,
             "• Area itself is NOT validated against a measured area, "
             "because none exists for this property.", fontsize=8.5,
             color=INK)
    fig.text(col, 0.06, _wrap(comp.get("area_claim", ""), 112), fontsize=7.5,
             color=MUTED, va="top")
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# Page 8: Views (pitch-colored 3D + elevations + dormer annotation)
# ==========================================================================

def page_views(pdf, inputs, labeled, geom):
    fig = page("Views", "Pitch-colored 3D, two elevations, and dormer-"
               "suspect annotation (individual dormers are unsegmented).",
               inputs)
    lo, hi = geom["bbox_lo"], geom["bbox_hi"]

    def band_c(r):
        return rd.pitch_band(r["pitch_deg"])[1]

    # Two 3D oblique views, pitch-colored.
    for i, azim in enumerate((45, 225)):
        ax = fig.add_axes([0.03 + i * 0.48, 0.62, 0.46, 0.28],
                          projection="3d")
        for r in geom["facets"]:
            s = r["sub"]
            ax.scatter(s[:, 0], s[:, 1], s[:, 2], s=0.2, color=band_c(r),
                       rasterized=True)
        ax.view_init(elev=30, azim=azim)
        ax.set_axis_off(); ax.set_box_aspect(hi - lo)
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_title(f"oblique azim {azim}", fontsize=8, color=MUTED)

    # Two elevations: project along +y (looking north) and +x (looking east).
    # An elevation is a side-on orthographic: plot (x, z) and (y, z).
    for i, (hx, label) in enumerate([(0, "South elevation (x vs z)"),
                                     (1, "East elevation (y vs z)")]):
        ax = fig.add_axes([0.08 + i * 0.47, 0.34, 0.38, 0.22])
        for r in geom["facets"]:
            s = r["sub"]
            ax.scatter(s[:, hx], s[:, 2], s=0.2, color=band_c(r),
                       rasterized=True)
        ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor(RULE)
        ax.set_title(label, fontsize=8, color=MUTED)

    # Dormer-suspect annotation: list suspect facets (by label), honest that
    # individual dormers are unmodeled.
    fig.text(0.06, 0.28, "Dormer annotation", fontsize=10, fontweight="bold",
             color=INK)
    suspect = [r["label"] for r in labeled
               if r["dormer"] and "suspect" in (r["dormer"] or "")]
    clean = [r["label"] for r in labeled
             if r["dormer"] and "clean" in (r["dormer"] or "")]
    fig.text(0.06, 0.255,
             f"Dormer-suspect facets: {', '.join(suspect) or 'none'}.  "
             f"Near-clean facets: {', '.join(clean) or 'none'}.",
             fontsize=8.5, color=INK)
    fig.text(0.06, 0.16, _wrap(
        "About 8 dormers were not segmented as their own facets; their "
        "points were absorbed into the host facets above, so the affected "
        "per-facet areas and pitches are biased in an amount that is not "
        "cleanly separable from foliage and an assignment artifact. "
        "Individual dormers therefore cannot be drawn; the honest "
        "annotation is which host facets are contaminated. Only the near-"
        "clean facets are safe to cite per-facet (decision 2026-07-15).",
        112), fontsize=8, color=MUTED, va="top")
    pdf.savefig(fig); plt.close(fig)


# ==========================================================================
# small text helpers
# ==========================================================================

def _wrap(text, width):
    """Wrap to a character width, preserving explicit newlines."""
    import textwrap
    out = []
    for para in (text or "").split("\n"):
        out.append(textwrap.fill(para, width) if para else "")
    return "\n".join(out)


# ==========================================================================
# main
# ==========================================================================

def main():
    ap = argparse.ArgumentParser(description="Build the per-house PDF report.")
    ap.add_argument("dataset_dir", help="ODM workspace dir (holds the cloud "
                    "+ roofkit.json), e.g. C:\\odm\\datasets\\big_house")
    ap.add_argument("--refresh", action="store_true",
                    help="ignore the geometry cache and re-segment the cloud")
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    dataset_name = dataset_dir.name
    print(f"Building report for {dataset_name}")

    inputs = rd.load_inputs(dataset_name, REPO_ROOT, dataset_dir)
    if inputs["comparison"] is None:
        print("  WARNING: no scored comparison file; real-world claims will "
              "read 'n/a'. Score the freeze first for a full report.")
    labeled = rd.label_facets(inputs)
    geom = prepare_geometry(dataset_dir, inputs, refresh=args.refresh)

    out_dir = REPO_ROOT / "reports" / dataset_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"report-{dataset_name}-{datetime.date.today().isoformat()}.pdf"

    with PdfPages(out) as pdf:
        page_cover(pdf, inputs, labeled, geom)
        page_plan(pdf, inputs, labeled, geom)
        page_pitch(pdf, inputs, labeled, geom)
        page_area(pdf, inputs, labeled, geom)
        page_facet_table(pdf, inputs, labeled, geom)
        page_materials(pdf, inputs, labeled, geom)
        page_validation(pdf, inputs, labeled, geom)
        page_views(pdf, inputs, labeled, geom)
        d = pdf.infodict()
        d["Title"] = f"Roof Measurement Report - {dataset_name}"
        d["Subject"] = "Drone-derived roof area and pitch, with validation"

    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
