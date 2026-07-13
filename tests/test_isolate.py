import numpy as np
from roofkit.isolate import height_cutoff, excess_green, color_filter
from synthetic import solid_color


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
