import numpy as np
from scipy.spatial.transform import Rotation
from roofkit.measure import (tilt_degrees, opposing_pairs, z_tilt_residual,
                             vertical_from_pair)


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
