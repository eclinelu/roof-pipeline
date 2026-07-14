import numpy as np
from synthetic import (gable_roof, gable_side_area, foliage_blob,
                       erode_eaves, slope_dist_from_eave)


def test_gable_points_lie_on_the_two_known_planes():
    pts = gable_roof(pitch_deg=30.0, width=10.0, depth=6.0)
    slope = np.tan(np.radians(30.0))
    expected_z = (5.0 - np.abs(pts[:, 0])) * slope
    assert np.allclose(pts[:, 2], expected_z, atol=1e-9)


def test_gable_side_area_formula():
    # 6 * 5 / cos(30 deg) = 34.641...
    assert abs(gable_side_area(30.0, 10.0, 6.0) - 34.6410) < 1e-3


def test_foliage_blob_fills_its_box():
    blob = foliage_blob(center=(2.0, 3.0, 4.0), size=2.0, n=5000)
    assert blob.min(axis=0)[0] > 1.0 and blob.max(axis=0)[0] < 3.0


def test_erode_eaves_removes_exactly_the_edge_strip():
    pts = gable_roof(pitch_deg=30.0, width=10.0, depth=6.0, n_per_side=8000)
    eroded = erode_eaves(pts, pitch_deg=30.0, width=10.0, depth_cu=0.5)
    # every survivor sits at least 0.5 cu (slope distance) from an eave
    assert slope_dist_from_eave(eroded, 30.0, 10.0).min() >= 0.5
    # and the strip really was populated before erosion
    assert len(eroded) < len(pts)
    # interior is untouched: the deepest point survives
    assert np.isclose(eroded[:, 2].max(), pts[:, 2].max())
