# DIAGNOSTIC D: is boundary contamination a POPULATION property of facets,
# or something peculiar to blob 0?
#
#   .venv/Scripts/python.exe -u scripts/probe_boundary_erosion.py C:/odm/datasets/big_house
#
# Writes (standing rule R2):
#   reports/big_house/boundary-erosion-population-<date>.json
#   reports/big_house/boundary-erosion-population-<date>.png
#   reports/big_house/boundary-erosion-sweep-<date>.png
#
# SIDE ARTIFACT ONLY. Nothing adopted, no threshold changed, no erosion applied
# anywhere. canonical-2026-07-26-r2 remains canonical; published coverage
# remains 88.40 percent.
#
# ---------------------------------------------------------------------------
# WHY THIS PROBE EXISTS
#
# Blob 0's residual is flat across its interior and steps down sharply in the
# last ~20 inches at the edge where it abuts the main roof above it. On its own
# that is one observation on one patch, and an erosion width derived from it
# would be a threshold picked by looking at the answer.
#
# NOTHING HERE IS DERIVED FROM BLOB 0. The same depth-from-boundary profile is
# measured on all 8 main facets and all 21 recovered facets, from the canonical
# state, and blob 0 is only then placed against that population.
#
# THE PHYSICAL MECHANISM, and why it is testable rather than a story.
# Dense stereo matching estimates depth by matching image patches. At a DEPTH
# DISCONTINUITY the patch straddles two surfaces at different distances, and the
# estimate lands between them. The result is a skirt of points pulled off the
# true surface, confined to a band whose width is set by the matching window,
# not by the roof. So the effect should be STRONGEST at boundaries where a
# taller surface stands over this one, WEAKER at a free eave edge (where the
# other side is distant ground rather than a nearby surface), and WEAKEST at a
# ridge or hip, where two surfaces meet with no step at all. That ordering is a
# prediction the data can refute, which is what makes it evidence rather than a
# narrative fitted afterwards.
#
# WHAT IS DELIBERATELY NOT DONE HERE
# No erosion is applied. The sweep at the end reports what the bar WOULD become
# and what blob 0 WOULD score, as a pair, at every width. Emmett's condition:
# both numbers must move, and the outcome must not be predictable in advance,
# or the fix is just the answer written backwards.
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.ndimage import (binary_dilation, binary_erosion, binary_fill_holes,
                           distance_transform_edt)

sys.path.insert(0, str(Path(__file__).parent))
from dataset_config import load_config                            # noqa: E402
from canonical import load_canonical, scalar, leveled_points      # noqa: E402
from recon_common import discover_facets                          # noqa: E402
from roofkit.stats import median_nn_spacing                       # noqa: E402
from roofkit.measure import facet_area, tilt_degrees              # noqa: E402
from roofkit import coverage as cov                               # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"
COVERAGE_CELL_MULT = 2.5
MIN_BLOB_AREA = 0.15
MIN_AREA_POINTS_EQUIV = 3704
MAIN_MIN_PITCH = 5.0
RECOVERY_MIN_PITCH_DIAG = 1.0
NEAR_CELLS = 3          # how far to look for a neighbouring facet, in cells
STEP_MULT = 10.0        # a height difference above STEP_MULT x spacing counts
                        # as a STEP rather than a junction. Expressed in
                        # spacing so it transfers between clouds.
STABILISE_TOL = 1.05    # "stabilised" = within 5 percent of the deep asymptote


