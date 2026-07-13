import numpy as np
from roofkit.isolate import (height_cutoff, excess_green, color_filter,
                             planarity_scores, planarity_filter)
from synthetic import solid_color, gable_roof, foliage_blob


def test_height_cutoff_drops_low_points():
    pts = np.array([[0, 0, 0.0], [0, 0, 5.0], [0, 0, 10.0]])
    kept, mask = height_cutoff(pts, z_min=5.0)
    assert len(kept) == 2 and mask.tolist() == [False, True, True]


def test_excess_green_separates_leaf_from_shingle():
    leaf = solid_color(1, (0.2, 0.7, 0.2))     # ExG = 2*0.7 - 0.2 - 0.2 = 1.0
    shingle = solid_color(1, (0.5, 0.5, 0.5))  # ExG = 0.0
    assert excess_green(leaf)[0] > 0.5
    assert abs(excess_green(shingle)[0]) < 1e-9


def test_color_filter_removes_green_keeps_gray():
    pts = np.zeros((4, 3))
    colors = np.vstack([solid_color(2, (0.2, 0.7, 0.2)),
                        solid_color(2, (0.5, 0.5, 0.5))])
    kept, mask = color_filter(pts, colors, exg_max=0.1)
    assert len(kept) == 2 and mask.tolist() == [False, False, True, True]


def test_plane_scores_low_blob_scores_high():
    plane = gable_roof(n_per_side=4000, noise=0.005)
    blob = foliage_blob(center=(0.0, 3.0, 8.0), size=3.0, n=3000)
    scores = planarity_scores(np.vstack([plane, blob]), radius=0.5)
    plane_scores = scores[: len(plane)]
    blob_scores = scores[len(plane):]
    assert np.median(plane_scores) < 0.02
    assert np.median(blob_scores) > 0.10


def test_planarity_filter_separates_roof_from_blob():
    plane = gable_roof(n_per_side=4000, noise=0.005)
    blob = foliage_blob(center=(0.0, 3.0, 8.0), size=3.0, n=3000)
    both = np.vstack([plane, blob])
    kept, mask = planarity_filter(both, radius=0.5, score_max=0.05)
    kept_from_plane = mask[: len(plane)].mean()
    kept_from_blob = mask[len(plane):].mean()
    assert kept_from_plane > 0.90   # roof survives
    assert kept_from_blob < 0.10    # confetti does not
