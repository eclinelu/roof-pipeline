import numpy as np
from synthetic import gable_roof, gable_side_area, foliage_blob


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