class Patch:
    """One facet's plan footprint, held on a small sub-grid rather than the
    full building grid. 29 facets x a 7-million-cell grid would be 200 MB per
    copy; each facet only covers a small box of it."""

    def __init__(self, cells_ij, shape):
        i, j = cells_ij[:, 0], cells_ij[:, 1]
        self.i0, self.i1 = int(i.min()), int(i.max()) + 1
        self.j0, self.j1 = int(j.min()), int(j.max()) + 1
        occ = np.zeros((self.i1 - self.i0 + 2, self.j1 - self.j0 + 2), bool)
        occ[i - self.i0 + 1, j - self.j0 + 1] = True
        # Fill enclosed holes BEFORE anything else, for the same reason the
        # footprint denominator does: a cell surrounded by facet is facet, and
        # eroding a hole-riddled mask measures capture density instead of the
        # facet's edge (decision 2026-07-26).
        self.occ_raw = occ
        self.occ = binary_fill_holes(occ)
        self.dil = binary_dilation(self.occ, iterations=NEAR_CELLS)
        self.boundary = self.occ & ~binary_erosion(self.occ, iterations=1)

    def local(self, i, j):
        """Global cell indices -> indices into this patch's sub-grid, plus a
        mask of which ones actually land inside the box."""
        li, lj = i - self.i0 + 1, j - self.j0 + 1
        inside = ((li >= 0) & (li < self.occ.shape[0]) &
                  (lj >= 0) & (lj < self.occ.shape[1]))
        return np.clip(li, 0, self.occ.shape[0] - 1), \
            np.clip(lj, 0, self.occ.shape[1] - 1), inside

    def near(self, i, j):
        li, lj, inside = self.local(i, j)
        return self.dil[li, lj] & inside

    def centers(self, cells, g):
        return np.column_stack([g["xlo"] + (cells[:, 0] + 0.5) * g["cell"],
                                g["ylo"] + (cells[:, 1] + 0.5) * g["cell"]])


def plane_z(xy, normal, centroid):
    n = np.asarray(normal, float); n = n / np.linalg.norm(n)
    c = np.asarray(centroid, float)
    return c[2] - (n[0] * (xy[:, 0] - c[0]) + n[1] * (xy[:, 1] - c[1])) / n[2]


def up_normal(n):
    """Normal oriented so +z is up, making 'negative residual' mean 'below the
    surface' for every facet regardless of which way RANSAC pointed it."""
    n = np.asarray(n, float) / np.linalg.norm(n)
    return n if n[2] >= 0 else -n


def profile(depth, resid, edges):
    rows = []
    w = np.clip(np.digitize(depth, edges) - 1, 0, len(edges) - 2)
    for k in range(len(edges) - 1):
        m = w == k
        if m.sum() < 30:
            continue
        rows.append(dict(depth_lo=float(edges[k]), depth_hi=float(edges[k + 1]),
                         n=int(m.sum()),
                         mean_signed=float(resid[m].mean()),
                         mean_abs=float(np.abs(resid[m]).mean())))
    return rows


