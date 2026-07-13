# End-to-end on synthetic ground truth: gray gable + green blob + brown
# blob in, two facets at the known pitch and known area out. The brown
# blob exists to force the planarity filter to earn its keep: it survives
# the color filter on purpose.
import numpy as np
from synthetic import gable_roof, gable_side_area, foliage_blob, solid_color
from roofkit.stats import median_nn_spacing
from roofkit.isolate import color_filter, planarity_filter
from roofkit.segment import find_roof_planes
from roofkit.measure import z_tilt_residual, facet_area


def test_pipeline_recovers_known_pitch_and_area():
    roof = gable_roof(pitch_deg=30.0, n_per_side=8000, noise=0.005)
    green = foliage_blob(center=(3.0, 3.0, 3.0), size=3.0, n=3000, seed=1)
    brown = foliage_blob(center=(-3.0, 3.0, 3.0), size=3.0, n=3000, seed=2)
    points = np.vstack([roof, green, brown])
    colors = np.vstack([solid_color(len(roof), (0.5, 0.5, 0.5)),
                        solid_color(len(green), (0.2, 0.7, 0.2)),
                        solid_color(len(brown), (0.4, 0.3, 0.2))])

    s = median_nn_spacing(points)
    pts, _ = color_filter(points, colors, exg_max=0.1)
    pts, _ = planarity_filter(pts, radius=5.0 * s, score_max=0.05)

    facets = find_roof_planes(pts, distance_threshold=3.0 * s,
                              min_points=int(0.05 * len(pts)))
    assert len(facets) == 2

    for f in facets:
        assert abs(f["pitch"] - 30.0) < 1.0

    residual, pairs = z_tilt_residual(facets)
    assert pairs and residual < 0.5

    true_area = gable_side_area(30.0)
    for f in facets:
        got = facet_area(f["points"], f["normal"], alpha=4.0 * s)
        assert abs(got - true_area) / true_area < 0.05
