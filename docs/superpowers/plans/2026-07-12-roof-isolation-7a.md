# Roof Isolation Through Stage 7a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A dataset-agnostic pipeline that isolates a roof from vegetation and ground, segments its facets, gates the vertical reference, and reports per-facet pitch and polygon area (stage 7a of the approved design). Validated first on big_house.

**Architecture:** Per-point filters (height, color, planarity) strip ground and foliage, iterative RANSAC peels roof facets, a symmetry gate validates the Z axis before any pitch is reported, and a Delaunay alpha-shape sums each facet's area in its own plane. All analysis functions take and return plain NumPy arrays; every scale-dependent threshold is derived from the cloud's median nearest-neighbor spacing. Site-specific numbers live in a per-dataset `roofkit.json` next to the data, so the same code runs on any cloud.

**Tech Stack:** Python 3.12 (`.venv`), NumPy, SciPy (cKDTree, Delaunay, Rotation), Open3D (RANSAC, covariance estimation, visualization), pytest. Spec: `docs/superpowers/specs/2026-07-12-roof-isolation-design.md`.

## Global Constraints

- `roofkit/io.py` is the ONLY module that touches point cloud formats. Everything else consumes and returns plain NumPy arrays.
- The pipeline is dataset-agnostic. No dataset name appears in any module, script name, or constant. Site-specific numbers (crop box, height cutoff, tuned cutoffs) live in `<dataset>\roofkit.json` next to the data; scripts take the dataset directory as an argument.
- Scale-dependent thresholds (planarity radius, RANSAC band, alpha) are NEVER hardcoded lengths. They are multiples of `median_nn_spacing(points)`.
- EXPLANATION GATE (decision 2026-07-12): Tasks 2 through 7 produce analysis core. After each of these tasks, STOP and give Emmett a plain-language walkthrough covering the approach, every threshold, and each threshold's scale-dependence. NO QUIZZING: end with an invitation for questions, and proceed when he says to continue. Do not batch gates.
- Visual verification on the real cloud (Tasks 8 and 9) before any stage's output is trusted downstream.
- Stage 7b (edge fitting and dimensions) is OUT OF SCOPE for this plan. Do not start it.
- Test synthetic clouds live in `tests/`; drivers and per-dataset glue live in `scripts/`; reusable analysis lives in `roofkit/`. Do not mix (CLAUDE.md).
- Run commands with the venv active (`.venv\Scripts\Activate.ps1`); tests are `python -m pytest`.

---

### Task 1: Test infrastructure and synthetic clouds

**Files:**
- Create: `tests/synthetic.py`
- Test: `tests/test_synthetic.py`

**Interfaces:**
- Produces: `gable_roof(pitch_deg=30.0, width=10.0, depth=6.0, n_per_side=5000, seed=0, noise=0.0) -> (N,3) ndarray`, `gable_side_area(pitch_deg, width, depth) -> float`, `foliage_blob(center, size, n=3000, seed=1) -> (N,3) ndarray`, `solid_color(n, rgb) -> (N,3) ndarray`. Every later test consumes these.

- [ ] **Step 1: Install pytest into the venv**

Run: `python -m pip install pytest`
Expected: `Successfully installed pytest-...` (or already satisfied).

- [ ] **Step 2: Write the synthetic cloud generators**

`tests/synthetic.py`:

```python
# Synthetic point clouds with KNOWN geometry, used as ground truth in tests.
# A gable roof at a chosen pitch, a random blob standing in for foliage,
# and solid color arrays. If a pipeline stage cannot recover the known
# numbers from these, it has no business touching the real cloud.
import numpy as np


def gable_roof(pitch_deg=30.0, width=10.0, depth=6.0, n_per_side=5000,
               seed=0, noise=0.0):
    """Two rectangular planes meeting at a ridge along the Y axis.

    Footprint spans x in [-width/2, width/2], y in [0, depth]. Height is
    z = (width/2 - |x|) * tan(pitch), so the eaves sit at z=0 and the ridge
    at z = (width/2) * tan(pitch). True per-side area (slope-corrected):
    depth * (width/2) / cos(pitch).
    """
    rng = np.random.default_rng(seed)
    slope = np.tan(np.radians(pitch_deg))
    sides = []
    for sign in (-1.0, 1.0):
        x = sign * rng.uniform(0.0, width / 2.0, n_per_side)
        y = rng.uniform(0.0, depth, n_per_side)
        z = (width / 2.0 - np.abs(x)) * slope
        sides.append(np.column_stack([x, y, z]))
    points = np.vstack(sides)
    if noise > 0.0:
        points = points + rng.normal(0.0, noise, points.shape)
    return points


def gable_side_area(pitch_deg=30.0, width=10.0, depth=6.0):
    """The true slope-corrected area of ONE side of gable_roof."""
    return depth * (width / 2.0) / np.cos(np.radians(pitch_deg))


def foliage_blob(center, size, n=3000, seed=1):
    """Uniform random points in a cube: geometry with no planar structure,
    the synthetic stand-in for foliage."""
    rng = np.random.default_rng(seed)
    return rng.uniform(-0.5, 0.5, (n, 3)) * size + np.asarray(center, float)


def solid_color(n, rgb):
    """(n, 3) array of one repeated 0-1 RGB color."""
    return np.tile(np.asarray(rgb, float), (n, 1))
```

