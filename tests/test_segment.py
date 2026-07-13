import numpy as np
from synthetic import gable_roof
from roofkit.segment import find_roof_planes, assign_to_planes, fit_plane_svd


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


def test_fit_plane_svd_recovers_known_normal():
    rng = np.random.default_rng(0)
    pts = np.column_stack([rng.uniform(0, 5, 2000), rng.uniform(0, 5, 2000),
                           rng.normal(0, 0.01, 2000)])  # noisy z=0 plane
    n = fit_plane_svd(pts)
    assert abs(abs(n[2]) - 1.0) < 1e-3         # normal is (0, 0, +-1)


def test_assign_to_planes_picks_nearest_and_caps_distance():
    # Two horizontal planes, z=0 and z=1, as minimal facet dicts.
    f0 = {"points": np.array([[0, 0, 0.], [1, 0, 0.], [0, 1, 0.]]),
          "normal": np.array([0, 0, 1.])}
    f1 = {"points": np.array([[0, 0, 1.], [1, 0, 1.], [0, 1, 1.]]),
          "normal": np.array([0, 0, 1.])}
    pts = np.array([[0.5, 0.5, 0.05],   # near plane 0
                    [0.5, 0.5, 0.90],   # near plane 1
                    [0.5, 0.5, 5.00]])  # near nothing
    owner, dist = assign_to_planes(pts, [f0, f1], max_dist=0.2)
    assert owner.tolist() == [0, 1, -1]
    assert abs(dist[0] - 0.05) < 1e-9 and abs(dist[1] - 0.10) < 1e-9
