# Tests for the invariants added 2026-07-26: single facet ownership, enclosed
# hole filling, and the coverage split.
#
# These exist because each one is a claim the pipeline now makes on every run,
# and a claim nothing checks is a claim nobody should believe. The ownership
# assertion in particular replaced a defect that survived a full diagnostic
# pass, so the test verifies it FAILS on the bad input as well as passing on
# the good one. A guard only tested against passing input has not been tested.
import numpy as np
import pytest

from roofkit import coverage as cov
from roofkit.measure import (LOW_SLOPE_DEG, is_low_slope, rise_over_12)
from roofkit.segment import assert_single_ownership


def _facet(idx):
    """A facet stub carrying only what the ownership check reads."""
    return dict(idx=np.asarray(idx, np.int64),
                points=np.zeros((len(idx), 3)), normal=np.array([0., 0., 1.]),
                pitch=0.0)


# --------------------------------------------------------------------------
# Single ownership
# --------------------------------------------------------------------------
def test_single_ownership_passes_when_facets_are_disjoint():
    facets = [_facet([0, 1, 2]), _facet([3, 4]), _facet([5])]
    assert assert_single_ownership(facets) == 0


def test_single_ownership_raises_on_a_shared_point():
    # THE REGRESSION: two facets owning the same point is exactly the defect
    # found on big_house (facets 20 and 23 shared 9,739 points).
    facets = [_facet([0, 1, 2]), _facet([2, 3])]
    with pytest.raises(AssertionError) as e:
        assert_single_ownership(facets)
    msg = str(e.value)
    assert "facets 0 and 1" in msg          # it must name WHERE, not just THAT
    assert "1" in msg


def test_single_ownership_raises_when_a_facet_has_no_indices():
    # R1 requires every facet to carry indices. A facet without them cannot be
    # checked, and silently skipping it would make the guard meaningless.
    facets = [_facet([0, 1]), dict(points=np.zeros((2, 3)))]
    with pytest.raises(AssertionError, match="no index array"):
        assert_single_ownership(facets)


# --------------------------------------------------------------------------
# Hole filling
# --------------------------------------------------------------------------
def _ring_cloud(cell=1.0, n=9, per_cell=5, hole=(4, 4)):
    """A solid square of plan cells with ONE interior cell left empty: the
    smallest thing that behaves like the real mask, which was riddled with
    single-cell holes."""
    pts = []
    for i in range(n):
        for j in range(n):
            if (i, j) == hole:
                continue
            for k in range(per_cell):
                pts.append([(i + 0.5) * cell, (j + 0.5) * cell, 0.01 * k])
    return np.asarray(pts, float)


def test_enclosed_hole_is_filled_and_counted():
    pts = _ring_cloud()
    masks, g, _, _ = cov.coverage_masks(pts, [], band=1e9, cell=1.0)
    # The hole holds no points, so it can never be "testable"...
    assert masks["testable"].sum() < masks["footprint"].sum()
    # ...but it is enclosed, so it IS footprint.
    assert int(masks["filled"].sum()) >= 1
    rep = cov.filled_hole_report(masks, cell=1.0)
    assert rep["n_holes"] >= 1
    assert rep["total_cells"] >= 1


def test_fill_holes_false_reproduces_the_old_behaviour():
    # The escape hatch that lets a superseded number be recomputed rather than
    # merely quoted. Without filling, the hole stays a hole.
    pts = _ring_cloud()
    off, _, _, _ = cov.coverage_masks(pts, [], band=1e9, cell=1.0,
                                      fill_holes=False)
    assert int(off["filled"].sum()) == 0
    assert np.array_equal(off["footprint"], off["testable"])


def test_a_hole_touching_the_edge_is_not_filled():
    # binary_fill_holes only fills regions with NO path to the outside. A gap
    # open to the edge is not enclosed and must be left alone, which is what
    # stops the fill from quietly absorbing a real notch in the footprint.
    pts = _ring_cloud(hole=(0, 4))          # on the boundary, not interior
    masks, _, _, _ = cov.coverage_masks(pts, [], band=1e9, cell=1.0)
    assert int(masks["filled"].sum()) == 0


def test_footprint_three_ways_is_ordered_and_consistent():
    pts = _ring_cloud()
    masks, _, _, _ = cov.coverage_masks(pts, [], band=1e9, cell=1.0)
    fp = cov.footprint_three_ways(masks, cell=1.0)
    # raw <= filled, and eroding can only shrink it.
    assert fp["raw_cells_at_2_points"] <= fp["filled_cells"]
    assert fp["eroded_cells"] <= fp["filled_cells"]
    assert (fp["holes_filled_cells"] ==
            fp["filled_cells"] - fp["raw_cells_at_2_points"])
    assert (fp["erosion_cost_cells"] ==
            fp["filled_cells"] - fp["eroded_cells"])


# --------------------------------------------------------------------------
# The coverage split
# --------------------------------------------------------------------------
def test_split_coverage_separates_capture_from_segmentation():
    pts = _ring_cloud()
    masks, _, _, _ = cov.coverage_masks(pts, [], band=1e9, cell=1.0)
    s = cov.split_coverage(masks, cell=1.0)
    # With no facets, nothing is explained, so segmentation coverage is 0...
    assert s["facet_coverage"]["pct"] == 0.0
    # ...but the capture metric is independent of that and must not be 0 just
    # because no facet was fitted. Conflating the two is the defect this split
    # exists to remove.
    assert s["density_testable_fraction"]["pct"] > 0.0
    assert (s["density_testable_fraction"]["testable_cells"] <=
            s["density_testable_fraction"]["footprint_cells"])


# --------------------------------------------------------------------------
# Low-slope classification (a LABEL, never a filter)
# --------------------------------------------------------------------------
def test_low_slope_boundary_is_2_over_12():
    assert rise_over_12(LOW_SLOPE_DEG) == pytest.approx(2.0, abs=1e-9)
    assert LOW_SLOPE_DEG == pytest.approx(9.4623, abs=1e-3)


def test_is_low_slope_classifies_either_side():
    assert is_low_slope(8.16)               # big_house blob 6, ~1.72:12
    assert not is_low_slope(21.19)          # a main facet, ~4.6:12
    assert not is_low_slope(LOW_SLOPE_DEG + 1e-9)


def test_rise_over_12_matches_known_pitches():
    assert rise_over_12(np.degrees(np.arctan2(4.0, 12.0))) == pytest.approx(4.0)
    assert rise_over_12(np.degrees(np.arctan2(8.0, 12.0))) == pytest.approx(8.0)