- [ ] **Step 3: Write the fixture sanity test**

`tests/test_synthetic.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/ -v`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add tests/synthetic.py tests/test_synthetic.py
git commit -m "test: add synthetic gable and foliage generators for pipeline tests"
```

---

### Task 2: Median nearest-neighbor spacing (the scale yardstick)

**Files:**
- Create: `roofkit/stats.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Produces: `median_nn_spacing(points, sample_size=20000, seed=0) -> float`. Tasks 4, 7, 8, 9 derive every scale-dependent threshold from this value.

- [ ] **Step 1: Write the failing test**

`tests/test_stats.py`:

```python
import numpy as np
from roofkit.stats import median_nn_spacing


def test_regular_grid_spacing_is_recovered():
    # 100 x 100 grid with 0.1 spacing: every nearest neighbor is 0.1 away.
    xs, ys = np.meshgrid(np.arange(100) * 0.1, np.arange(100) * 0.1)
    pts = np.column_stack([xs.ravel(), ys.ravel(), np.zeros(xs.size)])
    assert abs(median_nn_spacing(pts) - 0.1) < 1e-6


def test_sampling_path_matches_full_path():
    rng = np.random.default_rng(0)
    pts = rng.uniform(0, 10, (30000, 3))
    full = median_nn_spacing(pts, sample_size=30000)
    sampled = median_nn_spacing(pts, sample_size=5000)
    assert abs(full - sampled) / full < 0.05
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'roofkit.stats'`.

- [ ] **Step 3: Write the implementation**

`roofkit/stats.py`:

```python
# The scale yardstick. Scale-dependent thresholds (RANSAC band, planarity
# radius, alpha) are expressed as multiples of this number so they transfer
# between clouds of different scale and density (decision 2026-07-12).
import numpy as np
from scipy.spatial import cKDTree


def median_nn_spacing(points, sample_size=20000, seed=0):
    """Median distance from a point to its single nearest neighbor.

    Queries a random sample (not every point) against the full cloud, which
    is statistically identical for a median and far cheaper on millions of
    points. k=2 because a point's nearest neighbor at k=1 is itself.
    """
    points = np.asarray(points)
    if len(points) > sample_size:
        rng = np.random.default_rng(seed)
        sample = points[rng.choice(len(points), sample_size, replace=False)]
    else:
        sample = points
    tree = cKDTree(points)
    dists, _ = tree.query(sample, k=2)
    return float(np.median(dists[:, 1]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stats.py -v`
Expected: 2 PASSED.

- [ ] **Step 5: Commit, then STOP for the explanation gate**

```bash
git add roofkit/stats.py tests/test_stats.py
git commit -m "feat: median nearest-neighbor spacing as the scale yardstick"
```

Gate walkthrough must cover: why a median and not a mean (outlier robustness), why k=2, why sampling is valid for a median, and why this number is the basis for every scale-dependent threshold.

---

### Task 3: Height cutoff and color filter

**Files:**
- Create: `roofkit/isolate.py`
- Test: `tests/test_isolate.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `height_cutoff(points, z_min) -> (points, mask)`, `excess_green(colors) -> (N,) ndarray`, `color_filter(points, colors, exg_max=0.1) -> (points, mask)`. Masks let callers keep color arrays aligned, same pattern as `crop_box`.

- [ ] **Step 1: Write the failing tests**

`tests/test_isolate.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_isolate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'roofkit.isolate'`.

- [ ] **Step 3: Write the implementation**

`roofkit/isolate.py`:

```python
# Roof isolation filters: strip ground, walls, and vegetation BEFORE plane
# segmentation, so RANSAC only ever sees roof candidates (decisions
# 2026-07-12: vegetation is the adversary; no ground-plane RANSAC).
import numpy as np


