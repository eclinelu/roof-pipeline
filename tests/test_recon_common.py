import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import numpy as np
from synthetic import gable_roof
from recon_common import discover_facets

CFG = {"fit_sample": 200000, "band_mult": 3.0, "min_points_frac": 0.03,
       "max_planes": 12, "trim_mult": 3.0}


def test_discover_facets_finds_both_gable_sides():
    pts = gable_roof(pitch_deg=30.0, width=10.0, depth=6.0,
                     n_per_side=8000, noise=0.01)
    facets, band, s = discover_facets(pts, CFG)
    assert len(facets) == 2
    for f in facets:
        assert abs(f["pitch"] - 30.0) < 0.5
    assert band > 0 and s > 0


def test_discover_facets_is_reproducible():
    pts = gable_roof(pitch_deg=30.0, width=10.0, depth=6.0,
                     n_per_side=8000, noise=0.01)
    a, _, _ = discover_facets(pts, CFG)
    b, _, _ = discover_facets(pts, CFG)
    assert len(a) == len(b)
    for fa, fb in zip(a, b):
        assert len(fa["points"]) == len(fb["points"])
