# House-agnostic data layer for the PDF roof report.
#
# This module does NO rendering and touches NO point cloud. It reads the
# frozen pre-registration, the comparison (scored) file, the ground-truth
# record, and the dataset's roofkit.json, then reshapes them into the
# tables and labels the report pages need. Keeping it separate from the
# drawing code means the label mapping, the unit conversions, and the
# graceful-degradation logic can be unit-tested without rendering anything,
# and it enforces the project rule that nothing house-specific is baked
# into the report code: every house-specific value arrives from a file.
#
# Vocabulary used throughout (plain language, defined once):
#   freeze / pre-registration : the JSON the pipeline wrote and committed
#       BEFORE any tape measurement was taken. Cloud-unit geometry only.
#   comparison / scored file  : the JSON that scored the freeze against the
#       field measurements. This is where real-world claims (feet, degrees
#       of error, pass/fail) live. The report quotes claims from HERE.
#   segmentation index        : the arbitrary 0..7 order RANSAC happened to
#       find the facets in. Not meaningful to a reader.
#   facet label (A, B, C...)  : a STABLE name we assign, smallest roof area
#       first, following the EagleView convention. Same label on every page.
#   cloud unit (cu)           : the reconstruction's arbitrary length unit.
#       One tape measurement converts cu to feet (the scale multiplier).
#   pitch                     : the slope of a roof face from horizontal, in
#       degrees. Scale-independent (it is a ratio), unlike area.
#   x:12                      : the roofer's way of stating pitch as "x
#       inches of rise per 12 inches of run". x = 12 * tan(pitch).
import json
import math
import subprocess
from pathlib import Path


# --- Loading the raw files -------------------------------------------------

def _read_json(path):
    return json.loads(Path(path).read_text())


def newest(glob_dir, pattern):
    """Newest file matching a glob, or None. Used so the report always
    picks up the latest freeze / comparison without a hardcoded date."""
    hits = sorted(Path(glob_dir).glob(pattern))
    return hits[-1] if hits else None


def load_inputs(dataset_name, repo_root, dataset_dir):
    """Gather every input the report needs for one house.

    dataset_name : e.g. "big_house" (used only to find the reports folder)
    repo_root    : the roof-pipeline repo root (holds reports/<name>/)
    dataset_dir  : the ODM workspace dir holding the cloud + roofkit.json

    Returns a dict. Everything the pages read comes out of here, so if a
    file is missing the degradation happens in ONE place (a None value),
    not scattered through the drawing code.
    """
    reports = Path(repo_root) / "reports" / dataset_name
    freeze_path = newest(reports, "preregistered-*.json")
    comp_path = newest(reports, "comparison-*-scored-*.json")
    truth_path = newest(reports, "ground-truth-*.json")

    freeze = _read_json(freeze_path) if freeze_path else None
    comparison = _read_json(comp_path) if comp_path else None
    truth = _read_json(truth_path) if truth_path else None

    # roofkit.json holds all site-specific numbers (decision 2026-07-12).
    cfg_path = Path(dataset_dir) / "roofkit.json"
    config = _read_json(cfg_path) if cfg_path.exists() else {}

    # The run-1 comparison is the baseline the validation page reports
    # FIRST (the failure before the fix). It is whichever scored comparison
    # is NOT the newest one, if more than one exists.
    comps = sorted(reports.glob("comparison-*-scored-*.json"))
    baseline_comp = _read_json(comps[0]) if len(comps) >= 2 else None

    return {
        "dataset": dataset_name,
        "freeze_path": freeze_path,
        "comparison_path": comp_path,
        "truth_path": truth_path,
        "freeze": freeze,
        "comparison": comparison,
        "truth": truth,
        "baseline_comparison": baseline_comp,
        "config": config,
        "provenance": _provenance(repo_root, freeze_path, config),
    }