def height_cutoff(points, z_min):
    """Keep points at or above z_min. With a georeferenced cloud and a tight
    crop, one cut below eave height removes sloped ground and the thin
    partial walls in a single stroke. z_min is site-specific and chosen
    visually by the caller; it does not belong in this module as a constant."""
    mask = points[:, 2] >= z_min
    return points[mask], mask


def excess_green(colors):
    """ExG = 2G - R - B per point, on 0-1 RGB. Foliage scores high, gray or
    brown shingle scores near zero. Unitless, therefore scale-independent.
    ASSUMPTION (logged 2026-07-12): the roof is not green. Fails on green,
    moss-covered, or copper-patina roofs."""
    return 2.0 * colors[:, 1] - colors[:, 0] - colors[:, 2]


def color_filter(points, colors, exg_max=0.1):
    """Keep points that are NOT green (ExG at or below exg_max)."""
    mask = excess_green(colors) <= exg_max
    return points[mask], mask
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_isolate.py -v`
Expected: 3 PASSED.

- [ ] **Step 5: Commit, then STOP for the explanation gate**

```bash
git add roofkit/isolate.py tests/test_isolate.py
git commit -m "feat: height cutoff and ExG color filter for roof isolation"
```

Gate walkthrough must cover: why ExG works and exactly when it fails; why the cutoff is scale-independent; why z_min stays out of roofkit.

---

### Task 4: Local planarity filter

**Files:**
- Modify: `roofkit/isolate.py` (append)
- Test: `tests/test_isolate.py` (append)

**Interfaces:**
- Consumes: `median_nn_spacing` (Task 2) is what callers use to derive `radius`.
- Produces: `planarity_scores(points, radius, max_nn=30) -> (N,) ndarray`, `planarity_filter(points, radius, score_max=0.05, max_nn=30) -> (points, mask)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_isolate.py`:

```python
from roofkit.isolate import planarity_scores, planarity_filter
from synthetic import gable_roof, foliage_blob


def test_plane_scores_low_blob_scores_high():
    plane = gable_roof(n_per_side=4000, noise=0.005)
    blob = foliage_blob(center=(0.0, 3.0, 8.0), size=3.0, n=3000)
    scores = planarity_scores(np.vstack([plane, blob]), radius=0.5)
    plane_scores = scores[: len(plane)]
    blob_scores = scores[len(plane):]
    assert np.median(plane_scores) < 0.02
    assert np.median(blob_scores) > 0.10


def test_planarity_filter_separates_roof_from_blob():
    plane = gable_roof(n_per_side=4000, noise=0.005)
    blob = foliage_blob(center=(0.0, 3.0, 8.0), size=3.0, n=3000)
    both = np.vstack([plane, blob])
    kept, mask = planarity_filter(both, radius=0.5, score_max=0.05)
    kept_from_plane = mask[: len(plane)].mean()
    kept_from_blob = mask[len(plane):].mean()
    assert kept_from_plane > 0.90   # roof survives
    assert kept_from_blob < 0.10    # confetti does not
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_isolate.py -v`
Expected: the 3 old tests PASS, the 2 new FAIL with `ImportError: cannot import name 'planarity_scores'`.

- [ ] **Step 3: Write the implementation**

Append to `roofkit/isolate.py`:

```python
import open3d as o3d


def planarity_scores(points, radius, max_nn=30):
    """Surface variation per point: how confetti-like is the neighborhood?

    For each point, Open3D fits a covariance to the neighbors within
    `radius` (capped at max_nn, in C++, so it is fast). The covariance's
    three eigenvalues measure the neighborhood's spread along its three
    principal directions. On a flat sheet the smallest eigenvalue is ~0
    (no spread off the plane); in foliage all three are comparable.
    The score is smallest_eigenvalue / sum, ranging 0 (perfect plane) to
    1/3 (isotropic confetti). The RATIO is unitless and scale-independent;
    the RADIUS is a length and therefore scale-DEPENDENT: callers derive
    it from median_nn_spacing, never hardcode it.
    """
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    cloud.estimate_covariances(
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=max_nn))
    eig = np.linalg.eigvalsh(np.asarray(cloud.covariances))  # ascending
    total = eig.sum(axis=1)
    scores = np.full(len(points), 1.0 / 3.0)  # degenerate = worst case
    ok = total > 1e-12  # points with too few neighbors have ~zero covariance
    scores[ok] = eig[ok, 0] / total[ok]
    return scores


