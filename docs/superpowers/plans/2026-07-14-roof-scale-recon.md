# Roof-Derived Scale Reconnaissance Implementation Plan

> **For agentic workers:** Implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive and rank every roof-based scale-span candidate for big_house from fitted geometry alone, with bias and noise reported separately, before any tape measurement.

**Architecture:** Three new geometry primitives in `roofkit/measure.py` (eave line, parallel-line span, line extent), proven on a synthetic eroded gable before touching real data. A recon script `scripts/roof_recon.py` orchestrates: segment facets (reusing measure_roof's seed-pinned path via a small shared module), derive intersection lines and bracketed eave lines, enumerate candidates, rank by predicted error. A pre-registration script freezes cloud-unit outputs into a committed JSON before the field visit.

**Tech Stack:** Python 3.12 (native Windows venv `.venv`), NumPy, Open3D, pytest. Spec: `docs/superpowers/specs/2026-07-14-roof-scale-recon-design.md`. Read the spec before starting; read `DECISIONS.md` entries dated 2026-07-14 for the constraints.

## Global Constraints

- Never use em dashes anywhere, including code comments and printouts.
- Explain WHY in comments, matching the existing comment density and style of `roofkit/measure.py`.
- Every threshold is documented at its definition as scale-dependent (a length, derived from `median_nn_spacing`) or scale-free (an angle or unitless ratio). This is a house rule an interviewer probes.
- Diagnostics print in CLOUD UNITS (`cu`), never cm/m. GPS scale is an untested assumption. The only exception is the tape-error term used for RANKING, documented exactly as `wall_recon.py` documents its `TAPE_ERR`.
- `roofkit/io.py` stays the only module touching file formats. Scripts load `roof.npy` via `np.load` (existing pattern in `measure_roof.py`) and `.laz` via `roofkit.io.load_xyz_rgb`.
- Pin randomness: `o3d.utility.random.seed(0)` and `np.random.default_rng(0)` wherever RANSAC or subsampling runs.
- Do not modify `scripts/measure_roof.py`, `roofkit/segment.py`, or any existing test. All 32 existing tests must stay green: run `python -m pytest -q` from the repo root (venv activated) after every task.
- Bias and noise are never folded together. Bracket outputs are lower/upper/delta, never averaged, never half-corrected.
- The user is a mechanical engineering student, strong on geometry, new to software. **Explanation gate steps in Tasks 2, 3, 4, and 8 are mandatory**: walk him through the approach and every threshold, invite questions, never quiz him (his standing preference). Code enters `roofkit/` only after his OK (decision 2026-07-12).
- Commit after every task with the message given in the task.

---

### Task 1: Synthetic erosion and truth helpers

The bracket must be proven against known truth before real data. `tests/synthetic.py` already builds a gable with known dimensions; add an eroder that strips a known depth from the eaves, and a truth function for eave position.

**Files:**
- Modify: `tests/synthetic.py` (append at end)
- Test: `tests/test_synthetic.py` (append at end)

**Interfaces:**
- Consumes: `gable_roof(pitch_deg, width, depth, n_per_side, seed, noise)` from `tests/synthetic.py` (exists).
- Produces: `erode_eaves(points, pitch_deg, width, depth_cu) -> (M,3) ndarray`, and `slope_dist_from_eave(points, pitch_deg, width) -> (N,) ndarray`. Later tasks rely on these exact names.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_synthetic.py`:

```python
from synthetic import gable_roof, erode_eaves, slope_dist_from_eave
import numpy as np


def test_erode_eaves_removes_exactly_the_edge_strip():
    pts = gable_roof(pitch_deg=30.0, width=10.0, depth=6.0, n_per_side=8000)
    eroded = erode_eaves(pts, pitch_deg=30.0, width=10.0, depth_cu=0.5)
    # every survivor sits at least 0.5 cu (slope distance) from an eave
    assert slope_dist_from_eave(eroded, 30.0, 10.0).min() >= 0.5
    # and the strip really was populated before erosion
    assert len(eroded) < len(pts)
    # interior is untouched: the deepest point survives
    assert np.isclose(eroded[:, 2].max(), pts[:, 2].max())
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_synthetic.py -q`
Expected: FAIL with `ImportError: cannot import name 'erode_eaves'`

- [ ] **Step 3: Implement**

Append to `tests/synthetic.py`:

```python
def slope_dist_from_eave(points, pitch_deg, width):
    """Each point's distance from its side's eave, measured IN the roof
    plane down the slope (the same axis the eave estimator reads).
    gable_roof puts the eaves at |x| = width/2, so the horizontal run to
    the eave is width/2 - |x| and the slope distance divides by cos."""
    run = width / 2.0 - np.abs(points[:, 0])
    return run / np.cos(np.radians(pitch_deg))


def erode_eaves(points, pitch_deg, width, depth_cu):
    """Strip every point within depth_cu (slope distance) of either
    eave: the synthetic stand-in for edge erosion, whose depth is KNOWN
    so bracket tests have a truth to contain."""
    return points[slope_dist_from_eave(points, pitch_deg, width) >= depth_cu]
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_synthetic.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/synthetic.py tests/test_synthetic.py
git commit -m "test: synthetic eave erosion with known depth for bracket truth tests"
```

---

### Task 2: `_density_edge` and `line_extent` in roofkit/measure.py

The shared estimator: the supported extent of a 1D coordinate set. Used for eave position (Task 3) and line length (this task). One estimator, validated once.

**Files:**
- Modify: `C:\dev\roof-pipeline\roofkit\measure.py` (append after `up_from_tilt`)
- Create: `tests/test_recon_primitives.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `_density_edge(t, bin_width, edge_frac=0.5) -> (t_lo, t_hi, n_lo, n_hi)` and `line_extent(points, p0, d, spacing, edge_frac=0.5, bin_mult=4.0) -> dict` with keys `t_lo, t_hi, length, n_lo, n_hi`. Tasks 3, 7, 8 use these exact signatures.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_recon_primitives.py`:

```python
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
    assert ext["n_lo"] > 20 and ext["n_hi"] > 20


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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_recon_primitives.py -q`
Expected: FAIL with `ImportError: cannot import name 'line_extent'`

- [ ] **Step 3: Implement**

Append to `roofkit/measure.py` (after `up_from_tilt`, before the 7a section):

```python
# --- Recon primitives (decision 2026-07-14: roof-derived scale spans) ---
# A span between two DERIVED parallel lines depends on no endpoint, which
# is why it beats a line LENGTH as a scale candidate: a line's ends sit
# where facets stop being reconstructed, the cloud's worst data. These
# primitives make both constructs measurable, with the endpoint
# dependence of the length isolated in one estimator so its bias can be
# reported instead of hidden.


def _density_edge(t, bin_width, edge_frac=0.5):
    """Supported extent of a 1D coordinate set: the extreme values among
    histogram bins carrying at least edge_frac of the central (median
    filled-bin) density. Stragglers past the real edge live in
    near-empty bins and are excluded. Erosion removes whole edge bins,
    so the reading moves INWARD: a one-sided bias with known sign,
    which callers report as a bracket, never correct away.
    bin_width is a LENGTH (scale-dependent: callers derive it from
    median_nn_spacing); edge_frac is a unitless ratio, scale-free.
    Returns (t_lo, t_hi, n_lo, n_hi): the supported extremes and the
    point count inside each supporting end bin."""
    t = np.asarray(t, float)
    edges = np.arange(t.min(), t.max() + bin_width, bin_width)
    if len(edges) < 4:  # fewer than 3 bins: nothing to compare against
        return float(t.min()), float(t.max()), len(t), len(t)
    counts, edges = np.histogram(t, bins=edges)
    central = float(np.median(counts[counts > 0]))
    ok = np.flatnonzero(counts >= edge_frac * central)
    lo, hi = ok[0], ok[-1]
    kept = t[(t >= edges[lo]) & (t <= edges[hi + 1])]
    n_lo = int(((t >= edges[lo]) & (t < edges[lo + 1])).sum())
    n_hi = int(((t >= edges[hi]) & (t <= edges[hi + 1])).sum())
    return float(kept.min()), float(kept.max()), n_lo, n_hi


def line_extent(points, p0, d, spacing, edge_frac=0.5, bin_mult=4.0):
    """Supported extent of a line's contact points ALONG the line. The
    two ends are where the supporting facets stop overlapping: the
    eroded edge zone. This is the one primitive whose answer depends on
    the cloud's worst data, so callers must report per-end sensitivity
    (re-select contacts at other radii and diff the ends) rather than
    trusting the ends as read.
    Returns dict: t_lo, t_hi (cu along d, relative to p0), length,
    n_lo, n_hi (per-end supporting counts)."""
    d = np.asarray(d, float)
    d = d / np.linalg.norm(d)
    t = (np.asarray(points, float) - np.asarray(p0, float)) @ d
    t_lo, t_hi, n_lo, n_hi = _density_edge(t, bin_mult * spacing, edge_frac)
    return {"t_lo": t_lo, "t_hi": t_hi, "length": t_hi - t_lo,
            "n_lo": n_lo, "n_hi": n_hi}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_recon_primitives.py tests/test_measure.py -q`
Expected: all PASS

- [ ] **Step 5: Explanation gate (do not skip, do not quiz)**

Walk Emmett through: why a histogram density edge instead of min/max (stragglers), why the bias is one-sided (erosion deletes bins, never adds them), which knobs are scale-dependent (`bin_width` via `bin_mult * spacing`) versus scale-free (`edge_frac`). Invite questions. Wait for his OK.

- [ ] **Step 6: Commit**

```bash
git add roofkit/measure.py tests/test_recon_primitives.py
git commit -m "feat: density-edge estimator and line_extent; erosion reads short, never long"
```

---

### Task 3: `eave_line` with the origin parameter

**Files:**
- Modify: `C:\dev\roof-pipeline\roofkit\measure.py` (append after `line_extent`)
- Test: `tests/test_recon_primitives.py` (append)

**Interfaces:**
- Consumes: `_density_edge` (Task 2).
- Produces: `eave_line(points, normal, spacing, origin=None, edge_frac=0.5, bin_mult=4.0) -> dict | None` with keys `p0, d, w, t_edge, n_edge, azimuth_deg`. Tasks 5, 7, 8 use this exact signature. `origin` is the comparability anchor: pass the TIGHT set's centroid when reading a LOOSE set so `t_edge_loose - t_edge_tight` IS the bracket delta.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_recon_primitives.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_recon_primitives.py -q`
Expected: FAIL with `ImportError: cannot import name 'eave_line'`

- [ ] **Step 3: Implement**

Append to `roofkit/measure.py` after `line_extent`:

```python
def eave_line(points, normal, spacing, origin=None,
              edge_frac=0.5, bin_mult=4.0):
    """The eave of a facet, derived WITHOUT fitting a direction to the
    ragged boundary. Geometry gives the direction free: a non-horizontal
    plane contains exactly one level direction, so the eave is exactly
    parallel to its own ridge. The only estimated quantity is the
    eave's POSITION down the slope: the density edge of the along-slope
    distribution (_density_edge), averaged over the whole edge length.

    origin anchors the downslope coordinate (default: the point set's
    own centroid). Pass the TIGHT set's centroid when reading a LOOSE
    set, so tight and loose share one axis and their t_edge difference
    IS the two-cloud bracket delta (decision 2026-07-14).

    Returns None for a near-horizontal plane (no level direction), else
    a dict:
      p0          : a point on the eave line (origin + t_edge * w)
      d           : unit level direction (the eave/ridge direction)
      w           : in-plane downslope unit vector, w[2] < 0
      t_edge      : downslope coordinate of the eave, relative to origin
      n_edge      : point count in the supporting end bin
      azimuth_deg : bearing of d, folded to [0, 180) (a line has no
                    forward end)"""
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    if n[2] < 0:
        n = -n
    if np.hypot(n[0], n[1]) < 0.02:  # within ~1 deg of flat: no downslope
        return None
    d = np.cross(n, [0.0, 0.0, 1.0])
    d = d / np.linalg.norm(d)
    w = np.cross(n, d)  # in-plane, perpendicular to the level direction
    if w[2] > 0:
        w = -w  # orient downslope, so bigger t_edge means longer facet
    points = np.asarray(points, float)
    origin = points.mean(axis=0) if origin is None else np.asarray(origin, float)
    t = (points - origin) @ w
    _, t_hi, _, n_hi = _density_edge(t, bin_mult * spacing, edge_frac)
    az = float(np.degrees(np.arctan2(d[0], d[1])) % 360.0)
    if az >= 180.0:
        az -= 180.0
    return {"p0": origin + t_hi * w, "d": d, "w": w, "t_edge": float(t_hi),
            "n_edge": n_hi, "azimuth_deg": az}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_recon_primitives.py -q`
Expected: all PASS

- [ ] **Step 5: Explanation gate**

Walk Emmett through: the unique-level-direction argument (why the direction is exact and only one scalar is estimated), the origin parameter as the bracket's comparability anchor, why noise-free estimates can never read past the physical edge. Invite questions. Wait for his OK.

- [ ] **Step 6: Commit**

```bash
git add roofkit/measure.py tests/test_recon_primitives.py
git commit -m "feat: eave_line, direction from the plane, position from the density edge"
```

---

### Task 4: `line_pair_span`

**Files:**
- Modify: `C:\dev\roof-pipeline\roofkit\measure.py` (append after `eave_line`)
- Test: `tests/test_recon_primitives.py` (append)

**Interfaces:**
- Consumes: `plane_intersection` (exists), `eave_line` (Task 3), `_plane_fit` (exists).
- Produces: `line_pair_span(p0a, da, p0b, db, t_lo, t_hi) -> dict` with keys `span, span_lo, span_hi, sens, divergence_deg`. Tasks 7, 8 use this exact signature. `t_lo, t_hi` is the evaluation window in cu along line A relative to `p0a` (the caller supplies the overlap of the two lines' supports).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_recon_primitives.py`:

```python
from roofkit.measure import line_pair_span, plane_intersection, _plane_fit


def gable_ridge_and_eave():
    """Fitted ridge line and derived eave line of the synthetic gable's
    right side, the way the recon script builds them."""
    pts = gable_roof(PITCH, WIDTH, DEPTH, N_SIDE)
    left, right = pts[pts[:, 0] <= 0], pts[pts[:, 0] > 0]
    na, ca = _plane_fit(left)
    nb, cb = _plane_fit(right)
    p0, d = plane_intersection(na, ca, nb, cb)
    e = eave_line(right, nb, median_nn_spacing(right))
    return pts, (p0, d), e


def test_ridge_to_eave_span_is_the_true_slope_length():
    pts, (p0, d), e = gable_ridge_and_eave()
    r = line_pair_span(p0, d, e["p0"], e["d"], t_lo=1.0, t_hi=5.0)
    true_slope = (WIDTH / 2.0) / np.cos(np.radians(PITCH))
    s = median_nn_spacing(pts)
    # the estimate sits within about one density bin of truth, and the
    # error is toward SHORT (the eave estimator's lower-bound side)
    assert r["span"] <= true_slope + 1e-6
    assert true_slope - r["span"] <= 1.5 * 4.0 * s
    assert r["divergence_deg"] < 0.5


def test_span_does_not_depend_on_where_either_line_ends():
    pts = gable_roof(PITCH, WIDTH, DEPTH, N_SIDE)
    # crop 25% off both y-ends: both lines lose their ends entirely
    crop = pts[(pts[:, 1] >= 0.25 * DEPTH) & (pts[:, 1] <= 0.75 * DEPTH)]
    spans = []
    for cloud in (pts, crop):
        left, right = cloud[cloud[:, 0] <= 0], cloud[cloud[:, 0] > 0]
        na, ca = _plane_fit(left)
        nb, cb = _plane_fit(right)
        p0, d = plane_intersection(na, ca, nb, cb)
        e = eave_line(right, nb, median_nn_spacing(right))
        spans.append(line_pair_span(p0, d, e["p0"], e["d"],
                                    t_lo=2.5, t_hi=3.5)["span"])
    # losing the ends moves the span by at most a couple of point
    # spacings: THE property that makes parallel-line spans the
    # instrument of choice (spec: endpoint-free claim, tested directly)
    assert abs(spans[0] - spans[1]) <= 0.05
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_recon_primitives.py -q`
Expected: FAIL with `ImportError: cannot import name 'line_pair_span'`

- [ ] **Step 3: Implement**

Append to `roofkit/measure.py` after `eave_line`:

```python
def line_pair_span(p0a, da, p0b, db, t_lo, t_hi):
    """Perpendicular separation of two near-parallel lines, evaluated at
    stated positions along line A, because a tape goes to ONE physical
    spot. Nothing here depends on where either line's point support
    ends, which is why parallel-line spans beat line lengths as scale
    candidates (a length's ends sit in the eroded edge zone).
    t_lo, t_hi: evaluation window along line A in cu relative to p0a,
    normally the overlap of the two lines' supported extents.
    Returns dict: span (window middle), span_lo/span_hi (window ends),
    sens (worst drift from the middle: if the lines diverge, the tape's
    exact position matters by this much), divergence_deg."""
    da = np.asarray(da, float)
    db = np.asarray(db, float)
    p0a = np.asarray(p0a, float)
    p0b = np.asarray(p0b, float)
    da = da / np.linalg.norm(da)
    db = db / np.linalg.norm(db)
    if da @ db < 0:  # a line has no forward end; compare like with like
        db = -db
    divergence = float(np.degrees(np.arccos(np.clip(da @ db, -1.0, 1.0))))

    def dist_to_b(q):
        rel = q - p0b
        return float(np.linalg.norm(rel - (rel @ db) * db))

    mid = (t_lo + t_hi) / 2.0
    span = dist_to_b(p0a + mid * da)
    span_lo = dist_to_b(p0a + t_lo * da)
    span_hi = dist_to_b(p0a + t_hi * da)
    return {"span": span, "span_lo": span_lo, "span_hi": span_hi,
            "sens": max(abs(span_lo - span), abs(span_hi - span)),
            "divergence_deg": divergence}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_recon_primitives.py -q`
Expected: all PASS

- [ ] **Step 5: Explanation gate**

Walk Emmett through: why the span is evaluated at a stated position rather than "between the lines" in the abstract (the tape goes to one spot; divergence makes position matter), and the endpoint-insensitivity test as the direct proof of the design's central claim. Invite questions. Wait for his OK.

- [ ] **Step 6: Commit**

```bash
git add roofkit/measure.py tests/test_recon_primitives.py
git commit -m "feat: line_pair_span, endpoint-free separation of parallel derived lines"
```

---

### Task 5: Honesty tests, split-half flattery and contamination

No new production code. These tests pin the two claims the decision log makes: repeatability flatters edge-derived quantities, and clutter near the plane blows the loose reading out (which must be detected, not averaged in).

**Files:**
- Test: `tests/test_recon_primitives.py` (append)

**Interfaces:**
- Consumes: `eave_line` (Task 3), `erode_eaves`, `foliage_blob` (tests/synthetic.py).
- Produces: nothing; guarantees later tasks rely on.

- [ ] **Step 1: Write the tests (they should pass immediately; they pin behavior, not drive new code)**

Append to `tests/test_recon_primitives.py`:

```python
from synthetic import foliage_blob


def test_split_half_repeatability_flatters_an_eroded_eave():
    """The reason the bracket exists: both halves of an eroded set are
    eroded identically, so split-half looks superb while the reading is
    biased by the full erosion depth. Pinned so nobody ever swaps the
    bracket for a repeatability number."""
    full = right_side(gable_roof(PITCH, WIDTH, DEPTH, N_SIDE))
    tight = erode_eaves(full, PITCH, WIDTH, depth_cu=0.5)
    s = median_nn_spacing(tight)
    origin = tight.mean(axis=0)
    halves = [eave_line(tight[off::2], NORMAL_R, s, origin=origin)["t_edge"]
              for off in (0, 1)]
    rep = abs(halves[0] - halves[1])
    truth_gap = (eave_line(full, NORMAL_R, s, origin=origin)["t_edge"]
                 - eave_line(tight, NORMAL_R, s, origin=origin)["t_edge"])
    assert rep < 0.2 * truth_gap  # repeatability says mm; the bias is 0.5 cu


def test_clutter_near_the_plane_blows_the_loose_reading_out():
    """Vegetation within the plane gate makes the loose eave read LONG.
    The recon must flag a wide bracket as contamination, so this pins
    that the blowout is visible in t_edge, not hidden."""
    full = right_side(gable_roof(PITCH, WIDTH, DEPTH, N_SIDE))
    s = median_nn_spacing(full)
    origin = full.mean(axis=0)
    clean = eave_line(full, NORMAL_R, s, origin=origin)["t_edge"]
    # a limb just past the eave, ON the extended plane so a distance
    # gate alone cannot reject it: x centered 1.0 past the eave
    x0 = WIDTH / 2.0 + 1.0
    z0 = (WIDTH / 2.0 - x0) * np.tan(np.radians(PITCH))
    blob = foliage_blob(center=(x0, DEPTH / 2.0, z0), size=1.5, n=4000)
    dirty = eave_line(np.vstack([full, blob]), NORMAL_R, s,
                      origin=origin)["t_edge"]
    assert dirty - clean > 0.5  # the blowout is unmistakable, so flaggable
```

- [ ] **Step 2: Run to verify pass**

Run: `python -m pytest tests/test_recon_primitives.py -q`
Expected: all PASS. If either fails, the primitives do not support the design's honesty claims: STOP and re-examine before proceeding (do not weaken the assertions).

- [ ] **Step 3: Commit**

```bash
git add tests/test_recon_primitives.py
git commit -m "test: pin the honesty claims, split-half flattery and loose-set blowout"
```

---

### Task 6: Shared facet discovery in `scripts/recon_common.py`

measure_roof.py's discovery block (seed pin, subsample fit, full-cloud assign, trimmed refit) is needed by roof_recon.py and preregister.py. Extract it into a shared script module. Do NOT modify measure_roof.py itself (it is the frozen 7a instrument; churn there risks the pre-registration baseline).

**Files:**
- Create: `scripts/recon_common.py`
- Test: `tests/test_recon_common.py`

**Interfaces:**
- Consumes: `find_roof_planes, assign_to_planes, fit_plane_trimmed` from `roofkit.segment`; `tilt_degrees` from `roofkit.measure`; `median_nn_spacing` from `roofkit.stats`.
- Produces: `discover_facets(points, cfg, seed=0) -> (facets, band, spacing_full)` where facets is a list of dicts with keys `points, normal, pitch` (normal up-oriented by fit_plane_trimmed's convention, points are the trimmed core). cfg needs keys `fit_sample, band_mult, min_points_frac, max_planes, trim_mult`. Tasks 7, 9 use this exact signature.

- [ ] **Step 1: Write the failing test**

Create `tests/test_recon_common.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import numpy as np
from synthetic import gable_roof
from recon_common import discover_facets

CFG = {"fit_sample": 200000, "band_mult": 3.0, "min_points_frac": 0.03,
       "max_planes": 12, "trim_mult": 3.0}


def test_discover_facets_finds_both_gable_sides():
    pts = gable_roof(pitch_deg=30.0, width=10.0, depth=6.0,
                     n_per_side=8000, noise=0.01)
    facets, band, s = discover_facets(pts, CFG)
    assert len(facets) == 2
    for f in facets:
        assert abs(f["pitch"] - 30.0) < 0.5
    assert band > 0 and s > 0


def test_discover_facets_is_reproducible():
    pts = gable_roof(pitch_deg=30.0, width=10.0, depth=6.0,
                     n_per_side=8000, noise=0.01)
    a, _, _ = discover_facets(pts, CFG)
    b, _, _ = discover_facets(pts, CFG)
    assert len(a) == len(b)
    for fa, fb in zip(a, b):
        assert len(fa["points"]) == len(fb["points"])
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_recon_common.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'recon_common'`

- [ ] **Step 3: Implement**

Create `scripts/recon_common.py`:

```python
# Facet discovery shared by the recon scripts: the same seed-pinned
# subsample-fit / full-assign / trimmed-refit sequence measure_roof.py
# runs, extracted so roof_recon.py and preregister.py segment the cloud
# IDENTICALLY to the 7a instrument. measure_roof.py itself is left
# untouched: it is the frozen pipeline the pre-registration commits.
import numpy as np
import open3d as o3d
from roofkit.stats import median_nn_spacing
from roofkit.segment import (find_roof_planes, assign_to_planes,
                             fit_plane_trimmed)
from roofkit.measure import tilt_degrees


def discover_facets(points, cfg, seed=0):
    """Segment roof facets exactly as measure_roof.py does.
    Returns (facets, band, spacing_full): facets is a list of dicts
    with the trimmed core points, the robust normal, and the pitch;
    band is the RANSAC/assignment band in cu; spacing_full is the full
    cloud's median point spacing in cu."""
    o3d.utility.random.seed(seed)  # RANSAC reproducibility (2026-07-13)
    rng = np.random.default_rng(seed)
    s_full = median_nn_spacing(points)
    n_fit = min(cfg["fit_sample"], len(points))
    sub = points[rng.choice(len(points), n_fit, replace=False)]
    s_sub = median_nn_spacing(sub)
    band = cfg["band_mult"] * s_sub  # a LENGTH: scale-dependent by design
    planes = find_roof_planes(sub, distance_threshold=band,
                              min_points=int(cfg["min_points_frac"] * n_fit),
                              max_planes=cfg["max_planes"])
    owner, dist = assign_to_planes(points, planes, max_dist=np.inf)
    facets = []
    for k in range(len(planes)):
        member = (owner == k) & (dist <= band)
        if member.sum() < 3:
            continue
        mine = points[member]
        normal, keep = fit_plane_trimmed(mine, trim_mult=cfg["trim_mult"])
        facets.append({"points": mine[keep], "normal": normal,
                       "pitch": tilt_degrees(normal)})
    return facets, band, s_full
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_recon_common.py -q` then `python -m pytest -q`
Expected: all PASS (existing 32 plus the new files)

- [ ] **Step 5: Commit**

```bash
git add scripts/recon_common.py tests/test_recon_common.py
git commit -m "feat: shared seed-pinned facet discovery for the recon scripts"
```

---

### Task 7: roof_recon.py part 1, lines, eaves, brackets

The script's first half: load and level both clouds, segment, derive every contact-validated intersection line with per-end sensitivity, derive every eave twice (tight and loose), print the line table and the bracket table. Candidates and ranking come in Task 8.

**Files:**
- Create: `scripts/roof_recon.py`

**Interfaces:**
- Consumes: `discover_facets` (Task 6), `eave_line, line_extent, line_pair_span, plane_intersection, azimuth_degrees, up_from_tilt` from `roofkit.measure`, `level_cloud` from `roofkit.segment`, `load_xyz_rgb` from `roofkit.io`, `crop_box` from `roofkit.crop`, `load_config` from `dataset_config`, `median_nn_spacing` from `roofkit.stats`.
- Produces: module-level functions `intersection_lines(facets, contact_dist, spacing)` and `bracket_eaves(facets, raw_points, band, spacing)` that Task 8's `main` additions and Task 9's preregister.py import. Their exact return shapes are defined in the code below.

- [ ] **Step 1: Write the script**

Create `scripts/roof_recon.py`:

```python
# Roof-derived scale reconnaissance BEFORE the tape (2026-07-14): walls
# have no coverage on big_house, so the scale span comes from the roof,
# a logged EXCEPTION for this dataset. Same recon-before-tape principle
# as wall_recon.py: derive every candidate span from fitted geometry,
# rank by predicted error, and only then choose where the tape goes.
#
#   python scripts/roof_recon.py C:\odm\datasets\big_house [--no-view]
#
# Bias and noise are NEVER folded together (decision 2026-07-14):
# split-half repeatability cannot see edge erosion, because both halves
# are eroded identically. Eave positions therefore carry a two-cloud
# bracket: tight (filtered roof points, lower bound) vs loose (raw crop
# gated only by distance to the plane plus an in-plane window, upper
# bound). Output is lower/upper/delta, never an average.
import argparse
import numpy as np
import open3d as o3d
from dataset_config import load_config
from recon_common import discover_facets
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box
from roofkit.stats import median_nn_spacing
from roofkit.segment import level_cloud, fit_plane_trimmed
from roofkit.measure import (plane_intersection, azimuth_degrees,
                             up_from_tilt, eave_line, line_extent,
                             line_pair_span)

MIN_CONTACT = 200        # points per side to validate a line (sample size)
RIDGE_FRAC = 0.8         # contact-height fraction: >= on BOTH sides = ridge
VALLEY_FRAC = 0.2        # <= on both sides = valley (unitless, scale-free)
MIN_EDGE_SUPPORT = 50    # points in an eave's supporting bin (sample size)
PAIR_TOL_DEG = 2.0       # lines within this angle count as parallel; an
                         # angle, scale-free (spec: divergence reported)
PLANE_TOL_DEG = 2.0      # facet planes within this angle are parallel
MIN_SPAN = 2.0           # cu; shorter spans dilute nothing (scale-DEPENDENT)
SEP_MIN, SEP_MAX = 0.3, 30.0  # cu; plausible plane-pair window (scale-DEP.)
LOOSE_MARGIN_DOWN = 30.0 # x spacing past the tight eave the loose window
                         # extends downslope (readmits the eroded strip)
LOOSE_MARGIN_ALONG = 10.0  # x spacing beyond the tight along-eave extent
EAVE_FLAG_CU = 0.4       # cu; a bracket wider than this is loose-set
                         # CONTAMINATION, not erosion (scale-DEPENDENT:
                         # real overhang+fascia geometry is ~0.1-0.3 m and
                         # 1 cu ~ 1 m within GPS scale error; flag only)
TAPE_ERR = 0.01          # m; tape accuracy. RANKING term only: treats
                         # 1 cu ~ 1 m exactly as wall_recon.py documents


def contact_points(facet, p0, d, radius):
    """A facet's points within radius of a line (the ridge_line contact
    idea, kept here because the recon needs the points themselves)."""
    rel = facet["points"] - p0
    along = rel @ d
    radial = np.linalg.norm(rel - np.outer(along, d), axis=1)
    return facet["points"][radial <= radius]


def intersection_lines(facets, contact_dist, spacing):
    """Every contact-validated plane-plane intersection line: ridges,
    valleys, junctions. Direction re-measured from the contact points
    (real geometry at the line, not extrapolated fits). Each line
    carries per-end extent sensitivity: the extent re-read with the
    contact radius halved and doubled, because the ENDS live in the
    eroded zone and must wear their uncertainty visibly."""
    lines = []
    for i in range(len(facets)):
        for j in range(i + 1, len(facets)):
            fi, fj = facets[i], facets[j]
            inter = plane_intersection(fi["normal"], fi["points"].mean(axis=0),
                                       fj["normal"], fj["points"].mean(axis=0))
            if inter is None:
                continue
            p0, d = inter
            touch, fracs = [], []
            for f in (fi, fj):
                t = contact_points(f, p0, d, contact_dist)
                if len(t) < MIN_CONTACT:
                    touch = None
                    break
                lo, hi = np.percentile(f["points"][:, 2], [1.0, 99.0])
                fracs.append(float(np.clip(
                    (np.median(t[:, 2]) - lo) / max(hi - lo, 1e-12), 0, 1)))
                touch.append(t)
            if touch is None:
                continue
            contact = np.vstack(touch)
            _, _, vt = np.linalg.svd(contact - contact.mean(axis=0),
                                     full_matrices=False)
            v = vt[0]
            if v @ d < 0:
                v = -v
            v = v / np.linalg.norm(v)
            c0 = contact.mean(axis=0)
            ext = line_extent(contact, c0, v, spacing)
            # per-end sensitivity: how far each end moves when the
            # contact radius changes 2x either way (bias bound, cu)
            end_bias = [0.0, 0.0]
            for mult in (0.5, 2.0):
                alt = np.vstack([contact_points(f, p0, d, mult * contact_dist)
                                 for f in (fi, fj)])
                if len(alt) < 2 * MIN_CONTACT:
                    continue
                e2 = line_extent(alt, c0, v, spacing)
                end_bias[0] = max(end_bias[0], abs(e2["t_lo"] - ext["t_lo"]))
                end_bias[1] = max(end_bias[1], abs(e2["t_hi"] - ext["t_hi"]))
            kind = ("ridge" if min(fracs) >= RIDGE_FRAC else
                    "valley" if max(fracs) <= VALLEY_FRAC else "junction")
            az = float(np.degrees(np.arctan2(v[0], v[1])) % 360.0)
            if az >= 180.0:
                az -= 180.0
            lines.append({"i": i, "j": j, "kind": kind, "p0": c0, "d": v,
                          "azimuth_deg": az, "fracs": fracs,
                          "n_contact": len(contact), "extent": ext,
                          "end_bias": end_bias, "contacts": contact})
    return lines


def loose_set(raw_points, facet, tight_eave, band, spacing):
    """The loose point set for one facet's bracket: raw cropped points
    gated by (a) perpendicular distance to the TIGHT-fit plane and (b)
    an in-plane window around the tight facet, extended downslope past
    the tight eave. Gate (b) exists because an extended roof plane
    eventually slices terrain and canopy; without it the loose set is
    unbounded contamination (spec: in-plane region gate)."""
    n = facet["normal"] / np.linalg.norm(facet["normal"])
    c = facet["points"].mean(axis=0)
    d_perp = np.abs((raw_points - c) @ n)
    near = raw_points[d_perp <= band]
    d, w = tight_eave["d"], tight_eave["w"]
    a = (near - c) @ d
    t = (near - c) @ w
    a_t = (facet["points"] - c) @ d
    t_t = (facet["points"] - c) @ w
    keep = ((a >= a_t.min() - LOOSE_MARGIN_ALONG * spacing) &
            (a <= a_t.max() + LOOSE_MARGIN_ALONG * spacing) &
            (t >= t_t.min()) &
            (t <= tight_eave["t_edge"] + LOOSE_MARGIN_DOWN * spacing))
    return near[keep]


def bracket_eaves(facets, raw_points, band, spacing):
    """Each facet's eave, twice: tight (lower bound) and loose (upper).
    The plane and the coordinate origin ALWAYS come from the tight set,
    so the two t_edge values share one axis and their difference is the
    bracket delta. Split-half repeatability of the tight reading rides
    along so the table shows noise and bias side by side."""
    brackets = []
    for k, f in enumerate(facets):
        c = f["points"].mean(axis=0)
        tight = eave_line(f["points"], f["normal"], spacing, origin=c)
        if tight is None or tight["n_edge"] < MIN_EDGE_SUPPORT:
            brackets.append(None)
            continue
        loose_pts = loose_set(raw_points, f, tight, band, spacing)
        loose = eave_line(loose_pts, f["normal"], spacing, origin=c)
        halves = []
        for off in (0, 1):
            half_pts = f["points"][off::2]
            normal, keep = fit_plane_trimmed(half_pts, trim_mult=3.0)
            h = eave_line(half_pts[keep], normal, spacing, origin=c)
            if h is not None:
                halves.append(h["t_edge"])
        rep = abs(halves[0] - halves[1]) if len(halves) == 2 else None
        delta = (loose["t_edge"] - tight["t_edge"]) if loose else None
        flagged = delta is not None and delta > EAVE_FLAG_CU
        brackets.append({"facet": k, "tight": tight, "loose": loose,
                         "rep": rep, "delta": delta, "flagged": flagged,
                         "n_loose": len(loose_pts)})
    return brackets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="dataset directory (holds roofkit.json)")
    ap.add_argument("--no-view", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.dataset)

    roof = np.load(cfg["roof_path"])
    raw, _ = load_xyz_rgb(cfg["cloud_path"])
    if cfg["crop_min"] is None or cfg["crop_max"] is None:
        raise SystemExit("set crop_min/crop_max in roofkit.json first")
    raw, _ = crop_box(raw, cfg["crop_min"], cfg["crop_max"])
    if cfg["level_tilt_deg"] is None:
        raise SystemExit("no measured tilt in roofkit.json; run measure_roof "
                         "first, the recon needs the leveled frame")
    up = up_from_tilt(cfg["level_tilt_deg"], cfg["level_uphill_az_deg"])
    roof = level_cloud(roof, up)
    raw = level_cloud(raw, up)
    print(f"leveled both clouds by {cfg['level_tilt_deg']} deg, uphill az "
          f"{cfg['level_uphill_az_deg']} (roofkit.json)")
    origin = roof.min(axis=0)  # for relative dx/dy/z printouts

    facets, band, s = discover_facets(roof, cfg)
    print(f"{len(roof):,} roof points, {len(raw):,} raw crop points, "
          f"spacing {s:.4f} cu, band {band:.4f} cu, {len(facets)} facets")
    print(f"\n{'facet':>5} {'points':>10} {'pitch':>7} {'azimuth':>8}")
    for k, f in enumerate(facets):
        print(f"{k:>5} {len(f['points']):>10,} {f['pitch']:>7.2f} "
              f"{azimuth_degrees(f['normal']):>8.1f}")

    contact_dist = cfg["ridge_contact_mult"] * s
    lines = intersection_lines(facets, contact_dist, s)
    print(f"\n{len(lines)} contact-validated intersection lines "
          f"(contact {contact_dist:.4f} cu, min {MIN_CONTACT}/side):")
    print(f"{'facets':>7} {'kind':>9} {'az':>7} {'length cu':>10} "
          f"{'end bias cu':>12} {'contacts':>9} {'fracs':>11}")
    for L in lines:
        print(f"{L['i']:>3},{L['j']:>3} {L['kind']:>9} "
              f"{L['azimuth_deg']:>7.1f} {L['extent']['length']:>10.3f} "
              f"{L['end_bias'][0]:>5.3f}/{L['end_bias'][1]:<5.3f} "
              f"{L['n_contact']:>9,} "
              f"{L['fracs'][0]:>5.2f}/{L['fracs'][1]:<5.2f}")

    brackets = bracket_eaves(facets, raw, band, s)
    print(f"\neave brackets (tight=filtered lower bound, loose=raw-crop "
          f"upper bound, delta=loose-tight; NEVER averaged):")
    print(f"{'facet':>5} {'az':>7} {'rep cu':>8} {'delta cu':>9} "
          f"{'loose pts':>10}  note")
    for b in brackets:
        if b is None:
            continue
        note = ("CONTAMINATED loose set (bracket wider than "
                f"{EAVE_FLAG_CU} cu): excluded from scale candidates"
                if b["flagged"] else "ok")
        rep = f"{b['rep']:.4f}" if b["rep"] is not None else "n/a"
        delta = f"{b['delta']:.3f}" if b["delta"] is not None else "n/a"
        print(f"{b['facet']:>5} {b['tight']['azimuth_deg']:>7.1f} {rep:>8} "
              f"{delta:>9} {b['n_loose']:>10,}  {note}")
    print("note: tight, loose, and a physical tape can be three different "
          "edges (shingle overhang, fascia, wall line); a bracket gap may "
          "be geometry, not erosion. Field notes must record which edge "
          "the tape hooked.")
    return


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Sanity-run the tests and the script**

Run: `python -m pytest -q` then `python scripts/roof_recon.py C:\odm\datasets\big_house --no-view`
Expected: tests all PASS. Script prints the facet table (8 facets expected), an intersection-line table including the three known ridges (azimuths near 88.6 / 112.6 / 178.5), and a bracket row per facet. If the loose sets are enormous or every bracket is flagged, inspect before proceeding: that is data speaking, not necessarily a bug. Report what the tables say either way.

- [ ] **Step 3: Commit**

```bash
git add scripts/roof_recon.py
git commit -m "feat: roof_recon part 1, intersection lines and two-cloud eave brackets"
```

---

### Task 8: roof_recon.py part 2, candidates, ranking, viewer

**Files:**
- Modify: `scripts/roof_recon.py`

**Interfaces:**
- Consumes: everything from Task 7 plus `line_pair_span`.
- Produces: `enumerate_candidates(facets, lines, brackets, spacing) -> list of dicts` (keys: `cand_id, kind, span, rep, bias, noise_pct, bias_pct, lin_pct, area_pct, where, tape_plan, dz`), and a `rank_and_print(candidates)` function. Task 9 imports `enumerate_candidates`. `cand_id` is a stable human-readable string (seed-pinned segmentation makes indices reproducible), e.g. `lines:e3-r0,2` or `planes:1|4` or `length:r0,2`.

- [ ] **Step 1: Add the candidate machinery**

Insert into `scripts/roof_recon.py` after `bracket_eaves` (before `main`):

```python
def _split_half_line_span(fa, fb, facet_e, contact_dist, spacing):
    """Split-half repeatability of a ridge-to-eave span: the FULL
    derivation (plane fits, intersection, eave) re-run on even/odd
    halves, so the number is the instrument's noise, not a shortcut's."""
    spans = []
    for off in (0, 1):
        pa, pb = fa["points"][off::2], fb["points"][off::2]
        na, ka = fit_plane_trimmed(pa, trim_mult=3.0)
        nb, kb = fit_plane_trimmed(pb, trim_mult=3.0)
        inter = plane_intersection(na, pa[ka].mean(axis=0),
                                   nb, pb[kb].mean(axis=0))
        if inter is None:
            return None
        p0, d = inter
        pe = facet_e["points"][off::2]
        ne, ke = fit_plane_trimmed(pe, trim_mult=3.0)
        e = eave_line(pe[ke], ne, spacing,
                      origin=facet_e["points"].mean(axis=0))
        if e is None:
            return None
        r = line_pair_span(p0, d, e["p0"], e["d"], -1.0, 1.0)
        spans.append(r["span"])
    return abs(spans[0] - spans[1])


def _where(p, origin):
    r = p - origin
    return f"dx={r[0]:.1f} dy={r[1]:.1f} z={r[2]:.1f}"


def _overlap_window(line_a, pts_b, p0a, da):
    """Evaluation window along line A: the overlap of A's supported
    extent and B's support projected onto A. The span gets read where
    BOTH lines actually have data under them."""
    ta = line_a
    tb = (pts_b - p0a) @ da
    lo = max(ta["t_lo"], float(tb.min()))
    hi = min(ta["t_hi"], float(tb.max()))
    return (lo, hi) if hi > lo else None


def enumerate_candidates(facets, lines, brackets, spacing, origin):
    cands = []
    # class 1: parallel facet-plane separations (interior fits, no edges)
    for i in range(len(facets)):
        for j in range(i + 1, len(facets)):
            ni = facets[i]["normal"] / np.linalg.norm(facets[i]["normal"])
            nj = facets[j]["normal"] / np.linalg.norm(facets[j]["normal"])
            if ni[2] < 0:
                ni = -ni
            if nj[2] < 0:
                nj = -nj
            ang = np.degrees(np.arccos(np.clip(ni @ nj, -1.0, 1.0)))
            if ang > PLANE_TOL_DEG:
                continue
            ci = facets[i]["points"].mean(axis=0)
            sep_ij = np.abs((facets[j]["points"] - ci) @ ni).mean()
            cj = facets[j]["points"].mean(axis=0)
            sep_ji = np.abs((facets[i]["points"] - cj) @ nj).mean()
            sep = float((sep_ij + sep_ji) / 2.0)
            if not SEP_MIN <= sep <= SEP_MAX:
                continue
            halves = []
            for off in (0, 1):
                pi = facets[i]["points"][off::2]
                pj = facets[j]["points"][off::2]
                n1, k1 = fit_plane_trimmed(pi, trim_mult=3.0)
                if n1[2] < 0:
                    n1 = -n1
                halves.append(float(np.abs((pj - pi[k1].mean(axis=0)) @ n1)
                                    .mean()))
            cands.append({
                "cand_id": f"planes:{i}|{j}", "kind": "plane pair",
                "span": sep, "rep": abs(halves[0] - halves[1]), "bias": 0.0,
                "where": _where((ci + cj) / 2.0, origin), "dz": None,
                "tape_plan": "perpendicular offset between two parallel "
                             "roof planes; tapeable only if a step or "
                             "junction physically joins them, judge on "
                             "site"})
    # class 2: parallel derived-line pairs. Pool intersection lines and
    # unflagged eaves; every pair within PAIR_TOL_DEG is a candidate.
    pool = []
    for L in lines:
        pool.append({"tag": f"{L['kind'][0]}{L['i']},{L['j']}", "p0": L["p0"],
                     "d": L["d"], "sup": L["contacts"], "ext": L["extent"],
                     "bias": 0.0, "eave": False, "line": L})
    for b in brackets:
        if b is None or b["flagged"] or b["delta"] is None:
            continue
        f = facets[b["facet"]]
        t = (f["points"] - f["points"].mean(axis=0)) @ b["tight"]["d"]
        ext = {"t_lo": float(t.min()), "t_hi": float(t.max())}
        pool.append({"tag": f"e{b['facet']}", "p0": b["tight"]["p0"],
                     "d": b["tight"]["d"], "sup": f["points"], "ext": ext,
                     "bias": b["delta"], "eave": True,
                     "facet": b["facet"], "rep_e": b["rep"]})
    for a in range(len(pool)):
        for c in range(a + 1, len(pool)):
            A, B = pool[a], pool[c]
            fold = abs(A["d"] @ B["d"])
            ang = np.degrees(np.arccos(np.clip(fold, 0.0, 1.0)))
            if ang > PAIR_TOL_DEG:
                continue
            # extent window of A, intersected with B's support footprint
            win = _overlap_window(A["ext"], B["sup"], A["p0"], A["d"])
            r = line_pair_span(A["p0"], A["d"], B["p0"], B["d"],
                               *(win if win else (A["ext"]["t_lo"],
                                                  A["ext"]["t_hi"])))
            if r["span"] < MIN_SPAN:
                continue
            bias = A["bias"] + B["bias"]  # once per eave involved
            both_eave = A["eave"] and B["eave"]
            dz = abs(float(A["p0"][2] - B["p0"][2])) if both_eave else None
            reps = [x["rep_e"] for x in (A, B)
                    if x["eave"] and x.get("rep_e") is not None]
            rep = float(np.hypot(*reps)) if len(reps) == 2 else (
                reps[0] if reps else r["sens"])
            plan = ("ground: plumb drops from both drip edges, tape the "
                    "horizontal" if both_eave else
                    "on roof: hook the drip edge, run up the slope"
                    if A["eave"] or B["eave"] else
                    "on roof: between the two lines")
            cands.append({
                "cand_id": f"lines:{A['tag']}-{B['tag']}",
                "kind": "line pair", "span": float(r["span"]), "rep": rep,
                "bias": float(bias), "dz": dz,
                "where": _where((A["p0"] + B["p0"]) / 2.0, origin),
                "tape_plan": plan + f" (divergence {r['divergence_deg']:.2f} "
                                    f"deg, pos-sens {r['sens']:.3f} cu)"})
    # class 3: intersection-line lengths (fallback, endpoint bias visible)
    for L in lines:
        length = L["extent"]["length"]
        if length < MIN_SPAN:
            continue
        cands.append({
            "cand_id": f"length:{L['kind'][0]}{L['i']},{L['j']}",
            "kind": f"{L['kind']} length", "span": float(length),
            "rep": None, "bias": float(sum(L["end_bias"])), "dz": None,
            "where": _where(L["p0"], origin),
            "tape_plan": "on roof, along the line; BOTH ends are eroded "
                         "edge zone, bias is one-sided (reads short)"})
    return cands


def rank_and_print(cands):
    for e in cands:
        rep = e["rep"] if e["rep"] is not None else 0.0
        noise = float(np.hypot(rep, TAPE_ERR))
        e["noise_pct"] = 100.0 * noise / e["span"]
        e["bias_pct"] = 100.0 * e["bias"] / e["span"]
        e["lin_pct"] = e["noise_pct"] + e["bias_pct"]
        e["area_pct"] = 2.0 * e["lin_pct"]
    cands.sort(key=lambda e: e["lin_pct"])
    print(f"\ncandidate scale spans, ranked by predicted linear error "
          f"(noise and bias SHOWN SPLIT, tape term {TAPE_ERR} m):")
    print(f"{'rank':>4} {'id':>18} {'kind':>14} {'span cu':>8} "
          f"{'noise %':>8} {'bias %':>7} {'lin %':>6} {'area %':>7}  "
          f"where / tape plan")
    for r, e in enumerate(cands, 1):
        print(f"{r:>4} {e['cand_id']:>18} {e['kind']:>14} {e['span']:>8.3f} "
              f"{e['noise_pct']:>8.3f} {e['bias_pct']:>7.3f} "
              f"{e['lin_pct']:>6.2f} {e['area_pct']:>7.2f}  "
              f"{e['where']}; {e['tape_plan']}"
              + (f"; dz={e['dz']:.2f} cu" if e["dz"] is not None else ""))
    print("\nnotes: bias is a BOUND with known direction, not noise; a "
          "candidate with tiny noise and fat bias is not better than the "
          "reverse. Eave-based spans inherit the bracket delta once per "
          "eave. Physical access is Emmett's judgment, from the where "
          "column, not the script's.")
```

Then in `main`, replace the final `return` with:

```python
    cands = enumerate_candidates(facets, lines, brackets, s, origin)
    if not cands:
        print("\nNO candidate span survived. The honest outcome per the "
              "spec: report it, do not paper over it.")
        return
    rank_and_print(cands)

    if not args.no_view:
        geoms = []
        view = roof
        rng = np.random.default_rng(0)
        if len(view) > 1_500_000:
            view = view[rng.choice(len(view), 1_500_000, replace=False)]
        pc = o3d.geometry.PointCloud()
        pc.points = o3d.utility.Vector3dVector(view)
        pc.paint_uniform_color((0.45, 0.45, 0.45))
        geoms.append(pc)
        for L in lines:  # intersection lines in red
            seg = o3d.geometry.LineSet()
            a = L["p0"] + L["extent"]["t_lo"] * L["d"]
            b = L["p0"] + L["extent"]["t_hi"] * L["d"]
            seg.points = o3d.utility.Vector3dVector([a, b])
            seg.lines = o3d.utility.Vector2iVector([[0, 1]])
            seg.paint_uniform_color((1.0, 0.0, 0.0))
            geoms.append(seg)
        for b in brackets:  # tight eaves green, loose eaves yellow
            if b is None:
                continue
            f = facets[b["facet"]]
            c = f["points"].mean(axis=0)
            t = (f["points"] - c) @ b["tight"]["d"]
            for key, col in (("tight", (0.0, 0.8, 0.2)),
                             ("loose", (0.95, 0.85, 0.1))):
                e = b[key]
                if e is None:
                    continue
                seg = o3d.geometry.LineSet()
                seg.points = o3d.utility.Vector3dVector(
                    [e["p0"] + t.min() * e["d"], e["p0"] + t.max() * e["d"]])
                seg.lines = o3d.utility.Vector2iVector([[0, 1]])
                seg.paint_uniform_color(col)
                geoms.append(seg)
        print("\nviewer: intersection lines red, tight eaves green, loose "
              "eaves yellow. A wide green-to-yellow gap IS the bracket. "
              "Q closes.")
        o3d.visualization.draw_geometries(
            geoms, window_name="roof recon: derived lines and brackets")
```

- [ ] **Step 2: Run everything**

Run: `python -m pytest -q` then `python scripts/roof_recon.py C:\odm\datasets\big_house --no-view`
Expected: tests PASS. Ranked candidate table prints. Verify against known geometry: ridge azimuths 88.6/112.6/178.5 imply NO ridge-ridge pair within 2 deg (the spec predicts this); ridge-to-eave and eave-to-eave pairs should appear for each gable; class 1 may be empty. If the table contradicts these expectations, investigate before committing and report what was found.

- [ ] **Step 3: Explanation gate (the big one)**

Walk Emmett through the whole candidate table with the viewer open: what each candidate is physically, where its noise number comes from, where its bias number comes from, why the ranking is noise+bias, and which candidates HE judges tapeable. This is the recon deliverable; he chooses the span. Invite questions throughout. Wait for his OK.

- [ ] **Step 4: Commit**

```bash
git add scripts/roof_recon.py
git commit -m "feat: roof_recon part 2, candidate enumeration, split ranking, viewer"
```

---

### Task 9: Pre-registration writer

**Files:**
- Create: `scripts/preregister.py`
- Create directory: `reports/` (first file creates it)

**Interfaces:**
- Consumes: `discover_facets` (Task 6), `intersection_lines, bracket_eaves, enumerate_candidates` (Tasks 7-8, import from `roof_recon`), `facet_area, azimuth_degrees` from `roofkit.measure`, config loading as in roof_recon.
- Produces: `reports/<dataset_name>/preregistered-YYYY-MM-DD.json`, committed by the HUMAN (the commit IS the pre-registration; the script never runs git).

- [ ] **Step 1: Write the script**

Create `scripts/preregister.py`:

```python
# Pre-registration writer (decision 2026-07-14): freeze the pipeline's
# cloud-unit outputs into a JSON in the repo BEFORE the field visit.
# The human commits it; that commit hash is the pre-registration. Roof
# measurements taken afterward score THIS file and never edit it. A
# retune is a NEW run of this script, a NEW file, a NEW commit; both
# get reported.
#
#   python scripts/preregister.py C:\odm\datasets\big_house --candidate lines:e3-r0,2
#
# The candidate id comes from roof_recon.py's ranked table (Emmett's
# choice of which span the tape measures). The report lands in the
# repo, a deliberate exception to "the repo holds only code": a frozen
# deliverable must live where the hash freezes it.
import argparse
import datetime
import json
import numpy as np
from pathlib import Path
from dataset_config import load_config
from recon_common import discover_facets
from roof_recon import intersection_lines, bracket_eaves, enumerate_candidates
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box
from roofkit.segment import level_cloud
from roofkit.measure import azimuth_degrees, facet_area, up_from_tilt

AREA_MAX_POINTS = 400_000  # same cap and reasoning as measure_roof.py


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--candidate", required=True,
                    help="cand_id of the chosen scale span, from roof_recon")
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    rng = np.random.default_rng(0)

    roof = np.load(cfg["roof_path"])
    raw, _ = load_xyz_rgb(cfg["cloud_path"])
    raw, _ = crop_box(raw, cfg["crop_min"], cfg["crop_max"])
    up = up_from_tilt(cfg["level_tilt_deg"], cfg["level_uphill_az_deg"])
    roof, raw = level_cloud(roof, up), level_cloud(raw, up)
    origin = roof.min(axis=0)

    facets, band, s = discover_facets(roof, cfg)
    lines = intersection_lines(facets, cfg["ridge_contact_mult"] * s, s)
    brackets = bracket_eaves(facets, raw, band, s)
    cands = enumerate_candidates(facets, lines, brackets, s, origin)
    chosen = [c for c in cands if c["cand_id"] == args.candidate]
    if not chosen:
        raise SystemExit(f"candidate {args.candidate!r} not found; ids: "
                         + ", ".join(c["cand_id"] for c in cands))

    facet_rows = []
    for k, f in enumerate(facets):
        pts = f["points"]
        if len(pts) > AREA_MAX_POINTS:
            pts = pts[rng.choice(len(pts), AREA_MAX_POINTS, replace=False)]
        from roofkit.stats import median_nn_spacing
        s_f = median_nn_spacing(pts)
        facet_rows.append({
            "facet": k, "points": int(len(f["points"])),
            "pitch_deg": round(float(f["pitch"]), 3),
            "azimuth_deg": round(azimuth_degrees(f["normal"]), 2),
            "area_cu2": round(facet_area(pts, f["normal"],
                                         alpha=cfg["alpha_mult"] * s_f), 3)})
    eave_rows = [
        {"facet": b["facet"], "rep_cu": b["rep"], "delta_cu": b["delta"],
         "flagged": b["flagged"]}
        for b in brackets if b is not None]
    report = {
        "protocol": "decision 2026-07-14: outputs frozen BEFORE field "
                    "visit; this file is never edited",
        "date": datetime.date.today().isoformat(),
        "dataset": Path(args.dataset).name,
        "config": {k: cfg[k] for k in
                   ("band_mult", "trim_mult", "min_points_frac", "max_planes",
                    "fit_sample", "alpha_mult", "ridge_contact_mult",
                    "level_tilt_deg", "level_uphill_az_deg")},
        "units": "cloud units (cu); one tape number converts, later",
        "facets": facet_rows,
        "eave_brackets": eave_rows,
        "total_area_cu2": round(sum(r["area_cu2"] for r in facet_rows), 3),
        "scale_candidate": chosen[0],
    }
    out_dir = Path(__file__).resolve().parents[1] / "reports" / report["dataset"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"preregistered-{report['date']}.json"
    if out.exists():
        raise SystemExit(f"{out} already exists; a retune is a NEW dated "
                         "file, and the old one is never overwritten")
    out.write_text(json.dumps(report, indent=2))
    print(f"wrote {out}")
    print("NOW COMMIT IT. The commit hash is the pre-registration. Only "
          "then does anyone climb the roof.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it end to end**

Run: `python -m pytest -q` then `python scripts/preregister.py C:\odm\datasets\big_house --candidate <top-ranked unflagged id from Task 8's run>`
Expected: tests PASS; JSON appears under `reports/big_house/`; totals match measure_roof's 7a numbers (total near 313.00 cu^2, 8 facets, pitches near 5:12 and 8:12 classes). A mismatch means recon_common diverged from measure_roof: STOP and reconcile before committing.

Do NOT commit the generated JSON as part of this task: the real pre-registration commit is Emmett's, made when he has chosen the candidate and is ready to go to the roof.

- [ ] **Step 3: Commit the script only**

```bash
git add scripts/preregister.py
git commit -m "feat: pre-registration writer; frozen cloud-unit outputs, human commits the hash"
```

---

### Task 10: Close out

**Files:**
- Modify: `DECISIONS.md` (Current state block ONLY; the log entries are already written)

- [ ] **Step 1: Full verification**

Run: `python -m pytest -q` (all green, 32 existing plus the new ones) and one final `python scripts/roof_recon.py C:\odm\datasets\big_house --no-view` with the output saved for Emmett.

- [ ] **Step 2: Update the Current state block in DECISIONS.md**

Overwrite (never the log below it): phase = recon built and run; blocker = Emmett judges tapeability from the ranked table, picks the candidate, runs preregister.py, commits, then the field visit; last verified = test count and the recon run; next action = tape the chosen span, put scale_span_cu and scale_true_m into roofkit.json, audit readings go in a new comparison file.

- [ ] **Step 3: Commit**

```bash
git add DECISIONS.md
git commit -m "Log: roof recon built; awaiting candidate choice and pre-registration"
```

---

## Plan self-review notes (already applied)

- Spec coverage: class 1/2/3 instruments (Tasks 7-8), bracket with region gate and flag (Tasks 3, 5, 7), error model split (Task 8), physical report (Task 8), viewer (Task 8), synthetic tests 1-5 from the spec (Tasks 2-5: truth bracketing, contamination flag, endpoint insensitivity, erosion shortening, split-half flattery), pre-registration (Task 9), scale-dependence documentation (constants blocks).
- The spec's "no candidate survives" honest outcome is handled in Task 8's main (explicit NO-candidate print).
- Known limitation to mention at the Task 8 gate: the density-edge estimator reads inboard on triangular (hip) facets whose width tapers; eave candidates on such facets will show it as a wider tight-vs-truth gap, which the bracket reports rather than hides.
