import numpy as np
from roofkit.stats import median_nn_spacing


def test_regular_grid_spacing_is_recovered():
    # 100 x 100 grid with 0.1 spacing: every nearest neighbor is 0.1 away.
    xs, ys = np.meshgrid(np.arange(100) * 0.1, np.arange(100) * 0.1)
    pts = np.column_stack([xs.ravel(), ys.ravel(), np.zeros(xs.size)])
    assert abs(median_nn_spacing(pts) - 0.1) < 1e-6


def test_sampling_path_matches_full_path():
    rng = np.random.default_rng(0)
    pts = rng.uniform(0, 10, (30000, 3))
    full = median_nn_spacing(pts, sample_size=30000)
    sampled = median_nn_spacing(pts, sample_size=5000)
    assert abs(full - sampled) / full < 0.05