def planarity_filter(points, radius, score_max=0.05, max_nn=30):
    """Keep points whose neighborhood is sheet-like (score at or below
    score_max). Known cost: roof edges and ridges score somewhat rough and
    can be eroded; tune score_max visually against that tradeoff."""
    mask = planarity_scores(points, radius, max_nn) <= score_max
    return points[mask], mask
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_isolate.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit, then STOP for the explanation gate**

```bash
git add roofkit/isolate.py tests/test_isolate.py
git commit -m "feat: local planarity filter (surface variation) for foliage removal"
```

Gate walkthrough must cover: what the covariance eigenvalues mean physically; why the score is scale-independent but the radius is not; why degenerate points get the worst score; the edge-erosion tradeoff.

---

### Task 5: Z-verification gate

**Files:**
- Modify: `roofkit/measure.py` (append)
- Test: `tests/test_measure.py`

**Interfaces:**
- Consumes: `tilt_degrees(normal)` already in `roofkit/measure.py`; facet dicts `{"points", "normal", "pitch"}` as produced by `find_roof_planes`.
- Produces: `opposing_pairs(facets, direction_tol_deg=15.0, pitch_tol_deg=10.0) -> list[tuple[int, int]]`, `z_tilt_residual(facets, ...) -> tuple[float | None, list]`, `vertical_from_pair(facet_a, facet_b) -> (3,) ndarray`. Task 9 runs the gate before reporting pitch.

- [ ] **Step 1: Write the failing tests**

`tests/test_measure.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_measure.py -v`
Expected: FAIL with `ImportError: cannot import name 'opposing_pairs'`.

- [ ] **Step 3: Write the implementation**

Append to `roofkit/measure.py`:

```python
# --- Z-verification gate (decision 2026-07-12) ---
# Georeferenced Z comes from meter-grade GPS and is an ASSUMPTION as a
# gravity reference. Before any pitch is reported, measure the residual
# tilt using the building's own symmetry: opposing gable facets must read
# equal pitch, so half their difference IS the Z tilt.


def _up_normal(facet):
    """Facet normal as a unit vector oriented upward (z >= 0). RANSAC's
    normal sign is arbitrary, so orient before comparing directions."""
    n = np.asarray(facet["normal"], float)
    n = n / np.linalg.norm(n)
    return -n if n[2] < 0 else n


def opposing_pairs(facets, direction_tol_deg=15.0, pitch_tol_deg=10.0):
    """Indices (i, j) of facets that face each other like two sides of a
    gable: horizontal components of their normals point in opposite
    directions (within direction_tol_deg) and their pitches are similar
    (within pitch_tol_deg). Both tolerances are angles: scale-independent."""
    pairs = []
    for i in range(len(facets)):
        for j in range(i + 1, len(facets)):
            hi, hj = _up_normal(facets[i]).copy(), _up_normal(facets[j]).copy()
            hi[2] = 0.0
            hj[2] = 0.0
            li, lj = np.linalg.norm(hi), np.linalg.norm(hj)
            if li < 1e-9 or lj < 1e-9:
                continue  # a flat facet faces no direction
            angle = np.degrees(np.arccos(np.clip(hi @ hj / (li * lj), -1, 1)))
            if (angle >= 180.0 - direction_tol_deg and
                    abs(facets[i]["pitch"] - facets[j]["pitch"]) <= pitch_tol_deg):
                pairs.append((i, j))
    return pairs


def z_tilt_residual(facets, direction_tol_deg=15.0, pitch_tol_deg=10.0):
    """(residual_degrees, pairs). Residual = the WORST half-difference of
    pitch across all opposing pairs: conservative on purpose, because the
    gate exists to catch error, not to average it away. Returns (None, [])
    when no pair exists: the gate has no instrument, and that fact must
    reach the report rather than pass silently."""
    pairs = opposing_pairs(facets, direction_tol_deg, pitch_tol_deg)
    if not pairs:
        return None, []
    residuals = [abs(facets[i]["pitch"] - facets[j]["pitch"]) / 2.0
                 for i, j in pairs]
    return max(residuals), pairs


def vertical_from_pair(facet_a, facet_b):
    """True up recovered from a symmetric gable: the bisector of the two
    opposing facet normals. Valid exactly when the two real-world pitches
    are equal, which is the same symmetry assumption the gate itself uses.
    Feed the result to level_cloud if the gate rejects georeferenced Z."""
    up = _up_normal(facet_a) + _up_normal(facet_b)
    return up / np.linalg.norm(up)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_measure.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit, then STOP for the explanation gate**

```bash
git add roofkit/measure.py tests/test_measure.py
git commit -m "feat: Z-verification gate via opposing-facet pitch symmetry"
```

Gate walkthrough must cover: why half the difference equals the Z tilt; why max not mean; why the bisector is true up and what assumption that rests on; why every tolerance here is scale-independent; what happens when no gable pair exists.

---

### Task 6: Facet polygon area (stage 7a)

**Files:**
- Modify: `roofkit/measure.py` (append)
- Test: `tests/test_measure.py` (append)

**Interfaces:**
- Consumes: facet dicts from `find_roof_planes`.
- Produces: `project_to_plane(points, normal) -> (N,2) ndarray`, `alpha_shape_area(pts2d, alpha) -> float`, `facet_area(points, normal, alpha) -> float`. Task 9 reports these; 7b will later reuse `project_to_plane`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_measure.py`:

```python
from roofkit.measure import project_to_plane, alpha_shape_area, facet_area


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
    from scipy.spatial.transform import Rotation
    rot = Rotation.from_euler("x", 40.0, degrees=True)
    tilted = rot.apply(rect)
    normal = rot.apply([0.0, 0.0, 1.0])
    assert abs(facet_area(tilted, normal, alpha=0.15) - 6.0) < 0.1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_measure.py -v`
Expected: the 6 gate tests PASS, the 3 new FAIL with `ImportError: cannot import name 'project_to_plane'`.

- [ ] **Step 3: Write the implementation**

Append to `roofkit/measure.py`:

```python
# --- Stage 7a: polygon area per facet (decision 2026-07-12) ---
# Area is measured IN THE FACET'S OWN PLANE (slope area, what shingles
# cover), not the ground footprint. The alpha shape is a shrink-wrapped
# outline: keep Delaunay triangles whose circumradius is at most alpha,
# sum their areas. Gaps narrower than ~2*alpha get bridged (point noise,
# small occlusions); gaps wider stay open (chimney and dormer holes).
from scipy.spatial import Delaunay


def project_to_plane(points, normal):
    """2D coordinates of points in the facet's own plane. Build an
    orthonormal basis (u, v) perpendicular to the normal and express each
    centered point in it. Distances within the plane are preserved, so
    areas and lengths measured in 2D are the true slope quantities."""
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    helper = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(n, helper)
    u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    centered = points - points.mean(axis=0)
    return np.column_stack([centered @ u, centered @ v])


def alpha_shape_area(pts2d, alpha):
    """Area of the alpha shape of 2D points: the sum of Delaunay triangles
    with circumradius at most alpha. Alpha is a LENGTH and therefore
    scale-dependent: callers derive it from median_nn_spacing."""
    tri = Delaunay(pts2d).simplices
    a, b, c = pts2d[tri[:, 0]], pts2d[tri[:, 1]], pts2d[tri[:, 2]]
    ab, ac, bc = b - a, c - a, c - b
    cross = ab[:, 0] * ac[:, 1] - ab[:, 1] * ac[:, 0]
    tri_area = np.abs(cross) / 2.0
    la = np.linalg.norm(bc, axis=1)
    lb = np.linalg.norm(ac, axis=1)
    lc = np.linalg.norm(ab, axis=1)
    # Circumradius R = (product of side lengths) / (4 * area); degenerate
    # slivers (area ~ 0) get R = inf so they are never kept.
    with np.errstate(divide="ignore", invalid="ignore"):
        circum_r = np.where(tri_area > 1e-15, la * lb * lc / (4.0 * tri_area),
                            np.inf)
    return float(tri_area[circum_r <= alpha].sum())


def facet_area(points, normal, alpha):
    """Slope area of one facet: project into its plane, alpha-shape, sum."""
    return alpha_shape_area(project_to_plane(points, normal), alpha)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_measure.py -v`
Expected: 9 PASSED.

- [ ] **Step 5: Commit, then STOP for the explanation gate**

```bash
git add roofkit/measure.py tests/test_measure.py
git commit -m "feat: per-facet slope area via in-plane Delaunay alpha shape"
```

Gate walkthrough must cover: why slope area requires projecting into the facet plane; what the circumradius test does; the hole behavior (bridged below ~2*alpha, open above) and how that interacts with chimneys; why alpha is scale-dependent.

---

### Task 7: Full-pipeline integration test on the synthetic cloud