def stabilisation_depth(rows, depth, resid):
    """Shallowest depth beyond which mean |residual| stays within
    STABILISE_TOL of its deep asymptote. The asymptote is taken over the
    deepest quarter of the points, so it is a property of the facet's interior
    rather than of any chosen width."""
    if len(rows) < 3:
        return None
    deep = depth > np.percentile(depth, 75)
    if deep.sum() < 50:
        return None
    asym = float(np.abs(resid[deep]).mean())
    ok = [r["mean_abs"] <= STABILISE_TOL * asym for r in rows]
    for k in range(len(rows)):
        if all(ok[k:]):
            return dict(depth=float(rows[k]["depth_lo"]), asymptote=asym,
                        bin_index=k)
    return dict(depth=float(rows[-1]["depth_lo"]), asymptote=asym,
                bin_index=len(rows) - 1, note="never stabilised within the "
                                              "profiled range")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    args = ap.parse_args()
    cfg = load_config(args.dataset)
    name = Path(args.dataset).name
    out = REPO / "reports" / name
    checks = []

    # --- the canonical 29, read from disk, NOT re-fitted --------------------
    # A diagnostic that re-fits describes its own fit, not the state under
    # discussion. load_canonical re-hashes the cloud before indexing into it.
    doc, points, facets, cfg = load_canonical(args.dataset, CANONICAL_STAMP)
    spacing = scalar(doc, "spacing_cu")
    band = scalar(doc, "band_cu")
    cell = scalar(doc, "cell_cu")
    bar_canon = scalar(doc, "quality_bar")
    in_per_cu = 40.4541
    sc = out / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])
    n_main = doc["counts"]["n_main"]
    print(f"  loaded {len(facets)} canonical facets ({n_main} main), "
          f"spacing {spacing:.6f} cu, bar {bar_canon!r}")

    # --- blob 0's rejected candidate, from a reproducible pipeline run ------
    # Needed because blob 0 is NOT in the canonical state: it was rejected.
    # Cross-checked bit for bit against quality-bar-tie so the plane analysed
    # here is provably the plane that was rejected.
    s_full_chk = median_nn_spacing(points)
    _, band_r, s_full = discover_facets(points, cfg, probability=1.0,
                                        spacing=s_full_chk, min_pitch=10.0)
    main_r, band_r, s_full = discover_facets(points, cfg, probability=1.0,
                                             spacing=s_full_chk,
                                             min_pitch=MAIN_MIN_PITCH)
    bar_r, _ = cov.calibrate_quality_bar(main_r, s_full)
    masks, g, _, dist = cov.coverage_masks(points, main_r, band_r,
                                           COVERAGE_CELL_MULT * s_full)
    blobs = cov.residual_blobs(masks["residual"], g, MIN_BLOB_AREA)
    b0 = blobs[0]
    min_area = MIN_AREA_POINTS_EQUIV * s_full_chk ** 2
    dd = []
    for f in main_r:
        p_ = np.asarray(f["points"], float)
        s_ff = float(np.median(cov._nn(p_)))
        dd.append(len(p_) * s_full_chk ** 2 /
                  max(float(facet_area(p_, f["normal"],
                                       cfg["alpha_mult"] * s_ff)), 1e-12))
    min_points = int(round(MIN_AREA_POINTS_EQUIV * float(np.median(dd))))
    captured = []
    _orig = cov.facet_quality

    def _spy(pts, normal, sp):
        q, n = _orig(pts, normal, sp)
        captured.append(dict(n=len(pts), q=float(q), points=pts,
                             normal=np.asarray(n, float).copy()))
        return q, n

    cov.facet_quality = _spy
    try:
        rlog = []
        cov.recover_facets(points, [b0], None, dist, band_r, s_full, bar_r,
                           alpha_mult=cfg["alpha_mult"], probability=1.0,
                           min_pitch=RECOVERY_MIN_PITCH_DIAG,
                           min_points_hard=min_points, min_area_hard=min_area,
                           log=rlog, grid=g)
    finally:
        cov.facet_quality = _orig
    logged = rlog[0]["planes"][0]
    shot = next(c for c in captured if c["n"] == logged["n"])
    tie = json.loads((out / f"quality-bar-tie-{args.stamp}.json").read_text())
    b0_n = up_normal(shot["normal"])
    checks.append(dict(
        check="blob 0's plane is the one recover_facets rejected",
        passed=bool(shot["n"] == 162938 and
                    [float(v).hex() for v in
                     (shot["normal"] / np.linalg.norm(shot["normal"]))] ==
                    tie["candidate"]["normal_hex"]),
        n_points=int(shot["n"]), quality=repr(float(shot["q"]))))
    checks.append(dict(
        check="the recomputed bar matches the canonical bar bit for bit",
        passed=bool(float(bar_r).hex() == float(bar_canon).hex()),
        recomputed=repr(float(bar_r)), canonical=repr(float(bar_canon))))

    # --- assemble the population: 29 canonical facets + blob 0 -------------
    ny1 = np.int64(g["ny"] + 1)

    def cells_of(pts):
        i = np.clip(((pts[:, 0] - g["xlo"]) / g["cell"]).astype(np.int64),
                    0, g["nx"] - 1)
        j = np.clip(((pts[:, 1] - g["ylo"]) / g["cell"]).astype(np.int64),
                    0, g["ny"] - 1)
        return i, j

    pop = []
    for f in facets:
        pop.append(dict(id=f"facet_{f['facet']}", kind=f["kind"],
                        points=np.asarray(f["points"], float),
                        normal=up_normal(f["normal"]),
                        pitch=float(f["pitch"])))
    pop.append(dict(id="blob_0", kind="REJECTED candidate (not in canonical)",
                    points=np.asarray(shot["points"], float),
                    normal=b0_n, pitch=float(tilt_degrees(b0_n))))

    for e in pop:
        i, j = cells_of(e["points"])
        e["ci"], e["cj"] = i, j
        e["patch"] = Patch(np.column_stack([i, j]), (g["nx"], g["ny"]))
        e["centroid"] = e["points"].mean(axis=0)

    # --- boundary type classification --------------------------------------
    # For every boundary cell of every entity, look for another entity within
    # NEAR_CELLS and compare plane heights there.
    step = STEP_MULT * spacing
    for k, e in enumerate(pop):
        P = e["patch"]
        bcells = np.argwhere(P.boundary)
        gi = bcells[:, 0] + P.i0 - 1
        gj = bcells[:, 1] + P.j0 - 1
        ctr = np.column_stack([g["xlo"] + (gi + 0.5) * g["cell"],
                               g["ylo"] + (gj + 0.5) * g["cell"]])
        zk = plane_z(ctr, e["normal"], e["centroid"])
        best_up = np.full(len(gi), -np.inf)
        any_near = np.zeros(len(gi), bool)
        for m, o in enumerate(pop):
            if m == k:
                continue
            near = o["patch"].near(gi, gj)
            if not near.any():
                continue
            zo = plane_z(ctr, o["normal"], o["centroid"])
            dz = zo - zk
            any_near |= near
            best_up = np.where(near & (dz > best_up), dz, best_up)
        # FREE = nothing else nearby. STEP_UP = something stands above this
        # facet here (the occlusion case). JUNCTION = a neighbour at
        # essentially the same height: a ridge, hip or valley.
        t = np.full(len(gi), 0, np.int8)          # 0 free, 1 junction, 2 step
        t[any_near] = 1
        t[any_near & (best_up > step)] = 2
        e["btype"] = t
        e["bcells"] = (gi, gj)
        e["blocal"] = bcells

    TYPES = {0: "free_edge", 1: "junction_no_step", 2: "abuts_taller_surface"}

    # --- per-entity depth profile ------------------------------------------
    edges_sp = np.array([0, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 1e9])
    rows_out = []
    pooled = {v: dict(d=[], r=[]) for v in TYPES.values()}
    for e in pop:
        P = e["patch"]
        depth_grid = distance_transform_edt(P.occ)
        li, lj, _ = P.local(e["ci"], e["cj"])
        depth_cells = depth_grid[li, lj]
        depth = depth_cells * g["cell"] / spacing        # in POINT SPACINGS
        n_hat = e["normal"]
        r = (e["points"] - e["centroid"]) @ n_hat
        rr = r / spacing                                  # spacings, transferable

        # distance to the nearest boundary cell OF EACH TYPE, so each point can
        # be attributed to the boundary that governs it
        gov = np.full(len(rr), -1, np.int8)
        best = np.full(len(rr), np.inf)
        per_type_counts = {}
        for tv, tname in TYPES.items():
            seed = np.zeros_like(P.occ)
            sel = e["btype"] == tv
            per_type_counts[tname] = int(sel.sum())
            if not sel.any():
                continue
            bl = e["blocal"][sel]
            seed[bl[:, 0], bl[:, 1]] = True
            dt = distance_transform_edt(~seed)[li, lj] * g["cell"] / spacing
            better = dt < best
            best[better] = dt[better]
            gov[better] = tv

        rws = profile(depth, rr, edges_sp)
        st = stabilisation_depth(rws, depth, rr)
        shallow = [x for x in rws if x["depth_hi"] <= 4]
        by_type = {}
        for tv, tname in TYPES.items():
            m = gov == tv
            if m.sum() < 200:
                continue
            by_type[tname] = profile(best[m], rr[m], edges_sp)
            pooled[tname]["d"].append(best[m])
            pooled[tname]["r"].append(rr[m])

        rows_out.append(dict(
            id=e["id"], kind=e["kind"], n_points=int(len(rr)),
            pitch_deg=round(float(e["pitch"]), 3),
            boundary_cells_by_type=per_type_counts,
            profile_depth_in_spacings=rws,
            stabilisation=st,
            stabilisation_depth_spacings=(st["depth"] if st else None),
            stabilisation_depth_in=(round(st["depth"] * spacing * in_per_cu, 2)
                                    if st else None),
            shallowest_bin_mean_signed=(shallow[0]["mean_signed"]
                                        if shallow else None),
            sign_negative_at_boundary=bool(shallow and
                                           shallow[0]["mean_signed"] < 0),
            profile_by_boundary_type=by_type))
        print(f"  {e['id']:<12} n={len(rr):>9,}  stabilises at "
              f"{(st['depth'] if st else float('nan')):>5.1f} spacings"
              f"  boundary mean {shallow[0]['mean_signed'] if shallow else float('nan'):+.4f}")

    # --- pooled by boundary type: the physical prediction -------------------
    pooled_out = {}
    for tname, acc in pooled.items():
        if not acc["d"]:
            continue
        d = np.concatenate(acc["d"]); rv = np.concatenate(acc["r"])
        rws = profile(d, rv, edges_sp)
        shallow = [x for x in rws if x["depth_hi"] <= 4]
        deep = d > 16
        pooled_out[tname] = dict(
            n_points=int(len(d)), n_entities=len(acc["d"]),
            profile=rws,
            boundary_mean_signed_spacings=(shallow[0]["mean_signed"]
                                           if shallow else None),
            boundary_mean_signed_in=(
                round(shallow[0]["mean_signed"] * spacing * in_per_cu, 4)
                if shallow else None),
            interior_mean_signed_in=(
                round(float(rv[deep].mean()) * spacing * in_per_cu, 4)
                if deep.sum() > 200 else None),
            boundary_minus_interior_in=(
                round((shallow[0]["mean_signed"] - float(rv[deep].mean()))
                      * spacing * in_per_cu, 4)
                if shallow and deep.sum() > 200 else None))

    order = sorted((v.get("boundary_minus_interior_in") or 0.0, k)
                   for k, v in pooled_out.items())
    prediction = dict(
        predicted_ordering="abuts_taller_surface strongest (most negative), "
                           "then free_edge, then junction_no_step weakest",
        observed_ordering_most_negative_first=[k for _, k in order],
        boundary_minus_interior_in={k: v.get("boundary_minus_interior_in")
                                    for k, v in pooled_out.items()},
        prediction_held=bool(order and order[0][1] == "abuts_taller_surface"),
        why_this_matters="the ordering was predicted from the matching-window "
                         "mechanism BEFORE it was measured. If it holds it is "
                         "independent physical support; if it fails, the "
                         "boundary story is wrong however good blob 0's "
                         "profile looked.")

    # --- population: is there ONE erosion width? ---------------------------
    st_all = [r["stabilisation_depth_spacings"] for r in rows_out
              if r["stabilisation_depth_spacings"] is not None]
    st_main = [r["stabilisation_depth_spacings"] for r in rows_out
               if r["kind"] == "main" and
               r["stabilisation_depth_spacings"] is not None]
    population = dict(
        n_entities=len(rows_out),
        stabilisation_depth_spacings=dict(
            min=float(np.min(st_all)), p25=float(np.percentile(st_all, 25)),
            median=float(np.median(st_all)),
            p75=float(np.percentile(st_all, 75)), max=float(np.max(st_all)),
            values=sorted(float(x) for x in st_all)),
        stabilisation_depth_inches=dict(
            median=round(float(np.median(st_all)) * spacing * in_per_cu, 2),
            p25=round(float(np.percentile(st_all, 25)) * spacing * in_per_cu, 2),
            p75=round(float(np.percentile(st_all, 75)) * spacing * in_per_cu, 2)),
        main_facets_only_median_spacings=(float(np.median(st_main))
                                          if st_main else None),
        n_with_negative_boundary_bias=int(sum(
            1 for r in rows_out if r["sign_negative_at_boundary"])),
        reading="a single erosion width describes the population only if these "
                "cluster. A wide spread means the width is a per-facet "
                "property and a single global value would be a compromise "
                "chosen by its effect, not a measurement.")

    # --- the sweep: what BOTH numbers do ------------------------------------
    # For each erosion width w, every entity is eroded IDENTICALLY, the bar is
    # recomputed from the eroded main facets, and blob 0's eroded quality is
    # measured against it. Reported as a pair at every w. NOT APPLIED.
    widths = [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 40]
    ent = {e["id"]: e for e in pop}
    depth_cache = {}
    for e in pop:
        P = e["patch"]
        dg = distance_transform_edt(P.occ)
        li, lj, _ = P.local(e["ci"], e["cj"])
        depth_cache[e["id"]] = dg[li, lj] * g["cell"] / spacing

    sweep = []
    for w in widths:
        quals, kept = [], []
        ok = True
        for k in range(n_main):
            e = ent[f"facet_{k}"]
            m = depth_cache[e["id"]] > w
            if m.sum() < 1000:
                ok = False
                break
            q, _ = cov.facet_quality(e["points"][m], e["normal"], spacing)
            quals.append(float(q)); kept.append(int(m.sum()))
        if not ok:
            sweep.append(dict(width_spacings=w, aborted="a main facet eroded "
                                                        "below 1,000 points"))
            continue
        e0 = ent["blob_0"]
        m0 = depth_cache["blob_0"] > w
        q0, _ = cov.facet_quality(e0["points"][m0], e0["normal"], spacing)
        bar_w = float(max(quals))
        sweep.append(dict(
            width_spacings=w,
            width_in=round(w * spacing * in_per_cu, 3),
            bar=float(bar_w), bar_set_by_facet=int(np.argmax(quals)),
            main_qualities=[round(q, 5) for q in quals],
            main_points_kept=kept,
            main_points_kept_pct=[
                round(100.0 * kept[k] / len(ent[f'facet_{k}']['points']), 2)
                for k in range(n_main)],
            blob0_quality=float(q0),
            blob0_points_kept=int(m0.sum()),
            blob0_points_kept_pct=round(100.0 * m0.mean(), 2),
            blob0_margin=float(q0 - bar_w),
            blob0_would_pass=bool(q0 <= bar_w)))
        print(f"    w={w:>3} sp ({w*spacing*in_per_cu:>5.2f} in)  bar "
              f"{bar_w:.5f}  blob0 {q0:.5f}  margin {q0-bar_w:+.5f}  "
              f"pass={q0 <= bar_w}")

    valid = [s for s in sweep if "bar" in s]
    flips = [s["width_spacings"] for s in valid if s["blob0_would_pass"]]
    sweep_summary = dict(
        widths_where_blob0_passes=flips,
        first_pass_width_spacings=(min(flips) if flips else None),
        first_pass_width_in=(round(min(flips) * spacing * in_per_cu, 2)
                             if flips else None),
        bar_at_w0=valid[0]["bar"] if valid else None,
        bar_at_max_w=valid[-1]["bar"] if valid else None,
        bar_moved_by=(round(valid[-1]["bar"] - valid[0]["bar"], 5)
                      if valid else None),
        blob0_at_w0=valid[0]["blob0_quality"] if valid else None,
        blob0_at_max_w=valid[-1]["blob0_quality"] if valid else None,
        blob0_moved_by=(round(valid[-1]["blob0_quality"] -
                              valid[0]["blob0_quality"], 5) if valid else None),
        both_moved=bool(valid and
                        abs(valid[-1]["bar"] - valid[0]["bar"]) > 0.01 and
                        abs(valid[-1]["blob0_quality"] -
                            valid[0]["blob0_quality"]) > 0.01),
        reading="Emmett's condition for a defensible fix: BOTH numbers must "
                "move, so that erosion is not a one-sided favour to the "
                "candidate under discussion. If the bar falls as fast as blob "
                "0's score, the outcome at any given width was not predictable "
                "in advance. If blob 0 passes over a WIDE range of widths, "
                "that range is a plateau and a width inside it cannot have "
                "been tuned. NOTHING IS APPLIED HERE.")

    out_doc = dict(
        task="DIAGNOSTIC D: boundary contamination as a POPULATION property "
             "of facets, measured on all 29 canonical facets. Nothing is "
             "derived from blob 0.",
        dataset=name, date=args.stamp,
        status=("SIDE ARTIFACT ONLY. No erosion applied, no threshold changed, "
                "no canonical state written. canonical-2026-07-26-r2 remains "
                "canonical; published coverage remains 88.40 pct."),
        cross_checks=checks,
        units=dict(
            depth="POINT SPACINGS, not inches. Depth is a length and therefore "
                  "scale-dependent; expressed in spacings it transfers to any "
                  "cloud, which is the form an adopted value would need.",
            spacing_cu=spacing, in_per_cu=in_per_cu,
            one_spacing_in=round(spacing * in_per_cu, 4),
            residual="also in point spacings, for the same reason",
            plan_vs_slope="depth is measured on the PLAN grid, so for a facet "
                          "at pitch p the along-surface depth is between the "
                          "quoted value and value/cos(p). At the steepest "
                          "facet here (34 deg) that is at most a 21 percent "
                          "understatement."),
        boundary_classification=dict(
            near_cells=NEAR_CELLS,
            step_threshold_spacings=STEP_MULT,
            step_threshold_in=round(STEP_MULT * spacing * in_per_cu, 3),
            types=TYPES,
            method="for each boundary cell, look within NEAR_CELLS for any "
                   "other facet and compare the two PLANE heights there. "
                   "Something standing more than the step threshold above this "
                   "facet is an occlusion step; a neighbour at the same height "
                   "is a ridge, hip or valley; nothing nearby is a free edge."),
        physical_prediction=prediction,
        pooled_by_boundary_type=pooled_out,
        population=population,
        per_entity=rows_out,
        erosion_sweep=sweep,
        erosion_sweep_summary=sweep_summary,
        not_done=("no erosion is applied anywhere; the 8.4 inch figure from "
                  "the blob 0 probe is deliberately not used, and no width is "
                  "adopted"))
    p = out / f"boundary-erosion-population-{args.stamp}.json"
    p.write_text(json.dumps(out_doc, indent=2, default=float))
    print(f"\n  wrote {p}")

    render(out, args.stamp, name, rows_out, pooled_out, valid, spacing,
           in_per_cu, population, n_main)
    print("\n  PREDICTION (ordering by boundary type): "
          f"{'HELD' if prediction['prediction_held'] else 'DID NOT HOLD'}")
    print(f"  observed most-negative-first: "
          f"{prediction['observed_ordering_most_negative_first']}")
    for c in checks:
        print(f"  CHECK {'PASS' if c['passed'] else 'FAIL'}: {c['check']}")


