import numpy as np
from synthetic import gable_roof
from roofkit.segment import find_roof_planes


def test_ridge_points_are_not_stolen_by_the_first_plane():
    # Greedy peeling lets the first-found plane absorb the other side's
    # points near the ridge (the two planes are within the RANSAC band of
    # each other there). After reassignment the two sides of a symmetric
    # gable must come out balanced, with exact pitches.
    roof = gable_roof(pitch_deg=30.0, n_per_side=8000, noise=0.005)
    s = 0.04  # ~median nn spacing of this cloud; band = 3s as in the pipeline
    facets = find_roof_planes(roof, distance_threshold=3 * s, min_points=1000)
    assert len(facets) == 2
    n0, n1 = len(facets[0]["points"]), len(facets[1]["points"])
    assert abs(n0 - n1) / max(n0, n1) < 0.03   # balanced: no theft
    for f in facets:
        assert abs(f["pitch"] - 30.0) < 0.1    # refit normals are unbiased