**Files:**
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: everything from Tasks 1 to 6 plus the existing `find_roof_planes`.
- Produces: the pass/fail bar that must be green before the real cloud is touched.

- [ ] **Step 1: Write the integration test**

`tests/test_pipeline.py`:

```python
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
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS. If it fails, STOP: something upstream is wrong. Debug with the systematic-debugging skill before touching thresholds at random.

- [ ] **Step 3: Run the whole suite**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 4: Commit, then STOP for the explanation gate**

```bash
git add tests/test_pipeline.py
git commit -m "test: synthetic end-to-end pipeline recovers known pitch and area"
```

Gate walkthrough must cover: why the brown blob is in the test; where each multiplier of `s` appears and what it controls.

---

### Task 8: Dataset-agnostic isolation script (glue plus visual checks)

**Files:**
- Create: `scripts/dataset_config.py`
- Create: `scripts/isolate_roof.py`

**Interfaces:**
- Consumes: `load_xyz_rgb`, `crop_box`, `height_cutoff`, `color_filter`, `planarity_filter`, `median_nn_spacing`, `clean_outliers`.
- Produces: `load_config(dataset_dir) -> dict` (shared with Task 9); `<dataset>\roof.npy`, the isolated roof points Task 9 loads. (A `.npy` of a plain NumPy array is not a point cloud format; io.py stays the only format-aware module.)

No TDD here: this is glue whose verification is visual, per the design's per-stage checks.

- [ ] **Step 1: Write the shared per-dataset config loader**

`scripts/dataset_config.py`:

```python
# Per-dataset configuration. Site-specific numbers (crop box, height
# cutoff, tuned cutoffs) describe a DATASET, so they live in a JSON file
# next to that dataset's data (<dataset>\roofkit.json), never in code.
# The pipeline code is identical for every cloud; only the config differs.
# Same seam principle as io.py: swap the dataset, nothing else changes.
import json
from pathlib import Path

DEFAULTS = {
    # relative to the dataset directory
    "cloud": "odm_georeferencing/odm_georeferenced_model.laz",
    # --- site-specific, filled in from the viewer (stage 0 / 1) ---
    "crop_min": None,        # [x, y, z]
    "crop_max": None,        # [x, y, z]
    "z_min": None,           # just below eave height, cloud units
    # --- scale-independent cutoffs (transfer between clouds) ---
    "exg_max": 0.1,          # unitless ExG color cutoff
    "score_max": 0.05,       # unitless planarity cutoff
    # --- multiples of median_nn_spacing (scale-adaptive) ---
    "radius_mult": 5.0,      # planarity radius = radius_mult * spacing
    "band_mult": 3.0,        # RANSAC band = band_mult * spacing
    "alpha_mult": 4.0,       # alpha shape radius = alpha_mult * spacing
    # --- density-dependent ---
    "min_points_frac": 0.03, # a facet must hold this fraction of roof points
    # --- design constants ---
    "gate_limit_deg": 1.0,   # reject georeferenced Z above this residual
}


def load_config(dataset_dir):
    """Read <dataset>/roofkit.json over the defaults. Writes a template on
    first use so every new dataset starts from the same documented knobs."""
    dataset_dir = Path(dataset_dir)
    path = dataset_dir / "roofkit.json"
    cfg = dict(DEFAULTS)
    if path.exists():
        cfg.update(json.loads(path.read_text()))
    else:
        path.write_text(json.dumps(cfg, indent=2))
        print(f"Wrote template config {path}. Fill in crop_min/crop_max/"
              f"z_min from the viewer before stages 1+.")
    cfg["cloud_path"] = str(dataset_dir / cfg["cloud"])
    cfg["roof_path"] = str(dataset_dir / "roof.npy")
    return cfg
```

- [ ] **Step 2: Write the isolation driver**

`scripts/isolate_roof.py`:

```python
# Stage-by-stage roof isolation for ANY dataset, with a viewer after each
# stage. Run:
#   python scripts/isolate_roof.py C:\odm\datasets\big_house --stage 0
# Stages: 0 raw, 1 crop, 2 height cutoff, 3 color filter, 4 planarity.
import argparse
import numpy as np
import open3d as o3d
from dataset_config import load_config
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box
from roofkit.isolate import height_cutoff, color_filter, planarity_filter
from roofkit.stats import median_nn_spacing
from roofkit.segment import clean_outliers


