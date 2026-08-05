# The streaming crop-on-read path must be a pure memory optimisation: same
# points, same colours, same ORDER as reading the whole cloud and cropping it.
#
# These tests are the anti-null for that claim (standing rule R4: every
# diagnostic carries an assertion built from something known independently of
# its own result). The independent thing here is the ORIGINAL one-shot path,
# which is what the canonical artifacts were built with. If the two ever
# disagree, the streaming reader is wrong, not the other way round.
#
# Two properties are tested separately because they fail for different reasons:
#
#   1. EQUIVALENCE to load_xyz_rgb + crop_box. Catches a drifted boundary
#      comparison, a lost chunk, or a reordering.
#   2. INVARIANCE to chunk_size. Catches the specific failure the global colour
#      divisor was written to prevent -- a per-chunk decision making the answer
#      depend on how the file happened to be grouped.
import numpy as np
import pytest

laspy = pytest.importorskip("laspy")

from roofkit.crop import crop_box
from roofkit.io import load_xyz_rgb, load_xyz_rgb_cropped


def _write_las(path, points, colors16):
    """Write a small 16-bit-colour LAZ/LAS so the tests own their input."""
    header = laspy.LasHeader(point_format=3, version="1.2")
    header.offsets = np.array([0.0, 0.0, 0.0])
    header.scales = np.array([0.001, 0.001, 0.001])
    las = laspy.LasData(header)
    las.x, las.y, las.z = points[:, 0], points[:, 1], points[:, 2]
    las.red, las.green, las.blue = (colors16[:, 0], colors16[:, 1], colors16[:, 2])
    las.write(str(path))


@pytest.fixture
def cloud(tmp_path):
    rng = np.random.default_rng(20260805)
    n = 5000
    pts = rng.uniform(-10.0, 10.0, size=(n, 3))
    # 16-bit colours, so the divisor rule must resolve to 65535. One point is
    # forced bright to pin that down; the rest are deliberately dim enough that
    # a chunk containing none of them would resolve to 255 on its own. That is
    # what makes the chunk-size invariance test able to fail.
    col = rng.integers(0, 200, size=(n, 3), dtype=np.uint16)
    col[n // 2] = 60000
    path = tmp_path / "cloud.las"
    _write_las(path, pts, col)
    return path


BOX_MIN = (-4.0, -4.0, -4.0)
BOX_MAX = (5.0, 5.0, 5.0)


def _reference(path):
    points, colors = load_xyz_rgb(path)
    points, mask = crop_box(points, BOX_MIN, BOX_MAX)
    return points, colors[mask]


def test_streaming_crop_equals_read_then_crop(cloud):
    ref_pts, ref_col = _reference(cloud)
    got_pts, got_col = load_xyz_rgb_cropped(cloud, BOX_MIN, BOX_MAX, chunk_size=997)

    assert got_pts.shape == ref_pts.shape
    assert got_col.shape == ref_col.shape
    # Bit for bit, not allclose. These feed a colour cutoff and a plane fit;
    # "close" is how a difference gets to survive into an artifact.
    assert np.array_equal(got_pts, ref_pts)
    assert np.array_equal(got_col, ref_col)


def test_result_does_not_depend_on_chunk_size(cloud):
    a_pts, a_col = load_xyz_rgb_cropped(cloud, BOX_MIN, BOX_MAX, chunk_size=64)
    b_pts, b_col = load_xyz_rgb_cropped(cloud, BOX_MIN, BOX_MAX, chunk_size=10_000_000)
    assert np.array_equal(a_pts, b_pts)
    assert np.array_equal(a_col, b_col)


def test_colour_divisor_is_global_not_per_chunk(cloud):
    """The power check for the test above.

    With chunk_size=64 the single bright point sits alone in one chunk of ~78,
    so almost every chunk sees a maximum below 255. An implementation choosing
    the divisor per chunk would scale those chunks by 255 instead of 65535 and
    return colours ~257x too large. This asserts the dim points came back on
    the 16-bit scale, which is the thing that would break.
    """
    pts, col = load_xyz_rgb_cropped(cloud, BOX_MIN, BOX_MAX, chunk_size=64)
    assert col.size, "the box kept nothing; this test would be void"
    # Raw values are < 200 except the one bright point, so on a 65535 divisor
    # everything must be tiny. On a 255 divisor the dim points alone reach ~0.78.
    dim = col[col < 0.5]
    assert dim.max() < 200.0 / 65535.0 * 1.0001, (
        "colours came back on a per-chunk divisor, not the global one"
    )


def test_empty_box_returns_empty_not_error(cloud):
    pts, col = load_xyz_rgb_cropped(cloud, (500.0, 500.0, 500.0), (501.0, 501.0, 501.0))
    assert pts.shape == (0, 3)
    assert col.shape == (0, 3)
