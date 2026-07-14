import numpy as np
from scipy.spatial.transform import Rotation
from synthetic import gable_roof
from roofkit.measure import (tilt_degrees, opposing_pairs, z_tilt_residual,
                             vertical_from_pair, project_to_plane,
                             alpha_shape_area, facet_area, azimuth_degrees,
                             ridge_line, tilt_from_ridges)


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


def test_ridge_line_finds_a_level_gable_ridge():
    roof = gable_roof(pitch_deg=30.0, n_per_side=6000, noise=0.005)
    a, b = roof[roof[:, 0] < 0], roof[roof[:, 0] >= 0]
    r = ridge_line(a, b, contact_dist=0.15)
    assert r is not None
    assert abs(r["inclination_deg"]) < 0.15          # a real ridge is level
    az = r["azimuth_deg"]
    assert az < 5.0 or az > 175.0                    # ridge runs along Y (north)
    assert r["frac_a"] > 0.9 and r["frac_b"] > 0.9   # contact at the TOP


def test_ridge_line_measures_a_known_inclination():
    from scipy.spatial.transform import Rotation
    roof = gable_roof(pitch_deg=30.0, n_per_side=6000, noise=0.005)
    tilted = Rotation.from_euler("x", 2.0, degrees=True).apply(roof)
    a, b = tilted[tilted[:, 0] < 0], tilted[tilted[:, 0] >= 0]
    r = ridge_line(a, b, contact_dist=0.15)
    assert abs(abs(r["inclination_deg"]) - 2.0) < 0.15


def test_valley_contact_reads_as_bottom_not_ridge():
    roof = gable_roof(pitch_deg=30.0, n_per_side=6000, noise=0.005)
    valley = roof.copy()
    valley[:, 2] = roof[:, 2].max() - roof[:, 2]     # flip: ridge becomes valley
    a, b = valley[valley[:, 0] < 0], valley[valley[:, 0] >= 0]
    r = ridge_line(a, b, contact_dist=0.15)
    assert r is not None
    assert r["frac_a"] < 0.2 and r["frac_b"] < 0.2   # contact at the BOTTOM


def test_tilt_from_ridges_recovers_the_vector():
    # ridges at az 0 and 90 with slopes 1.0 and 0.5: tilt vector components
    # u=1.0, w=0.5 -> magnitude hypot = 1.118, uphill az = atan2(0.5, 1.0)
    t, az = tilt_from_ridges([(0.0, 1.0), (90.0, 0.5)])
    assert abs(t - 1.1180) < 1e-3
    assert abs(az - 26.565) < 1e-2


def test_leveling_by_the_measured_tilt_nulls_the_ridges():
    # The full instrument chain, and the SIGN convention pin: tilt two
    # orthogonal gables by a known rotation, measure both ridges, solve
    # the tilt vector, level by it, re-measure. If any sign anywhere in
    # ridge_line / tilt_from_ridges / up_from_tilt is wrong, leveling
    # DOUBLES the readings instead of nulling them and this fails loudly.
    from roofkit.measure import up_from_tilt
    from roofkit.segment import level_cloud
    r1 = gable_roof(pitch_deg=30.0, n_per_side=6000, noise=0.005)
    r2 = r1[:, [1, 0, 2]] + np.array([20.0, 0.0, 0.0])  # ridge along X
    tilt = Rotation.from_euler("xy", [0.9, -1.1], degrees=True)
    t1, t2 = tilt.apply(r1), tilt.apply(r2)
    readings = []
    for roof, axis in ((t1, 0), (t2, 1)):
        split = roof[:, axis] < np.median(roof[:, axis])
        r = ridge_line(roof[split], roof[~split], contact_dist=0.15)
        readings.append((r["azimuth_deg"], r["inclination_deg"]))
    t_deg, az_deg = tilt_from_ridges(readings)
    # Non-vacuous check: euler xy [0.9, -1.1] puts true up in cloud coords
    # at (-0.019198, -0.015708, ~1), i.e. tilt 1.4215 deg, uphill az 50.7.
    assert abs(t_deg - 1.4215) < 0.05
    assert abs(az_deg - 50.7) < 2.0
    up = up_from_tilt(t_deg, az_deg)
    for roof, axis in ((t1, 0), (t2, 1)):
        lev = level_cloud(roof, up)
        split = lev[:, axis] < np.median(lev[:, axis])
        r = ridge_line(lev[split], lev[~split], contact_dist=0.15)
        assert abs(r["inclination_deg"]) < 0.1


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
