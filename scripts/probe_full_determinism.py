# Task 6A, part 2: does the determinism fix disturb the FROZEN main facets,
# and is the WHOLE pipeline reproducible once it is applied?
#
#   .venv/Scripts/python.exe -u scripts/probe_full_determinism.py C:/odm/datasets/big_house
#
# Writes reports/big_house/full-determinism-<date>.json     (standing rule R2)
#
# ---------------------------------------------------------------------------
# THE QUESTION THIS ANSWERS
#
# probability=1.0 makes recovery reproducible (measured: 25/25 identical). But
# discovery of the MAIN facets calls the same RANSAC, and the main facets are
# what the frozen pre-registration rests on. So before adopting the fix
# everywhere, two things must be measured, not assumed:
#
#   1. Does probability=1.0 CHANGE the main facets? If the pitches still match
#      the frozen file, the fix is free and can be applied everywhere. If they
#      move, adopting it pipeline-wide restates a frozen result, which is a
#      decision only Emmett makes.
#   2. Is the main-facet fit itself reproducible? It was measured "stable to
#      0.0004 deg", which is NOT the same as identical. 0.0004 deg of wobble is
#      harmless for pitch but means the fit is still not replayable exactly.
#
# Everything is compared against reports/big_house/preregistered-2026-07-18.json,
# which is READ ONLY here and never modified.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config
from recon_common import discover_facets
from roofkit.stats import median_nn_spacing
from roofkit.segment import level_cloud
from roofkit.measure import up_from_tilt, azimuth_degrees
from roofkit import coverage as cov

COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/big_house"
FROZEN = OUT / "preregistered-2026-07-18.json"


def circ_daz(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def match_frozen(my_facets, frozen):
    """Pair each fitted facet with its frozen counterpart by (pitch, azimuth),
    since RANSAC discovery ORDER is not meaningful."""
    fro, out, used = frozen["facets"], [], set()
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


def discovery_reps(points, cfg, spacing, prob, reps):
    """Run main-facet discovery `reps` times at a given probability, re-seeding
    identically each time. Returns per-rep facet summaries."""
    got = []
    for _ in range(reps):
        facets, band, _ = discover_facets(points, cfg, probability=prob,
                                          spacing=spacing)
        got.append([dict(pitch=float(f["pitch"]),
                         az=float(azimuth_degrees(f["normal"])),
                         n=int(len(f["points"]))) for f in facets])
    return got


def stability(got):
    """Count stability + worst per-index pitch spread across reps."""
    counts = sorted({len(g) for g in got})
    if len(counts) != 1:
        return dict(count_stable=False, counts=counts,
                    worst_pitch_spread_deg=None, bit_identical=False)
    n = counts[0]
    worst = max(max(g[k]["pitch"] for g in got) - min(g[k]["pitch"] for g in got)
                for k in range(n))
    exact = all(all(got[0][k]["n"] == g[k]["n"] for k in range(n)) for g in got)
    return dict(count_stable=True, counts=counts,
                worst_pitch_spread_deg=round(float(worst), 6),
                bit_identical=bool(exact))


def vs_frozen(facets_summary, facets_objs, frozen):
    """Largest pitch difference against the frozen pre-registration."""
    matched = match_frozen(facets_objs, frozen)
    rows, worst = [], 0.0
    for f, fr in zip(facets_objs, matched):
        d = abs(float(f["pitch"]) - float(fr["pitch_deg"]))
        worst = max(worst, d)
        rows.append(dict(frozen_facet=fr["facet"],
                         frozen_pitch=fr["pitch_deg"],
                         fitted_pitch=round(float(f["pitch"]), 4),
                         delta_deg=round(d, 5)))
    return dict(worst_delta_deg=round(float(worst), 5), per_facet=rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--reps", type=int, default=5)
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    frozen = json.loads(FROZEN.read_text())
    OUT.mkdir(parents=True, exist_ok=True)

    points = np.load(cfg["roof_path"])
    if cfg["level_tilt_deg"] is not None:
        points = level_cloud(points, up_from_tilt(cfg["level_tilt_deg"],
                                                  cfg["level_uphill_az_deg"]))
    # Computed ONCE and reused: it is a deterministic property of the points,
    # so sharing it changes no result and removes the dominant per-rep cost.
    spacing = median_nn_spacing(points)
    print(f"spacing {spacing:.6f} cu; frozen total "
          f"{frozen['total_area_cu2']:.3f} cu^2")

    results = {}
    for label, prob in (("default_probability", 0.99999999),
                        ("probability_1.0", 1.0)):
        got = discovery_reps(points, cfg, spacing, prob, args.reps)
        st = stability(got)
        # refit once more to get real facet objects for the frozen comparison
        facets, band, _ = discover_facets(points, cfg, probability=prob,
                                          spacing=spacing)
        fz = vs_frozen(got[0], facets, frozen)
        results[label] = dict(probability=prob, reps=args.reps,
                              stability=st, versus_frozen=fz,
                              n_facets=len(facets),
                              band_cu=round(float(band), 6))
        print(f"  discovery @ {label:<20} count_stable={st['count_stable']} "
              f"spread={st['worst_pitch_spread_deg']} "
              f"bit_identical={st['bit_identical']}  "
              f"worst delta vs frozen {fz['worst_delta_deg']} deg")

    # FULL pipeline (discovery + recovery) at probability=1.0, end to end.
    print(f"\nfull pipeline @ probability=1.0, {args.reps} reps:")
    full = []
    for _ in range(args.reps):
        facets, band, s_full = discover_facets(points, cfg, probability=1.0,
                                               spacing=spacing)
        bar, _ = cov.calibrate_quality_bar(facets, s_full)
        cell = COVERAGE_CELL_MULT * s_full
        masks, g, _, dist = cov.coverage_masks(points, facets, band, cell)
        blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
        new = cov.recover_facets(points, blobs, None, dist, band, s_full, bar,
                                 alpha_mult=cfg["alpha_mult"], probability=1.0)
        allf = facets + new
        full.append([dict(pitch=float(f["pitch"]), n=int(len(f["points"])))
                     for f in allf])
        print(f"  rep: {len(facets)} main + {len(new)} recovered = {len(allf)}")
    fst = stability(full)
    print(f"  FULL PIPELINE count_stable={fst['count_stable']} "
          f"counts={fst['counts']} spread={fst['worst_pitch_spread_deg']} "
          f"bit_identical={fst['bit_identical']}")

    doc = dict(
        task="6A part 2: does the determinism fix move the frozen main facets, "
             "and is the full pipeline reproducible",
        dataset="big_house", date=str(date.today()), reps=args.reps,
        frozen_file=FROZEN.name,
        frozen_note="read-only input; never edited",
        spacing_cu=round(float(spacing), 6),
        discovery=results,
        full_pipeline=dict(probability=1.0, stability=fst,
                           counts_per_rep=[len(f) for f in full]),
        interpretation=dict(
            frozen_safe=("compare discovery.probability_1.0.versus_frozen."
                         "worst_delta_deg against the frozen file's own "
                         "reported precision; a delta at or below the "
                         "0.0004 deg run-to-run wobble already measured means "
                         "the fix does not restate the frozen result"),
            gate="Emmett's gate: facet COUNT stable across repeated runs"))
    p = OUT / f"full-determinism-{date.today()}.json"
    p.write_text(json.dumps(doc, indent=2, default=float))
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
