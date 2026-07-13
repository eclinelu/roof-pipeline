# Per-dataset configuration. Site-specific numbers (crop box, height
# cutoff, tuned cutoffs) describe a DATASET, so they live in a JSON file
# next to that dataset's data (<dataset>\roofkit.json), never in code.
# The pipeline code is identical for every cloud; only the config differs.
# Same seam principle as io.py: swap the dataset, nothing else changes.
import json
from pathlib import Path

DEFAULTS = {
    # relative to the dataset directory
    "cloud": "odm_georeferencing/odm_georeferenced_model.laz",
    # --- site-specific, filled in from the viewer (stage 0 / 1) ---
    "crop_min": None,        # [x, y, z]
    "crop_max": None,        # [x, y, z]
    "z_min": None,           # just below eave height, cloud units
    # --- scale-independent cutoffs (transfer between clouds) ---
    "exg_max": 0.1,          # unitless ExG color cutoff
    "score_max": 0.05,       # unitless planarity cutoff
    "trim_mult": 3.0,        # robust refit trim = trim_mult x median scatter
                             # (unitless ratio; trim distance adapts per facet)
    # --- multiples of median_nn_spacing (scale-adaptive) ---
    "radius_mult": 5.0,      # planarity radius = radius_mult * spacing
    "band_mult": 3.0,        # RANSAC band = band_mult * spacing
    "alpha_mult": 4.0,       # alpha shape radius = alpha_mult * spacing
    # --- density-dependent ---
    "min_points_frac": 0.03, # a facet must hold this fraction of roof points
    "fit_sample": 200000,    # RANSAC discovery subsample; membership, refit,
                             # pitch and area always use the full cloud
    "max_planes": 12,        # safety ceiling on the peeling loop; the real
                             # floor is min_points_frac
    # --- design constants ---
    "gate_limit_deg": 1.0,   # reject georeferenced Z above this residual
}


def load_config(dataset_dir):
    """Read <dataset>/roofkit.json over the defaults. Writes a template on
    first use so every new dataset starts from the same documented knobs."""
    dataset_dir = Path(dataset_dir)
    path = dataset_dir / "roofkit.json"
    cfg = dict(DEFAULTS)
    if path.exists():
        cfg.update(json.loads(path.read_text()))
    else:
        path.write_text(json.dumps(cfg, indent=2))
        print(f"Wrote template config {path}. Fill in crop_min/crop_max/"
              f"z_min from the viewer before stages 1+.")
    cfg["cloud_path"] = str(dataset_dir / cfg["cloud"])
    cfg["roof_path"] = str(dataset_dir / "roof.npy")
    return cfg