def _git(repo_root, *args):
    """Run a git command in the repo; return stripped stdout or None.
    Never raises: provenance is nice-to-have, not load-bearing, so a
    non-git checkout degrades to 'unversioned' rather than crashing."""
    try:
        out = subprocess.run(["git", "-C", str(repo_root), *args],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def _provenance(repo_root, freeze_path, config):
    """Cover-page provenance: property name, flight date, pipeline version,
    and the git commit of the freeze being reported. Flight date and
    property name are house-specific, so they come from roofkit.json's
    optional report_meta block; everything else is derived from git or
    degrades to a clear placeholder."""
    meta = config.get("report_meta", {}) if isinstance(config, dict) else {}

    # git commit that last touched THIS freeze file = the freeze's identity.
    freeze_commit = None
    if freeze_path is not None:
        freeze_commit = _git(repo_root, "log", "-1", "--format=%h",
                             "--", str(freeze_path))
    head = _git(repo_root, "log", "-1", "--format=%h")

    return {
        "property_name": meta.get("property_name"),   # None -> use dataset
        "flight_date": meta.get("flight_date"),        # None -> 'not recorded'
        "pipeline_version": _pipeline_version(repo_root, head),
        "freeze_commit": freeze_commit,                # None -> 'uncommitted'
        "head_commit": head,
    }


def _pipeline_version(repo_root, head):
    """A human-facing version string for the cover: the packaged roofkit
    version plus the short HEAD commit, e.g. 'roofkit 0.1.0 (bdecd8a)'."""
    ver = None
    pyproject = Path(repo_root) / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text().splitlines():
            s = line.strip()
            if s.startswith("version"):
                ver = s.split("=", 1)[1].strip().strip('"').strip("'")
                break
    parts = []
    if ver:
        parts.append(f"roofkit {ver}")
    if head:
        parts.append(f"({head})")
    return " ".join(parts) if parts else "unversioned"


# --- Facet labeling (A, B, C... smallest area first) -----------------------

def label_facets(inputs):
    """Assign a stable label to every facet, smallest roof area first
    (EagleView convention), and join together everything the tables need
    per facet: the label, the arbitrary segmentation index, area in cu and
    ft2, pitch, azimuth, the pitch error and truth data, and the caveat
    flags (dormer, flagged eave, panel region).

    Returns a list of per-facet dicts sorted A, B, C.... The segmentation
    index is preserved in every dict so the report's mapping table can
    cross-reference the freeze and comparison files unambiguously.
    """
    freeze = inputs["freeze"]
    comparison = inputs["comparison"]
    if freeze is None:
        return []

    # Index the comparison's per-facet rows by segmentation index so we can
    # join. Both files key facets by the same integer index.
    comp_area = {}
    comp_pitch = {}
    if comparison is not None:
        for a in comparison.get("areas", []):
            comp_area[a["facet"]] = a
        for p in comparison.get("pitch", []):
            comp_pitch[p["facet"]] = p

    # Flagged-eave lookup from the freeze's eave brackets: a flagged bracket
    # means the loose/tight eave disagreement is wide enough to suspect
    # gutter/fascia/vegetation contamination at that eave (decision
    # 2026-07-15), which is a per-facet reliability caveat worth surfacing.
    eave_flag = {}
    for b in freeze.get("eave_brackets", []):
        eave_flag[b["facet"]] = bool(b.get("flagged", False))

    rows = []
    for f in freeze["facets"]:
        idx = f["facet"]
        area = comp_area.get(idx, {})
        pitch = comp_pitch.get(idx, {})
        rows.append({
            "seg_index": idx,
            "area_cu2": f.get("area_cu2"),
            "area_ft2": area.get("area_ft2"),      # None if not scored yet
            "pitch_deg": f.get("pitch_deg"),
            "azimuth_deg": f.get("azimuth_deg"),
            "x12": pitch_to_x12(f.get("pitch_deg")),
            "dormer": area.get("dormer") or pitch.get("dormer"),
            "eave_flagged": eave_flag.get(idx, False),
            "panel_region": area.get("panel_region"),  # for later houses
            # pitch validation fields (present once scored):
            "truth_mean_deg": pitch.get("truth_mean_deg"),
            "truth_spread_deg": pitch.get("truth_spread_deg"),
            "truth_raw_deg": pitch.get("truth_raw_deg"),
            "truth_used_deg": pitch.get("truth_used_deg"),
            "converted_90_minus": pitch.get("converted_90_minus"),
            "pitch_error_deg": pitch.get("error_deg"),
            "within_2deg": pitch.get("within_2deg"),
            "within_3deg": pitch.get("within_3deg"),
        })

    # Sort by area ascending. Fall back to cu area if ft2 is not scored yet,
    # so labeling still works on an un-scored freeze (graceful degradation).
    def sort_key(r):
        return (r["area_ft2"] if r["area_ft2"] is not None
                else r["area_cu2"] if r["area_cu2"] is not None else 0.0)

    rows.sort(key=sort_key)
    for i, r in enumerate(rows):
        r["label"] = chr(ord("A") + i)
    return rows


# --- Pitch helpers ---------------------------------------------------------

def pitch_to_x12(pitch_deg):
    """Nearest x:12 for a pitch in degrees: x = 12 * tan(pitch), rounded to
    the nearest whole inch of rise. This is a ROUNDING of the degree value
    for a contractor's convenience, not an independent measurement; the
    report states that explicitly on the page. Returns None on missing input."""
    if pitch_deg is None:
        return None
    return round(12.0 * math.tan(math.radians(pitch_deg)))


# Pitch bands for color-coding and grouping. Bands are named by the nearest
# common roof pitch; big_house has two families (~20-22 deg and ~33-34 deg).
# Boundaries are in degrees and are generic, not tuned to one house.
PITCH_BANDS = [
    # (low_deg_inclusive, high_deg_exclusive, name, hex color)
    (0.0, 10.0, "Low (<10 deg)", "#4575b4"),
    (10.0, 26.0, "Shallow (10-26 deg)", "#74add1"),
    (26.0, 38.0, "Steep (26-38 deg)", "#f46d43"),
    (38.0, 90.1, "Very steep (>38 deg)", "#d73027"),
]


def pitch_band(pitch_deg):
    """Return (name, color) for a pitch. Used to color facets on the pitch
    view and to group the areas-per-pitch table. None -> a neutral gray."""
    if pitch_deg is None:
        return ("Unknown", "#999999")
    for lo, hi, name, color in PITCH_BANDS:
        if lo <= pitch_deg < hi:
            return (name, color)
    return ("Unknown", "#999999")


# --- Materials / waste tables ----------------------------------------------

# A roofing "square" is 100 ft2 of roof surface: the unit shingles are sold
# and estimated in. Waste percentages are the standard allowances a
# contractor adds for cuts, starter courses, hips and valleys. These are
# generic industry values, not house-specific, so they live in code.
WASTE_PCTS = [0, 10, 12, 15, 17, 20, 22]


def squares_table(total_ft2, waste_pcts=WASTE_PCTS):
    """Convert a total roof area into roofing squares at several waste
    allowances. Returns rows of (waste_pct, area_with_waste_ft2, squares).
    Pure arithmetic on the total; the total's dormer caveat is carried
    separately by the caller and printed with the table."""
    if total_ft2 is None:
        return []
    rows = []
    for w in waste_pcts:
        adj = total_ft2 * (1.0 + w / 100.0)
        rows.append({
            "waste_pct": w,
            "area_ft2": adj,
            "squares": adj / 100.0,
        })
    return rows


def areas_per_pitch(labeled):
    """Group facet areas by pitch band for the materials summary. Returns
    rows of (band_name, color, total_ft2, facet_labels) sorted by pitch."""
    groups = {}
    for r in labeled:
        name, color = pitch_band(r["pitch_deg"])
        g = groups.setdefault(name, {"name": name, "color": color,
                                     "area_ft2": 0.0, "labels": []})
        if r["area_ft2"] is not None:
            g["area_ft2"] += r["area_ft2"]
        g["labels"].append(r["label"])
    # order groups by the band table order
    order = {name: i for i, (_, _, name, _) in enumerate(PITCH_BANDS)}
    return sorted(groups.values(), key=lambda g: order.get(g["name"], 99))


def predominant_pitch(labeled):
    """The pitch band covering the most roof AREA (not the most facets):
    what a reader means by 'the roof's pitch'. Returns (band_name,
    representative_pitch_deg, x12_string) or (None, None, None)."""
    if not labeled:
        return (None, None, None)
    per_band = areas_per_pitch(labeled)
    if not per_band:
        return (None, None, None)
    top = max(per_band, key=lambda g: g["area_ft2"])
    # representative pitch = area-weighted mean pitch of facets in that band
    members = [r for r in labeled
               if pitch_band(r["pitch_deg"])[0] == top["name"]
               and r["pitch_deg"] is not None]
    if not members:
        return (top["name"], None, None)
    wsum = sum((r["area_ft2"] or 0.0) for r in members)
    if wsum > 0:
        mean = sum(r["pitch_deg"] * (r["area_ft2"] or 0.0)
                   for r in members) / wsum
    else:
        mean = sum(r["pitch_deg"] for r in members) / len(members)
    x12 = pitch_to_x12(mean)
    return (top["name"], mean, f"{x12}:12" if x12 is not None else None)