def show(points, colors=None, title=""):
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    if colors is not None:
        cloud.colors = o3d.utility.Vector3dVector(colors)
    print(f"[{title}] {len(points):,} points")
    o3d.visualization.draw_geometries([cloud], window_name=title)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="dataset directory (holds roofkit.json)")
    ap.add_argument("--stage", type=int, default=0,
                    help="0 raw, 1 crop, 2 height, 3 color, 4 planarity")
    ap.add_argument("--save", action="store_true",
                    help="after stage 4, write roof points to <dataset>/roof.npy")
    args = ap.parse_args()
    cfg = load_config(args.dataset)

    points, colors = load_xyz_rgb(cfg["cloud_path"])
    if args.stage == 0:
        show(points, colors, "0 raw")
        return

    if cfg["crop_min"] is None or cfg["crop_max"] is None:
        raise SystemExit("Set crop_min/crop_max in roofkit.json from the "
                         "stage-0 view first.")
    points, mask = crop_box(points, cfg["crop_min"], cfg["crop_max"])
    colors = colors[mask]
    if args.stage == 1:
        show(points, colors, "1 crop")
        return

    if cfg["z_min"] is None:
        raise SystemExit("Set z_min in roofkit.json from the stage-1 view first.")
    points, mask = height_cutoff(points, cfg["z_min"])
    colors = colors[mask]
    if args.stage == 2:
        show(points, colors, "2 height cutoff")
        return

    points, mask = color_filter(points, colors, exg_max=cfg["exg_max"])
    colors = colors[mask]
    if args.stage == 3:
        show(points, colors, "3 color filter")
        return

    s = median_nn_spacing(points)
    print(f"median nn spacing: {s:.4f} cloud units")
    points, mask = planarity_filter(points, radius=cfg["radius_mult"] * s,
                                    score_max=cfg["score_max"])
    points = clean_outliers(points)
    show(points, None, "4 planarity filter + outlier cleanup")
    if args.save:
        np.save(cfg["roof_path"], points)
        print(f"saved {len(points):,} roof points to {cfg['roof_path']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Choose the crop box and height cutoff visually**

Run `python scripts/isolate_roof.py C:\odm\datasets\big_house --stage 0` (this writes the template `roofkit.json`), read coordinates off the viewer (same workflow as `scripts/find_crop_box.py` on tyco), fill in `crop_min`/`crop_max` in `C:\odm\datasets\big_house\roofkit.json`. Re-run with `--stage 1` until the box hugs the house. Then set `z_min` just below the eaves and check with `--stage 2`. Assumption A3 check: confirm no uphill ground survives the cutoff.

- [ ] **Step 4: Verify the color stage visually**

Run `--stage 3`. Expected: canopy bulk gone, roof intact, a residue of dark and brown foliage remaining. If the roof itself gets eaten, ExG assumption A1 is violated for this roof: STOP and revisit the design.

- [ ] **Step 5: Verify the planarity stage visually**

Run `--stage 4`. Expected: foliage residue gone, facets intact, some thinning along ridges and edges. Tune `score_max` (and `radius_mult` if needed) in `roofkit.json` visually against the edge-erosion tradeoff. Then run with `--save`.

- [ ] **Step 6: Commit**

```bash
git add scripts/dataset_config.py scripts/isolate_roof.py
git commit -m "feat: dataset-agnostic staged isolation script with per-dataset config"
```

---

### Task 9: Measurement script: segmentation, gate, pitch, area (stage 7a complete)

**Files:**
- Create: `scripts/measure_roof.py`

**Interfaces:**
- Consumes: `load_config` (Task 8); `<dataset>\roof.npy`; `find_roof_planes`, `z_tilt_residual`, `vertical_from_pair`, `level_cloud`, `facet_area`, `median_nn_spacing`.
- Produces: the printed 7a report: per-facet pitch and area, total area, Z-gate residual. This is the integration test for the whole pipeline and the input to the tape-measure validation.

- [ ] **Step 1: Write the script**

`scripts/measure_roof.py`:

```python
# Stages 5-7a on any isolated roof: segment facets, run the Z gate, report
# per-facet pitch and slope area. Run:
#   python scripts/measure_roof.py C:\odm\datasets\big_house
# The GATE RUNS FIRST: no pitch or area is printed as trusted output until
# the residual is known (decision 2026-07-12). Areas are in cloud units
# squared until the tape-measure scale factor is applied (decision
# 2026-07-12: scale from tape, not GPS).
import argparse
import numpy as np
import open3d as o3d
from dataset_config import load_config
from roofkit.stats import median_nn_spacing
from roofkit.segment import find_roof_planes, level_cloud
from roofkit.measure import z_tilt_residual, vertical_from_pair, facet_area


def segment(points, s, cfg):
    return find_roof_planes(
        points, distance_threshold=cfg["band_mult"] * s,
        min_points=int(cfg["min_points_frac"] * len(points)))


def show_facets(facets):
    rng = np.random.default_rng(0)
    clouds = []
    for f in facets:
        c = o3d.geometry.PointCloud()
        c.points = o3d.utility.Vector3dVector(f["points"])
        c.paint_uniform_color(rng.uniform(0.1, 0.9, 3))
        clouds.append(c)
    o3d.visualization.draw_geometries(clouds, window_name="facets")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="dataset directory (holds roofkit.json)")
    args = ap.parse_args()
    cfg = load_config(args.dataset)

    points = np.load(cfg["roof_path"])
    s = median_nn_spacing(points)
    print(f"{len(points):,} roof points, spacing {s:.4f}")

    facets = segment(points, s, cfg)
    print(f"{len(facets)} facets found")
    show_facets(facets)

    # --- Z-verification gate, BEFORE any trusted numbers ---
    residual, pairs = z_tilt_residual(facets)
    if residual is None:
        print("GATE: no opposing pair found. No instrument for Z. STOP:")
        print("a fallback vertical reference must be designed before any")
        print("pitch from this cloud can be trusted.")
        return
    print(f"GATE: residual Z tilt = {residual:.2f} deg "
          f"from {len(pairs)} opposing pair(s)")
    if residual > cfg["gate_limit_deg"]:
        print(f"GATE FAILED (> {cfg['gate_limit_deg']} deg): leveling from "
              f"the first opposing pair and re-segmenting.")
        i, j = pairs[0]
        up = vertical_from_pair(facets[i], facets[j])
        points = level_cloud(points, up)
        facets = segment(points, median_nn_spacing(points), cfg)
        residual, pairs = z_tilt_residual(facets)
        print(f"GATE re-run: residual = {residual:.2f} deg")

    # --- 7a report ---
    total = 0.0
    print(f"\n{'facet':>5} {'points':>8} {'pitch deg':>10} {'area':>10}")
    for k, f in enumerate(facets):
        area = facet_area(f["points"], f["normal"], alpha=cfg["alpha_mult"] * s)
        total += area
        print(f"{k:>5} {len(f['points']):>8,} {f['pitch']:>10.1f} {area:>10.2f}")
    print(f"\ntotal roof area: {total:.2f} cloud units^2")
    print(f"pitch uncertainty floor (gate residual): {residual:.2f} deg")
    print("NOTE: multiply areas by (tape scale factor)^2 before comparing "
          "to real dimensions.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it on big_house and verify the facet count visually**

Run: `python scripts/measure_roof.py C:\odm\datasets\big_house`
Expected: the facet viewer shows each real roof plane in one solid color, dormers and chimneys NOT absorbed into main facets, no facet spanning two real planes. Tune `band_mult` down in `roofkit.json` if planes merge, `min_points_frac` down if real facets are missed.

- [ ] **Step 3: Record the gate result**

Expected: `GATE: residual Z tilt = X deg`. Whatever X is, it goes into DECISIONS.md via the decision-log skill: it is the first measured evidence for or against assumption A2.

- [ ] **Step 4: Sanity-check the numbers**

Pitches should look like real roof pitches (10 to 60 degrees, consistent within gable pairs). Total area times the tape-derived scale factor squared should land near a rough visual estimate of the real roof. Wild disagreement means an upstream stage is contaminated: that is 7a doing its integration-test job.

- [ ] **Step 5: Commit, then STOP for the final explanation gate and decision logging**

```bash
git add scripts/measure_roof.py
git commit -m "feat: measurement script: segmentation, Z gate, 7a report"
```

Gate walkthrough: recap the full chain end to end. Then log via the decision-log skill: the measured gate residual, the tuned config values for big_house, and the 7a numbers. Update Current state: 7a complete, next action tape-scale validation, then the 7b plan.

---

## Verification (whole plan)

- `python -m pytest tests/ -v`: all green after every task.
- Visual checks at Tasks 8 and 9 as specified per step.
- Dataset-agnosticism check: no dataset name in any code file; `git grep -i big_house -- roofkit scripts tests` returns nothing.
- Done when: the 7a report prints per-facet pitch and area with the gate residual for big_house, and every explanation gate has been passed.
