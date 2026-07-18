# Labeled facet renders: numbered views of the segmented roof so field
# measurements (inclinometer readings keyed "F0..F7") can be matched to
# pipeline facet indices by LOOKING at the pictures, no compass needed.
#
#   python scripts/render_facets.py C:\odm\datasets\big_house
#
# The whole point is that the numbers in the picture are provably the same
# facet indices as the frozen pre-registration, so this script segments the
# cloud EXACTLY the way preregister.py does (same roof.npy, same leveling,
# same seed-pinned discover_facets) and then VERIFIES the result against
# the newest frozen JSON in reports/<dataset>/ before drawing anything:
# per-facet point counts must match exactly, pitch and azimuth to their
# frozen rounding. If any of that disagrees, the render aborts, because a
# picture with wrong numbers is worse than no picture.
#
# Output: <dataset>/facet_views/facet_map_top.png (plan view, the one to
# match readings against) and facet_map_oblique.png (two 3D views, to
# recognize the house). Renders live in the dataset workspace, not the
# repo: the repo holds code and frozen deliverables only.
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # render to file, no display window needed
import matplotlib.pyplot as plt
import numpy as np

from dataset_config import load_config
from recon_common import discover_facets
from roofkit.measure import azimuth_degrees, up_from_tilt
from roofkit.segment import level_cloud

PLOT_POINTS = 40_000  # per-facet cap: plenty for shape, keeps PNGs fast
COLORS = plt.get_cmap("tab10").colors


def newest_freeze(dataset_name):
    """Newest preregistered-*.json in the repo for this dataset, or None."""
    rep = Path(__file__).resolve().parents[1] / "reports" / dataset_name
    frz = sorted(rep.glob("preregistered-*.json"))
    return frz[-1] if frz else None


def verify_against_freeze(facets, freeze_path):
    """Abort unless discovered facets match the frozen file index-for-index.
    Counts exact; pitch/azimuth to the freeze's own rounding."""
    frozen = json.loads(freeze_path.read_text())["facets"]
    if len(facets) != len(frozen):
        sys.exit(f"facet count {len(facets)} != frozen {len(frozen)}")
    for k, (f, z) in enumerate(zip(facets, frozen)):
        got = (len(f["points"]), round(float(f["pitch"]), 3),
               round(azimuth_degrees(f["normal"]), 2))
        want = (z["points"], z["pitch_deg"], z["azimuth_deg"])
        if got != want:
            sys.exit(f"facet {k} mismatch: discovered {got}, frozen {want}. "
                     f"Numbering is NOT the frozen numbering; aborting.")
    print(f"verified: {len(facets)} facets match {freeze_path.name} "
          f"index-for-index (counts exact, pitch/azimuth at frozen rounding)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    rng = np.random.default_rng(0)

    roof = np.load(cfg["roof_path"])
    up = up_from_tilt(cfg["level_tilt_deg"], cfg["level_uphill_az_deg"])
    roof = level_cloud(roof, up)

    facets, _, _ = discover_facets(roof, cfg)
    freeze = newest_freeze(Path(args.dataset).name)
    if freeze is not None:
        verify_against_freeze(facets, freeze)
    else:
        print("no frozen pre-registration found; numbers are THIS run's "
              "indices only")

    out_dir = Path(args.dataset) / "facet_views"
    out_dir.mkdir(exist_ok=True)

    # Subsample each facet once, reused by both figures.
    subs = []
    for f in facets:
        pts = f["points"]
        if len(pts) > PLOT_POINTS:
            pts = pts[rng.choice(len(pts), PLOT_POINTS, replace=False)]
        subs.append(pts)

    # --- Plan view (top-down): the matching picture -----------------------
    fig, ax = plt.subplots(figsize=(11, 11))
    for k, pts in enumerate(subs):
        c = COLORS[k % len(COLORS)]
        ax.scatter(pts[:, 0], pts[:, 1], s=0.4, color=c, rasterized=True,
                   label=(f"F{k}: pitch {facets[k]['pitch']:.1f} deg, "
                          f"az {azimuth_degrees(facets[k]['normal']):.0f}"))
        cx, cy = facets[k]["points"][:, :2].mean(axis=0)
        ax.text(cx, cy, str(k), fontsize=26, fontweight="bold",
                ha="center", va="center",
                bbox=dict(facecolor="white", edgecolor=c, boxstyle="circle"))
    # North arrow: +y is northing in this frame.
    ax.annotate("N", xy=(0.97, 0.97), xytext=(0.97, 0.88),
                xycoords="axes fraction", ha="center", fontsize=14,
                arrowprops=dict(arrowstyle="-|>", lw=2))
    ax.set_aspect("equal")
    ax.set_xticks([]), ax.set_yticks([])
    ax.legend(loc="lower left", fontsize=9, markerscale=20, framealpha=0.9)
    ax.set_title(f"{Path(args.dataset).name}: facet numbers, plan view "
                 f"(matches frozen indices)" if freeze else
                 f"{Path(args.dataset).name}: facet numbers, plan view")
    fig.savefig(out_dir / "facet_map_top.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # --- Two oblique 3D views: for recognizing the actual house -----------
    fig = plt.figure(figsize=(20, 10))
    lo, hi = roof.min(axis=0), roof.max(axis=0)
    for i, azim in enumerate((45, 225)):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        for k, pts in enumerate(subs):
            c = COLORS[k % len(COLORS)]
            ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=0.3, color=c,
                       rasterized=True)
            cx, cy, cz = facets[k]["points"].mean(axis=0)
            # Lift labels well above the surface so they clear the points.
            ax.text(cx, cy, cz + 0.15 * (hi[2] - lo[2]) + 1.0, str(k),
                    fontsize=20, fontweight="bold", ha="center",
                    bbox=dict(facecolor="white", edgecolor=c,
                              boxstyle="circle", alpha=0.9))
        ax.view_init(elev=35, azim=azim)
        ax.set_axis_off()
        ax.set_title(f"view azim {azim} (0=from south, 90=from west)")
        # Equal aspect and tight limits: without these, matplotlib pads the
        # 3D axes so much the roof shrinks to a corner of the frame.
        ax.set_box_aspect(hi - lo)
        ax.set_xlim(lo[0], hi[0])
        ax.set_ylim(lo[1], hi[1])
        ax.set_zlim(lo[2], hi[2])
    fig.subplots_adjust(left=0, right=1, bottom=0, top=0.95, wspace=0)
    fig.savefig(out_dir / "facet_map_oblique.png", dpi=160,
                bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_dir / 'facet_map_top.png'}")
    print(f"wrote {out_dir / 'facet_map_oblique.png'}")


if __name__ == "__main__":
    main()
