# Replay the canonical facet state from disk (standing rule R1).
#
# Every Task 6 diagnostic reads the state through this module instead of
# re-running the fit. That matters for two reasons:
#
#   1. A diagnostic that re-fits is describing ITS OWN fit, not the state under
#      discussion. That is exactly how the 2026-07-23 numbers became
#      unverifiable. Loading from disk removes the question entirely.
#   2. It is fast. Rebuilding costs a median-spacing pass over 9.3M points plus
#      every RANSAC call; loading costs one np.load.
#
# There is NO fitting in this file and no randomness. It reads row numbers and
# indexes an array.
import hashlib
import json
from pathlib import Path

import numpy as np

from dataset_config import load_config
from roofkit.segment import level_cloud
from roofkit.measure import up_from_tilt

REPO = Path(__file__).resolve().parents[1]


def leveled_points(cfg):
    """The exact point array the canonical state indexes into: roof.npy put
    through level_cloud when the dataset declares a leveling correction.
    Leveling is a rotation, so it moves points without reordering them."""
    pts = np.load(cfg["roof_path"])
    if cfg["level_tilt_deg"] is not None:
        pts = level_cloud(pts, up_from_tilt(cfg["level_tilt_deg"],
                                            cfg["level_uphill_az_deg"]))
    return pts


def load_canonical(dataset, stamp, verify_cloud=True):
    """Load the canonical state. Returns (doc, points, facets, cfg) where
    facets is a list of dicts with points / normal / pitch / idx / kind, in the
    same order as doc["facets"].

    verify_cloud re-hashes the point array and compares it with the hash stored
    when the state was written. Indices are just row numbers, so pointing them
    at a DIFFERENT cloud would silently select the wrong geometry and report it
    confidently. The hash makes that impossible rather than unlikely."""
    name = Path(dataset).name
    out = REPO / "reports" / name
    doc = json.loads((out / f"canonical-{stamp}.json").read_text())
    cfg = load_config(dataset)
    points = leveled_points(cfg)

    if verify_cloud:
        want = doc["replay"]["source_cloud_sha256"]
        got = hashlib.sha256(
            np.ascontiguousarray(points, dtype=np.float64).tobytes()).hexdigest()
        if got != want:
            raise SystemExit(
                f"cloud mismatch: canonical-{stamp}.json was built on a cloud "
                f"hashing {want[:16]}..., this one hashes {got[:16]}.... The "
                f"saved indices do not describe these points; refusing to "
                f"report numbers about the wrong geometry.")

    npz = np.load(out / doc["replay"]["npz"])
    facets = []
    for row in doc["facets"]:
        idx = npz[f"facet_{row['facet']}"]
        # The saved plane is (a, b, c, d) with a unit normal. Only (a, b, c) is
        # the normal; d is the offset and is reconstructed from the points, so
        # it is not needed here, but it IS what makes two parallel surfaces
        # distinguishable in the file.
        n = np.array([float.fromhex(h) for h in row["plane_abcd_hex"][:3]])
        facets.append(dict(points=points[idx], normal=n,
                           pitch=float(row["pitch_deg"]), idx=idx,
                           kind=row["kind"], blob=row["blob"],
                           quality=row["quality_rms_over_spacing"],
                           facet=row["facet"]))
    return doc, points, facets, cfg


def scalar(doc, key):
    """Read one of the exactly-saved scalars back as the identical double."""
    return float.fromhex(doc["scalars"][key])
