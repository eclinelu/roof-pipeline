# HOW MUCH AREA DOES M1a ACTUALLY PUT AT RISK? Measured, and RENDERED.
#
#   .venv/Scripts/python.exe scripts/probe_m1a_area_exposure.py C:/odm/datasets/big_house
#
# Writes reports/big_house/m1a-area-exposure-<date>.png   (the render, R6)
#        reports/big_house/m1a-area-exposure-<date>.json  (the numbers, R2)
#
# SIDE ARTIFACT ONLY. Nothing adopted. canonical-2026-07-26-r2 unchanged.
#
# ---------------------------------------------------------------------------
# WHY: THE ONE THING THE PITCH AUDIT DID NOT COVER
#
# `2026-07-28-m1a-does-not-move-the-deliverable.md` showed M1a moves the frozen
# pitch validation by 0.0121 deg against 0.81 deg of headroom, and closed with
# an explicit open limit: **it says nothing about AREA.** Extent inflation is an
# area-shaped defect, and area is the deliverable it would most plausibly move.
# Deprioritising M1a while that limit is open would be deprioritising it on
# incomplete evidence.
#
# THE ARGUMENT BEING TESTED (Emmett's): the alpha shape rejects triangles that
# bridge large gaps, so a remote sliver cannot drag a huge spanning triangle
# into the facet's area. It contributes only its OWN LOCAL AREA. If that is
# right, the total alpha area of the removed components BOUNDS M1a's area
# exposure, and the question closes.
#
# So: at the canonical setting (2.5 x spacing, fraction 1.0), take the points
# the filter removes, split them into their own connected components, and sum
# the alpha area of each. Same alpha the facet's own area computation uses, so
# the two numbers are on the same footing.
#
# AND RENDER IT (standing rule R6, 2026-07-28): choosing to live with a real
# mechanism is a decision that should be taken while looking at the thing, not
# at its area in square units.
#
# INDEPENDENT ASSERTIONS (standing rule 2026-07-27):
#   - removed + kept equals the pre-filter membership, per facet
#   - the total removed count reproduces the M1a sweep's own figure at the same
#     grid point (151,449), which was written by different code
#   - the summed component alpha area never exceeds the alpha area of the whole
#     removed set taken together, because splitting a set into components can
#     only remove bridging triangles, never add them. This is the assertion that
#     would fail loudly if the alpha areas were being computed on the wrong
#     point sets.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.ndimage import label

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib.patches import Rectangle                           # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar                       # noqa: E402
from dataset_config import load_config                             # noqa: E402
from recon_common import discover_facets                           # noqa: E402
from roofkit.measure import facet_area                             # noqa: E402
from roofkit import coverage as cov                                # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"
SCALE = 2.5          # the canonical coverage cell
FRAC = 1.0           # the pre-registration's own "main body" definition
SWEEP_EXPECTED_REMOVED = 151449
STRUCT8 = np.ones((3, 3), dtype=bool)


