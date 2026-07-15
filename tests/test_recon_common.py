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
    # Reproducibility that matters for pre-registration is that the
    # MEASURED geometry (facet count, pitch, and the areas/spans derived
    # from plane fits over thousands of points) is stable, not that RANSAC
    # membership is bit-identical. Open3D's segment_plane RNG does not
    # fully reset on reseed WITHIN a process (its first call after process
    # start differs from later calls by a point or two at the band edge),
    # so a handful of ridge-band points flicker between the two adjacent
    # planes. Pitch is bit-identical; point counts match within that
    # flicker. Across separate invocations (the real usage, one run per
    # process) each first-and-only call is deterministic.
    pts = gable_roof(pitch_deg=30.0, width=10.0, depth=6.0,
                     n_per_side=8000, noise=0.01)
    a, _, _ = discover_facets(pts, CFG)
    b, _, _ = discover_facets(pts, CFG)
    # Pin the count to the gable's KNOWN two sides so a VANISHED facet
    # (the real historical nondeterminism failure, a whole facet not
    # rediscovered between runs, not a 1-point flicker) fails loudly
    # instead of slipping through a per-facet tolerance that only
    # compares facets present in both runs.
    assert len(a) == 2 and len(b) == 2
    assert (sorted(round(f["pitch"], 3) for f in a) ==
            sorted(round(f["pitch"], 3) for f in b))  # geometry reproducible
    ca = sorted(len(f["points"]) for f in a)
    cb = sorted(len(f["points"]) for f in b)
    for na, nb in zip(ca, cb):
        assert abs(na - nb) <= 5  # only band-edge points flicker in-process
