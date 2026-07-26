# Coverage-driven recon (Task 4, 2026-07-21). Runs the SAME leveling and
# main-facet discovery the frozen instrument runs, then applies the
# completeness gate (roofkit.coverage) to recover the facets that
# expected_facets used to hide: the dormers. expected_facets is NOT a gate
# here; it becomes an optional post-hoc assertion only.
#
#   python scripts/coverage_recon.py C:\odm\datasets\big_house
#
# Emits: main facets (== the freeze), fit-quality bar, threshold plateau
# sweep, coverage masks + residual blobs, recovered dormer facets, the
# pairwise facet matrix (no merge), area accounting (gross/occluded/net
# under highest-surface-wins), the total decomposed against the frozen
# total, coverage %, and a NEW comparison file. The frozen file is never
# touched.
import argparse
import gc
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config
from recon_common import discover_facets
from roofkit.segment import level_cloud
from roofkit.measure import up_from_tilt, azimuth_degrees
from roofkit import coverage as cov

COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
REPO = Path(__file__).resolve().parents[1]

FROZEN = REPO / "reports/big_house/preregistered-2026-07-18.json"


def circ_daz(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def match_frozen(my_facets, frozen):
    """Match each of my main facets to the nearest frozen facet by (pitch,
    azimuth), so per-facet deltas line up despite RANSAC discovery order."""
    fro = frozen["facets"]
    out = []
    used = set()
    for f in my_facets:
        az = azimuth_degrees(f["normal"])
        best, bd = None, 1e9
        for fr in fro:
            if fr["facet"] in used:
                continue
            d = abs(f["pitch"] - fr["pitch_deg"]) + circ_daz(az, fr["azimuth_deg"])
            if d < bd:
                bd, best = d, fr
        used.add(best["facet"])
        out.append(best)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    frozen = json.loads(FROZEN.read_text())

    points = np.load(cfg["roof_path"])
    if cfg["level_tilt_deg"] is not None:
        up = up_from_tilt(cfg["level_tilt_deg"], cfg["level_uphill_az_deg"])
        points = level_cloud(points, up)
        print(f"LEVELED: {cfg['level_tilt_deg']:.3f} deg removed\n")

    # 1. main facets, IDENTICAL discovery to the freeze
    facets, band, s_full = discover_facets(points, cfg)
    matched = match_frozen(facets, frozen)
    print(f"1. MAIN FACETS: {len(facets)} discovered, band {band:.4f} cu, "
          f"spacing {s_full:.4f} cu")
    print(f"   {'mine':>4} {'pitch':>6} {'az':>6}  matched frozen "
          f"{'fz_pitch':>8} {'fz_area':>8}")
    for k, (f, fr) in enumerate(zip(facets, matched)):
        print(f"   {k:>4} {f['pitch']:>6.2f} {azimuth_degrees(f['normal']):>6.1f}  "
              f"-> facet {fr['facet']}    {fr['pitch_deg']:>8.2f} {fr['area_cu2']:>8.2f}")

    # 2. fit-quality bar from the main facets
    bar, ratios = cov.calibrate_quality_bar(facets, s_full)
    print(f"\n2. FIT-QUALITY BAR (max main-facet trimmed RMS/spacing): {bar:.3f}")
    print(f"   per-facet RMS/spacing: " + " ".join(f"{r:.2f}" for r in ratios))

    # 3. coverage masks
    cell = COVERAGE_CELL_MULT * s_full
    masks, g, owner, dist = cov.coverage_masks(points, facets, band, cell)
    gc.collect()
    print(f"\n3. COVERAGE cell {cell:.4f} cu; building "
          f"{int(masks['building'].sum()):,} interior "
          f"{int(masks['interior'].sum()):,} residual "
          f"{int(masks['residual'].sum()):,}")

    # 4. threshold plateau sweep (justifies MIN_BLOB_AREA). Label the residual
    # ONCE, then count components above each threshold by array comparison.
    print(f"\n4. THRESHOLD PLATEAU SWEEP (blob count vs min area):")
    print(f"   {'min_area_cu2':>13} {'blob_count':>10}")
    areas = cov.blob_areas(masks["residual"], cell)
    sweep = []
    for thr in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.75, 1.0, 1.5, 2.0]:
        nb = int((areas >= thr).sum())
        sweep.append((thr, nb))
        print(f"   {thr:>13.2f} {nb:>10}")

    # 5. residual blobs at the chosen threshold
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    print(f"\n5. RESIDUAL BLOBS at {MIN_BLOB_AREA} cu^2: {len(blobs)}")
    for bi, b in enumerate(blobs):
        (x0, y0), _ = b["box"]
        print(f"   blob {bi}: {b['area_cu2']:.2f} cu^2  X~{x0:.0f} Y~{y0:.0f}")

    # 6. recover facets (relaxed SIZE, identical QUALITY)
    log = []
    new = cov.recover_facets(points, blobs, owner, dist, band, s_full, bar, log=log)
    print(f"\n6. RECOVERED {len(new)} facets (relaxed size, fixed quality):")
    for e in log:
        head = f"   blob {e['blob']} ({e['area_cu2']:.2f} cu^2, {e['n_candidate']:,} unexpl pts)"
        if e.get("skipped"):
            print(head + f": SKIP {e['skipped']}"); continue
        print(head + ":")
        for p in e["planes"]:
            print(f"       {p['n']:>6,} pts pitch {p['pitch']:>5} "
                  f"quality {p['quality']:>5}/{p['bar']} "
                  f"-> {'KEEP' if p['kept'] else 'reject'}")

    allf = facets + new
    del owner, dist          # recovery is done with them; free before area work
    gc.collect()

    # 6b. RECOMPUTE coverage with ALL facets: this is the post-recovery
    # completeness the pass condition targets (near 100%, residual at the
    # perimeter ring). The #3 number was pre-recovery, main facets only.
    masks2, g2, _, _ = cov.coverage_masks(points, allf, band, cell)
    frac2 = cov.coverage_fraction(masks2)
    resid2 = cov.residual_blobs(masks2["residual"], g2, MIN_BLOB_AREA)
    # how much remaining residual touches the eroded interior vs sits near
    # the perimeter: report the largest few remaining interior blobs
    print(f"\n6b. POST-RECOVERY coverage: {100*frac2:.1f}% "
          f"(was {100*cov.coverage_fraction(masks):.1f}% pre-recovery)")
    print(f"    remaining interior residual blobs >= {MIN_BLOB_AREA} cu^2: "
          f"{len(resid2)}")
    for b in resid2[:8]:
        (x0, y0), _ = b["box"]
        print(f"      {b['area_cu2']:.2f} cu^2  X~{x0:.0f} Y~{y0:.0f}")

    # 7. pairwise matrix over ALL facets (no merge, no tolerance)
    ang, off = cov.pairwise_matrix(allf)
    print(f"\n7. PAIRWISE MATRIX (angle deg / offset cu), {len(allf)} facets "
          f"[main 0-{len(facets)-1}, new {len(facets)}-{len(allf)-1}]:")
    hdr = "        " + " ".join(f"{j:>10}" for j in range(len(allf)))
    print(hdr)
    for i in range(len(allf)):
        cells = []
        for j in range(len(allf)):
            cells.append("     -    " if i == j else f"{ang[i,j]:>4.1f}/{off[i,j]:>4.2f}")
        print(f"   {i:>3}  " + " ".join(cells))
    # flag near-coplanar pairs (report only)
    print("   near-coplanar pairs (angle<2deg AND offset<0.10cu), REPORT ONLY:")
    found = False
    for i in range(len(allf)):
        for j in range(i+1, len(allf)):
            if ang[i, j] < 2.0 and off[i, j] < 0.10:
                print(f"     facets {i} & {j}: angle {ang[i,j]:.2f} deg, "
                      f"offset {off[i,j]:.3f} cu -> possible over-segmentation")
                found = True
    if not found:
        print("     none")

    # 8. area accounting (gross/occluded/net) under highest-surface-wins
    rows, totals = cov.area_accounting(allf, s_full, cfg["alpha_mult"], cell)
    print(f"\n8. AREA ACCOUNTING (highest surface wins), cu^2:")
    print(f"   {'facet':>5} {'kind':>6} {'pitch':>6} {'gross':>8} {'occluded':>9} {'net':>8}")
    for k, r in enumerate(rows):
        kind = "main" if k < len(facets) else "dormer"
        print(f"   {k:>5} {kind:>6} {r['pitch']:>6.2f} {r['gross']:>8.2f} "
              f"{r['occluded']:>9.3f} {r['net']:>8.2f}")
    print(f"   {'TOTAL':>5} {'':>6} {'':>6} {totals['gross']:>8.2f} "
          f"{totals['occluded']:>9.3f} {totals['net']:>8.2f}")

    # 9. decomposition against the frozen total
    frz = frozen["total_area_cu2"]
    main_net = sum(r["net"] for r in rows[:len(facets)])
    dorm_net = sum(r["net"] for r in rows[len(facets):])
    dorm_gross = sum(r["gross"] for r in rows[len(facets):])
    occ_total = totals["occluded"]
    print(f"\n9. DECOMPOSITION vs frozen total {frz:.3f} cu^2:")
    print(f"   frozen total (8 main facets)          : {frz:>9.3f}")
    print(f"   my main-facet net (should ~= frozen)  : {main_net:>9.3f}  "
          f"(delta {main_net-frz:+.3f})")
    print(f"   + dormer gross slope area             : {dorm_gross:>9.3f}")
    print(f"   - occlusion (parents lose counted overlap): {occ_total:>9.3f}")
    print(f"   = new total net                       : {totals['net']:>9.3f}")
    print(f"   net change vs frozen                  : {totals['net']-frz:>+9.3f} "
          f"({100*(totals['net']-frz)/frz:+.2f}%)")

    # 10. coverage fraction (post-recovery is the pass number)
    frac = frac2
    unexpl_plan = int(masks2["residual"].sum()) * cell * cell
    print(f"\n10. COVERAGE (post-recovery interior explained): {100*frac:.1f}%")
    print(f"    unexplained interior plan area: {unexpl_plan:.2f} cu^2 "
          f"across {len(resid2)} remaining blobs (see #6b)")
    print(f"    facet count: {len(facets)} -> {len(allf)}")

    # write comparison file (NEW file; frozen untouched)
    out = REPO / f"reports/big_house/coverage-comparison-{date.today()}.json"
    doc = dict(
        protocol="coverage run; frozen file is a read-only input, never edited",
        date=str(date.today()), dataset="big_house",
        inputs=dict(frozen=FROZEN.name, roof="roof.npy"),
        config=dict(coverage_cell_mult=COVERAGE_CELL_MULT,
                    min_blob_area_cu2=MIN_BLOB_AREA, band_cu=band,
                    quality_bar=bar, cell_cu=cell),
        facet_count=dict(frozen=len(facets), coverage=len(allf)),
        threshold_sweep=[dict(min_area=t, blobs=n) for t, n in sweep],
        area=dict(rows=[dict(facet=k, kind=("main" if k < len(facets) else "dormer"),
                             pitch=round(r["pitch"], 3), gross=round(r["gross"], 3),
                             occluded=round(r["occluded"], 4), net=round(r["net"], 3))
                        for k, r in enumerate(rows)],
                  total_gross=round(totals["gross"], 3),
                  total_occluded=round(totals["occluded"], 4),
                  total_net=round(totals["net"], 3)),
        decomposition=dict(frozen_total=frz, my_main_net=round(main_net, 3),
                           dormer_gross=round(dorm_gross, 3),
                           occlusion=round(occ_total, 4),
                           new_total_net=round(totals["net"], 3),
                           change=round(totals["net"] - frz, 3),
                           change_pct=round(100*(totals["net"]-frz)/frz, 3)),
        coverage_pct=round(100*frac, 2),
        unexplained_plan_cu2=round(unexpl_plan, 3),
        pairwise_note="raw matrix printed to stdout; no merge performed")
    out.write_text(json.dumps(doc, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