def components_of(xy, cell):
    lo = xy.min(axis=0)
    i = np.floor((xy[:, 0] - lo[0]) / cell).astype(np.int64)
    j = np.floor((xy[:, 1] - lo[1]) / cell).astype(np.int64)
    i -= i.min()
    j -= j.min()
    occ = np.zeros((i.max() + 1, j.max() + 1), bool)
    occ[i, j] = True
    lab, n = label(occ, structure=STRUCT8)
    return lab[i, j], n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    doc, points, facets_c, cfg_c = load_canonical(args.dataset, CANONICAL_STAMP)
    spacing = scalar(doc, "spacing_cu")
    cfg = load_config(args.dataset)
    in_per_cu = 40.4541
    sc = out / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])
    ft = in_per_cu / 12.0
    ft2 = ft * ft

    print(f"  running discover_facets at scale {SCALE}, fraction {FRAC} ...",
          flush=True)
    facets, band, s_full = discover_facets(
        points, cfg, probability=1.0, spacing=spacing,
        connect_mult=SCALE, min_component_frac=FRAC)
    conn_cell = SCALE * s_full

    rows, checks = [], []
    total_removed = 0
    total_rem_area = 0.0
    total_facet_area = 0.0
    render = []
    for k, f in enumerate(facets):
        fd = f["filter"]
        rem_idx = np.asarray(fd["removed_idx"], dtype=np.int64)
        total_removed += len(rem_idx)
        kept_pts = np.asarray(f["points"], float)
        # the facet's own alpha, so removed area and facet area are comparable
        s_f = float(np.median(cov._nn(kept_pts)))
        alpha = cfg["alpha_mult"] * s_f
        fa = float(facet_area(kept_pts, f["normal"], alpha)) * ft2
        total_facet_area += fa

        # A DEGENERATE COMPONENT HAS NO AREA, AND THE SKIP IS COUNTED.
        # Qhull raises on a component whose projected points are collinear or
        # span less than its roundoff tolerance: a 4-point sliver in a line has
        # no 2D hull. Its true alpha area IS zero, so skipping is correct, but
        # it is counted and reported rather than swallowed, because "the
        # exception fired 900 times" and "there was nothing there" are different
        # facts and only one of them is good news.
        def safe_area(pts):
            try:
                return float(facet_area(pts, f["normal"], alpha)) * ft2
            except Exception:
                return None

        n_degenerate, degenerate_pts = 0, 0
        if len(rem_idx) >= 3:
            rpts = points[rem_idx]
            lab, ncomp = components_of(rpts[:, :2], conn_cell)
            per_comp, comp_area = [], 0.0
            for c in range(1, ncomp + 1):
                sel = lab == c
                if sel.sum() < 3:
                    n_degenerate += 1
                    degenerate_pts += int(sel.sum())
                    continue
                a = safe_area(rpts[sel])
                if a is None:
                    n_degenerate += 1
                    degenerate_pts += int(sel.sum())
                    continue
                comp_area += a
                per_comp.append(dict(n_points=int(sel.sum()),
                                     area_ft2=round(a, 4)))
            per_comp.sort(key=lambda r: -r["area_ft2"])
            whole = safe_area(rpts) or 0.0
            render.append((k, rpts))
        else:
            ncomp, comp_area, per_comp, whole = 0, 0.0, [], 0.0
        total_rem_area += comp_area

        ok = (len(rem_idx) + len(fd["kept_idx_premtrim"]) == fd["n_points_in"])
        rows.append(dict(
            facet=k, n_removed=int(len(rem_idx)),
            n_removed_components=int(ncomp),
            removed_alpha_area_ft2=round(comp_area, 4),
            removed_as_one_set_alpha_area_ft2=round(whole, 4),
            facet_alpha_area_ft2=round(fa, 3),
            removed_pct_of_facet_area=round(100 * comp_area / max(fa, 1e-9), 4),
            n_degenerate_components=int(n_degenerate),
            points_in_degenerate_components=int(degenerate_pts),
            largest_components=per_comp[:5],
            conservation_ok=bool(ok)))

    checks.append(dict(
        check="removed + kept equals the pre-filter membership on every facet",
        passed=all(r["conservation_ok"] for r in rows)))
    checks.append(dict(
        check="total removed reproduces the M1a sweep's own figure at the same "
              "grid point, written by different code",
        passed=bool(total_removed == SWEEP_EXPECTED_REMOVED),
        detail=dict(this_probe=total_removed,
                    sweep=SWEEP_EXPECTED_REMOVED)))
    # splitting a set into components can only REMOVE bridging triangles
    sum_le_whole = all(
        r["removed_alpha_area_ft2"] <= r["removed_as_one_set_alpha_area_ft2"] + 1e-6
        for r in rows)
    checks.append(dict(
        check="summed per-component alpha area never exceeds the alpha area of "
              "the whole removed set, because splitting into components can "
              "only drop bridging triangles, never add them",
        passed=bool(sum_le_whole),
        detail=[dict(facet=r["facet"], summed=r["removed_alpha_area_ft2"],
                     whole=r["removed_as_one_set_alpha_area_ft2"])
                for r in rows]))

    frozen_total = 3559.0
    docout = dict(
        task="how much AREA does M1a actually put at risk? The open limit left "
             "by the pitch audit.",
        dataset=name, date=args.stamp,
        status="SIDE ARTIFACT ONLY. Nothing adopted. "
               "canonical-2026-07-26-r2 unchanged.",
        setting=dict(connectivity_scale_x_spacing=SCALE,
                     min_component_frac=FRAC,
                     connectivity_cell_cu=round(float(conn_cell), 8),
                     alpha="alpha_mult x the FACET's own median nn spacing, so "
                           "removed area and facet area are on the same footing"),
        argument_under_test="the alpha shape rejects triangles bridging large "
                            "gaps, so a remote sliver contributes only its own "
                            "local area rather than dragging a spanning "
                            "triangle into the facet. If so, the summed alpha "
                            "area of the removed components BOUNDS M1a's area "
                            "exposure.",
        totals=dict(
            n_removed=int(total_removed),
            removed_alpha_area_ft2=round(total_rem_area, 3),
            main_facet_alpha_area_ft2=round(total_facet_area, 2),
            removed_pct_of_main_facet_area=round(
                100 * total_rem_area / max(total_facet_area, 1e-9), 4),
            frozen_reported_total_ft2=frozen_total,
            removed_pct_of_frozen_total=round(
                100 * total_rem_area / frozen_total, 4)),
        cross_checks=checks,
        rows=rows,
        render=f"m1a-area-exposure-{args.stamp}.png")
    p = out / f"m1a-area-exposure-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2, default=float))

    # ---- THE RENDER (R6) --------------------------------------------------
    fig, ax = plt.subplots(figsize=(11, 12))
    allk = np.vstack([np.asarray(f["points"], float)[::40, :2] for f in facets])
    ax.scatter(allk[:, 0], allk[:, 1], s=0.4, c="0.82", linewidths=0,
               label="kept facet points (subsampled)")
    cmap = plt.get_cmap("tab10")
    for k, rpts in render:
        ax.scatter(rpts[:, 0], rpts[:, 1], s=1.4, color=cmap(k % 10),
                   linewidths=0, label=f"facet {k} removed "
                                       f"({len(rpts):,} pts)")
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    bar = 10.0 / ft
    ax.add_patch(Rectangle((x0 + 0.05 * (x1 - x0), y0 + 0.04 * (y1 - y0)),
                           bar, 0.008 * (y1 - y0), color="black"))
    ax.text(x0 + 0.05 * (x1 - x0), y0 + 0.055 * (y1 - y0), "10 ft", fontsize=9)
    ax.legend(loc="upper right", fontsize=7, markerscale=6, framealpha=0.9)
    ax.set_title(
        f"WHAT M1a LEAVES IN: the {total_removed:,} points the connectivity "
        f"filter would remove\n"
        f"at the canonical setting, drawn in place. Total alpha area "
        f"{total_rem_area:.2f} ft^2 = "
        f"{100 * total_rem_area / frozen_total:.3f} pct of the reported "
        f"{frozen_total:,.0f} ft^2.\n"
        f"R6: rendered before the mechanism is deprioritized.", fontsize=10)
    fig.tight_layout()
    png = out / f"m1a-area-exposure-{args.stamp}.png"
    fig.savefig(png, dpi=130, facecolor="white")
    plt.close(fig)

    print(f"\n{'f':>2} {'removed':>9} {'comps':>6} {'degen':>6} {'degen pts':>10} "
          f"{'rem area ft2':>13} {'facet ft2':>11} {'pct of facet':>13}")
    for r in rows:
        print(f"{r['facet']:>2} {r['n_removed']:>9,} "
              f"{r['n_removed_components']:>6,} "
              f"{r['n_degenerate_components']:>6,} "
              f"{r['points_in_degenerate_components']:>10,} "
              f"{r['removed_alpha_area_ft2']:>13.3f} "
              f"{r['facet_alpha_area_ft2']:>11.2f} "
              f"{r['removed_pct_of_facet_area']:>12.3f}%")
    t = docout["totals"]
    print(f"\n  TOTAL removed alpha area {t['removed_alpha_area_ft2']:.2f} ft^2")
    print(f"  = {t['removed_pct_of_main_facet_area']:.3f} pct of main facet area "
          f"({t['main_facet_alpha_area_ft2']:,.1f} ft^2)")
    print(f"  = {t['removed_pct_of_frozen_total']:.3f} pct of the reported "
          f"{frozen_total:,.0f} ft^2 total\n")
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check'][:84]}")
    print(f"  wrote {png}")
    print(f"  wrote {p}")


if __name__ == "__main__":
    main()
