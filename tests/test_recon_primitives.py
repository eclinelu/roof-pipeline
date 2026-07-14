# Tests for the recon primitives against a synthetic gable with KNOWN
# dimensions and KNOWN erosion depth. The directional assertions are the
# strong ones: erosion must read SHORT, never long, because the whole
# bracket design rests on filtering only ever removing boundary points.
import numpy as np
from synthetic import gable_roof, erode_eaves
from roofkit.measure import line_extent
from roofkit.stats import median_nn_spacing

PITCH, WIDTH, DEPTH = 30.0, 10.0, 6.0
N_SIDE = 8000


def right_side(points):
    """The x > 0 facet of the synthetic gable."""
    return points[points[:, 0] > 0]


def test_line_extent_recovers_ridge_length():
    pts = gable_roof(PITCH, WIDTH, DEPTH, N_SIDE)
    s = median_nn_spacing(pts)
    # the ridge of the synthetic gable is the y axis: x = 0, z = max
    near_ridge = pts[np.abs(pts[:, 0]) <= 10.0 * s]
    p0 = np.array([0.0, 0.0, pts[:, 2].max()])
    d = np.array([0.0, 1.0, 0.0])
    ext = line_extent(near_ridge, p0, d, s)
    # true length is DEPTH; the density edge sits within a bin of truth
    assert abs(ext["length"] - DEPTH) <= 2.0 * 4.0 * s
    # the supporting end bins hold real support, not one or two
    # stragglers (they carry a fraction of the ~20/bin central density;
    # the partial np.arange remainder bin at the far end holds ~half)
    assert ext["n_lo"] > 5 and ext["n_hi"] > 5


def test_line_extent_shortens_under_erosion_never_lengthens():
    pts = gable_roof(PITCH, WIDTH, DEPTH, N_SIDE)
    s = median_nn_spacing(pts)
    # erode the ridge ENDS by cropping y, a known 0.5 cu per end
    eroded = pts[(pts[:, 1] >= 0.5) & (pts[:, 1] <= DEPTH - 0.5)]
    p0 = np.array([0.0, 0.0, pts[:, 2].max()])
    d = np.array([0.0, 1.0, 0.0])
    s_band = 10.0 * s
    full = line_extent(pts[np.abs(pts[:, 0]) <= s_band], p0, d, s)
    short = line_extent(eroded[np.abs(eroded[:, 0]) <= s_band], p0, d, s)
    assert short["length"] < full["length"]
    # the shortening is at least most of the imposed 1.0 cu total
    assert full["length"] - short["length"] >= 0.5


def test_line_extent_ignores_stragglers():
    pts = gable_roof(PITCH, WIDTH, DEPTH, N_SIDE)
    s = median_nn_spacing(pts)
    p0 = np.array([0.0, 0.0, pts[:, 2].max()])
    d = np.array([0.0, 1.0, 0.0])
    strip = pts[np.abs(pts[:, 0]) <= 10.0 * s]
    # five stray points 3 cu past the real end must not stretch the extent
    strays = np.tile(p0 + (DEPTH + 3.0) * d, (5, 1))
    ext = line_extent(np.vstack([strip, strays]), p0, d, s)
    assert ext["t_hi"] <= DEPTH + 4.0 * 4.0 * s


from roofkit.measure import eave_line

# exact normal of the x > 0 facet: z = (WIDTH/2 - x) * tan(PITCH), so the
# plane is z + x*tan(p) = const and the unit normal is (sin p, 0, cos p)
NORMAL_R = np.array([np.sin(np.radians(PITCH)), 0.0,
                     np.cos(np.radians(PITCH))])


def test_eave_direction_is_the_planes_level_direction():
    pts = right_side(gable_roof(PITCH, WIDTH, DEPTH, N_SIDE))
    e = eave_line(pts, NORMAL_R, median_nn_spacing(pts))
    # level: no z component; parallel to the ridge (the y axis)
    assert abs(e["d"][2]) < 1e-12
    assert abs(abs(e["d"][1]) - 1.0) < 1e-12
    # downslope vector points down and toward +x on this side
    assert e["w"][2] < 0 and e["w"][0] > 0


def test_eave_position_is_a_lower_bound_and_near_truth_when_clean():
    pts = right_side(gable_roof(PITCH, WIDTH, DEPTH, N_SIDE))
    s = median_nn_spacing(pts)
    e = eave_line(pts, NORMAL_R, s)
    c = pts.mean(axis=0)
    true_eave = np.array([WIDTH / 2.0, DEPTH / 2.0, 0.0])
    t_truth = float((true_eave - c) @ e["w"])
    # noise-free points cannot lie past the physical eave, so the
    # estimate NEVER exceeds truth (the lower-bound property)...
    assert e["t_edge"] <= t_truth + 1e-9
    # ...and on clean data it sits within about one bin of truth
    assert t_truth - e["t_edge"] <= 1.5 * 4.0 * s


def test_bracket_contains_known_erosion():
    full = right_side(gable_roof(PITCH, WIDTH, DEPTH, N_SIDE))
    tight = erode_eaves(full, PITCH, WIDTH, depth_cu=0.5)
    s = median_nn_spacing(tight)
    origin = tight.mean(axis=0)
    lo = eave_line(tight, NORMAL_R, s, origin=origin)
    hi = eave_line(full, NORMAL_R, s, origin=origin)
    delta = hi["t_edge"] - lo["t_edge"]
    # the bracket brackets: tight short of loose, delta near the known
    # 0.5 cu erosion depth, within about one bin
    assert delta > 0
    assert abs(delta - 0.5) <= 1.5 * 4.0 * s


def test_flat_plane_has_no_eave():
    rng = np.random.default_rng(0)
    flat = np.column_stack([rng.uniform(0, 5, 2000),
                            rng.uniform(0, 5, 2000),
                            np.zeros(2000)])
    assert eave_line(flat, np.array([0.0, 0.0, 1.0]), 0.1) is None
