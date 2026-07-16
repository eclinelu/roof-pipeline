# Pre-registration writer (decision 2026-07-14): freeze the pipeline's
# cloud-unit outputs into a JSON in the repo BEFORE the field visit.
# The human commits it; that commit hash is the pre-registration. Roof
# measurements taken afterward score THIS file and never edit it. A
# retune is a NEW run of this script, a NEW file, a NEW commit; both
# get reported.
#
#   python scripts/preregister.py C:\odm\datasets\big_house \
#       --candidate lines:j0,3-j0,5 --fallback length:r6,7
#
# The candidate ids come from roof_recon.py's ranked table (Emmett's
# choice of the primary span the tape measures, plus the documented
# fallback if the primary is not reachable on the roof). Use --dry-run
# to verify the numbers WITHOUT writing the dated freeze file: the real
# freeze is a deliberate act, run once, right before the roof visit.
#
# The report lands in the repo, a deliberate exception to "the repo
# holds only code": a frozen deliverable must live where the hash
# freezes it.
import argparse
import datetime
import json
import numpy as np
from pathlib import Path
from dataset_config import load_config
from recon_common import discover_facets
from roof_recon import intersection_lines, bracket_eaves, enumerate_candidates
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box
from roofkit.stats import median_nn_spacing
from roofkit.segment import level_cloud
from roofkit.measure import azimuth_degrees, facet_area, up_from_tilt

AREA_MAX_POINTS = 400_000  # same cap and reasoning as measure_roof.py


def pick(cands, cand_id):
    """Find a candidate by id, or abort listing the ids that exist so a
    typo fails loudly instead of silently freezing the wrong span."""
    match = [c for c in cands if c["cand_id"] == cand_id]
    if not match:
        raise SystemExit(f"candidate {cand_id!r} not found; ids: "
                         + ", ".join(c["cand_id"] for c in cands))
    return match[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--candidate", required=True,
                    help="cand_id of the chosen PRIMARY scale span")
    ap.add_argument("--fallback", default=None,
                    help="cand_id of the documented fallback span")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute and print, write NO file (verification)")
    ap.add_argument("--notes-file", default=None,
                    help="path to a free-text file recorded VERBATIM in the "
                         "freeze as the 'context' field: honest metadata "
                         "around the frozen numbers (e.g. that a span was "
                         "already taped, or that a prediction was refuted on "
                         "site). It does NOT alter any frozen number, and it "
                         "must not contain real-world units or scale, which "
                         "belong in the later comparison file.")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    rng = np.random.default_rng(0)

    roof = np.load(cfg["roof_path"])
    raw, _ = load_xyz_rgb(cfg["cloud_path"])
    raw, _ = crop_box(raw, cfg["crop_min"], cfg["crop_max"])
    up = up_from_tilt(cfg["level_tilt_deg"], cfg["level_uphill_az_deg"])
    roof, raw = level_cloud(roof, up), level_cloud(raw, up)
    origin = roof.min(axis=0)

    facets, band, s = discover_facets(roof, cfg)
    # Vanish guard (decision 2026-07-15): freezing fewer facets than the
    # verified count would silently corrupt the frozen totals. Fail loudly
    # before writing anything.
    if cfg["expected_facets"] is not None and len(facets) != cfg["expected_facets"]:
        raise SystemExit(f"expected {cfg['expected_facets']} facets, found "
                         f"{len(facets)}: a facet vanished or split. Freeze "
                         f"aborted; investigate before pre-registering.")
    lines = intersection_lines(facets, cfg["ridge_contact_mult"] * s, s)
    brackets = bracket_eaves(facets, raw, band, s)
    cands = enumerate_candidates(facets, lines, brackets, s, origin)
    primary = pick(cands, args.candidate)
    fallback = pick(cands, args.fallback) if args.fallback else None

    facet_rows = []
    for k, f in enumerate(facets):
        pts = f["points"]
        if len(pts) > AREA_MAX_POINTS:
            pts = pts[rng.choice(len(pts), AREA_MAX_POINTS, replace=False)]
        s_f = median_nn_spacing(pts)
        facet_rows.append({
            "facet": k, "points": int(len(f["points"])),
            "pitch_deg": round(float(f["pitch"]), 3),
            "azimuth_deg": round(azimuth_degrees(f["normal"]), 2),
            "area_cu2": round(facet_area(pts, f["normal"],
                                         alpha=cfg["alpha_mult"] * s_f), 3)})
    eave_rows = [
        {"facet": b["facet"], "rep_cu": b["rep"], "delta_cu": b["delta"],
         "flagged": b["flagged"]}
        for b in brackets if b is not None]
    # Free-text context: honest metadata AROUND the frozen numbers, never
    # altering them. Read verbatim from --notes-file (decision 2026-07-15:
    # this freeze is not scale-blind, the primary was refuted on site, and
    # dormers contaminate specific facets). None when no file is given.
    context = (Path(args.notes_file).read_text(encoding="utf-8")
               if args.notes_file else None)
    report = {
        "protocol": "decision 2026-07-14: outputs frozen BEFORE field "
                    "visit; this file is never edited",
        "context": context,
        "date": datetime.date.today().isoformat(),
        "dataset": Path(args.dataset).name,
        "config": {k: cfg[k] for k in
                   ("band_mult", "trim_mult", "min_points_frac", "max_planes",
                    "fit_sample", "alpha_mult", "ridge_contact_mult",
                    "level_tilt_deg", "level_uphill_az_deg",
                    "expected_facets")},
        "units": "cloud units (cu); one tape number converts, later",
        "facets": facet_rows,
        "eave_brackets": eave_rows,
        "total_area_cu2": round(sum(r["area_cu2"] for r in facet_rows), 3),
        "scale_candidate_primary": primary,
        "scale_candidate_fallback": fallback,
    }

    if args.dry_run:
        print(json.dumps(report, indent=2))
        out = (Path(__file__).resolve().parents[1] / "reports"
               / report["dataset"] / f"preregistered-{report['date']}.json")
        print(f"\nDRY RUN: wrote nothing. A real run would write {out}")
        return

    out_dir = Path(__file__).resolve().parents[1] / "reports" / report["dataset"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"preregistered-{report['date']}.json"
    if out.exists():
        raise SystemExit(f"{out} already exists; a retune is a NEW dated "
                         "file, and the old one is never overwritten")
    out.write_text(json.dumps(report, indent=2))
    print(f"wrote {out}")
    print("NOW COMMIT IT. The commit hash is the pre-registration. Only "
          "then does anyone climb the roof.")


if __name__ == "__main__":
    main()