def render(out, stamp, name, rows, pooled, sweep, spacing, in_per_cu, pop,
           n_main):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(2, 2, figsize=(16, 11), dpi=140)

    # 1. every entity's mean |residual| vs depth
    a = ax[0, 0]
    for r in rows:
        pr = r["profile_depth_in_spacings"]
        if not pr:
            continue
        x = [(p["depth_lo"] + min(p["depth_hi"], 64)) / 2 for p in pr]
        y = [p["mean_abs"] for p in pr]
        if r["id"] == "blob_0":
            a.plot(x, y, "o-", color="#d1440e", lw=2.6, ms=5, zorder=5,
                   label="blob 0 (rejected candidate)")
        else:
            a.plot(x, y, "-", lw=1.0,
                   color="#22558a" if r["kind"] == "main" else "#9bb4cf",
                   alpha=0.85)
    a.plot([], [], color="#22558a", lw=1.4, label="8 main facets")
    a.plot([], [], color="#9bb4cf", lw=1.4, label="21 recovered facets")
    a.set_xlabel("depth from facet boundary, point spacings")
    a.set_ylabel("mean |residual|, point spacings")
    a.set_title("every facet: roughness falls with depth into the facet")
    a.legend(fontsize=8); a.grid(alpha=0.25); a.set_xscale("symlog")

    # 2. pooled mean SIGNED residual by boundary type: the physical test
    a = ax[0, 1]
    cols = dict(abuts_taller_surface="#b2182b", free_edge="#ef8a62",
                junction_no_step="#2166ac")
    for tname, v in pooled.items():
        pr = v["profile"]
        x = [(p["depth_lo"] + min(p["depth_hi"], 64)) / 2 for p in pr]
        y = [p["mean_signed"] for p in pr]
        a.plot(x, y, "o-", ms=4, lw=2, color=cols.get(tname, "#666666"),
               label=f"{tname} (n={v['n_points']:,})")
    a.axhline(0, color="#888888", lw=1)
    a.set_xlabel("depth from the nearest boundary OF THAT TYPE, point spacings")
    a.set_ylabel("mean signed residual, point spacings")
    a.set_title("the physical prediction: the step should bite hardest\n"
                "where a taller surface stands over the facet", fontsize=10)
    a.legend(fontsize=8); a.grid(alpha=0.25); a.set_xscale("symlog")

    # 3. distribution of stabilisation depths
    a = ax[1, 0]
    vals = pop["stabilisation_depth_spacings"]["values"]
    a.hist(vals, bins=20, color="#6f8fb5", ec="white")
    a.axvline(pop["stabilisation_depth_spacings"]["median"], color="#b2182b",
              lw=2, label=f"median {pop['stabilisation_depth_spacings']['median']:.1f} sp"
                          f" ({pop['stabilisation_depth_inches']['median']} in)")
    a.set_xlabel("depth at which |residual| stabilises, point spacings")
    a.set_ylabel("facets")
    a.set_title("is there ONE erosion width for the population?")
    a.legend(fontsize=8)

    # 4. the sweep: both numbers
    a = ax[1, 1]
    w = [s["width_in"] for s in sweep]
    a.plot(w, [s["bar"] for s in sweep], "o-", color="#2166ac", lw=2.2, ms=5,
           label="quality bar (max over the 8 eroded main facets)")
    a.plot(w, [s["blob0_quality"] for s in sweep], "s-", color="#d1440e",
           lw=2.2, ms=5, label="blob 0, eroded")
    passing = [s for s in sweep if s["blob0_would_pass"]]
    if passing:
        a.axvspan(min(s["width_in"] for s in passing),
                  max(s["width_in"] for s in passing),
                  color="#2e7d32", alpha=0.12,
                  label="widths where blob 0 would pass")
    a.set_xlabel("erosion width applied to EVERY facet, inches")
    a.set_ylabel("fit quality, trimmed RMS / spacing")
    a.set_title("REPORTED, NOT APPLIED: both numbers move together",
                fontsize=10)
    a.legend(fontsize=8); a.grid(alpha=0.25)

    fig.suptitle(f"{name}: boundary contamination across all 29 facets "
                 f"({stamp})   SIDE ARTIFACT, nothing applied", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out / f"boundary-erosion-population-{stamp}.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
