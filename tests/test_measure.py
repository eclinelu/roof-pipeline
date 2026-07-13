import numpy as np
from scipy.spatial.transform import Rotation
from roofkit.measure import (tilt_degrees, opposing_pairs, z_tilt_residual,
                             vertical_from_pair, project_to_plane,
                             alpha_shape_area, facet_area, azimuth_degrees)


def gable_facets(pitch_deg=30.0, tilt_about_ridge_deg=0.0):
    """Two facet dicts for a gable with ridge along Y, optionally tilted
    about the ridge (which adds the tilt to one pitch, subtracts from the
    other -- exactly the asymmetry the gate is designed to catch)."""
    p = np.radians(pitch_deg)
    normals = [np.array([np.sin(p), 0.0, np.cos(p)]),
               np.array([-np.sin(p), 0.0, np.cos(p)])]
    rot = Rotation.from_euler("y", tilt_about_ridge_deg, degrees=True)
    facets = []
    for n in normals:
        n = rot.apply(n)
        facets.append({"points": np.zeros((1, 3)), "normal": n,
                       "pitch": tilt_degrees(n)})
    return facets


def test_opposing_pairs_finds_the_gable_pair():
    facets = gable_facets(30.0)
    assert opposing_pairs(facets) == [(0, 1)]


def test_non_opposing_facets_do_not_pair():
    facets = gable_facets(30.0)
    p = np.radians(30.0)
    facets.append({"points": np.zeros((1, 3)),
                   "normal": np.array([0.0, np.sin(p), np.cos(p)]),
                   "pitch": 30.0})  # faces +Y: perpendicular, not opposite
    assert opposing_pairs(facets) == [(0, 1)]


def test_residual_zero_when_level():
    residual, pairs = z_tilt_residual(gable_facets(30.0))
    assert residual < 0.01 and pairs == [(0, 1)]


def test_residual_detects_a_known_2_degree_tilt():
    residual, _ = z_tilt_residual(gable_facets(30.0, tilt_about_ridge_deg=2.0))
    assert abs(residual - 2.0) < 0.05


def test_residual_is_none_without_an_instrument():
    residual, pairs = z_tilt_residual(gable_facets(30.0)[:1])
    assert residual is None and pairs == []


def test_vertical_from_pair_recovers_true_up():
    facets = gable_facets(30.0, tilt_about_ridge_deg=2.0)
    up = vertical_from_pair(facets[0], facets[1])
    true_up = Rotation.from_euler("y", 2.0, degrees=True).apply([0.0, 0.0, 1.0])
    assert np.degrees(np.arccos(np.clip(up @ true_up, -1, 1))) < 0.05


def test_azimuth_east_south_and_sign_flip():
    p = np.radians(30.0)
    east = np.array([np.sin(p), 0.0, np.cos(p)])       # faces +X = east
    south = np.array([0.0, -np.sin(p), np.cos(p)])     # faces -Y = south
    assert abs(azimuth_degrees(east) - 90.0) < 1e-6
    assert abs(azimuth_degrees(south) - 180.0) < 1e-6
    # RANSAC sign ambiguity: a downward copy of the same normal must give
    # the same compass bearing.
    assert abs(azimuth_degrees(-east) - 90.0) < 1e-6


def unit_square_grid(spacing=0.02):
    xs, ys = np.meshgrid(np.arange(0, 1 + spacing / 2, spacing),
                         np.arange(0, 1 + spacing / 2, spacing))
    return np.column_stack([xs.ravel(), ys.ravel()])


def test_unit_square_area():
    pts = unit_square_grid()
    assert abs(alpha_shape_area(pts, alpha=0.06) - 1.0) < 0.02


def test_hole_wider_than_alpha_stays_open():
    pts = unit_square_grid()
    hole = (np.abs(pts[:, 0] - 0.5) < 0.15) & (np.abs(pts[:, 1] - 0.5) < 0.15)
    area = alpha_shape_area(pts[~hole], alpha=0.06)
    assert abs(area - (1.0 - 0.09)) < 0.02  # the 0.3 x 0.3 hole is excluded


def test_facet_area_of_a_tilted_plane():
    # A 2 x 3 rectangle tilted 40 degrees: projected area must be 6, the
    # SLOPE area, not the footprint. This is why we project into the
    # facet's own plane instead of measuring the footprint.
    grid = unit_square_grid()
    rect = np.column_stack([grid[:, 0] * 2.0, grid[:, 1] * 3.0,
                            np.zeros(len(grid))])
    rot = Rotation.from_euler("x", 40.0, degrees=True)
    tilted = rot.apply(rect)
    normal = rot.apply([0.0, 0.0, 1.0])
    assert abs(facet_area(tilted, normal, alpha=0.15) - 6.0) < 0.1
