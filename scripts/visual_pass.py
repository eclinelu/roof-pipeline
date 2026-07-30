"""Build the side-by-side HTML for one visual review pass.

A visual pass grades ONE artifact's per-facet renders against the PREVIOUS
artifact's renders, side by side, so a human can see what a single change did.
The process rules live in the visual-pass skill; this file is the harness the
skill describes, and it is the ONLY place the invocation details are written
down.

    python scripts/visual_pass.py --old 2026-07-26-r2 --new 2026-07-30-grid-adopted
    python scripts/visual_pass.py --old ... --new ... --no-serve   # build only
    python scripts/visual_pass.py --selftest                       # assertions only

Run it and it prints a URL. Open the URL, grade, close the tab. Verdicts are
written to disk as you type; there is no save button to forget.

WHAT IT TOUCHES
    reads   reports/<dataset>/canonical-<stamp>.json      facet metadata
    reads   reports/<dataset>/canonical-<stamp>.npz       facet point index sets
    reads   reports/<dataset>/review/*/review-data.json   locates render sets
    reads   reports/<dataset>/review/*/facet-NN.png       the renders themselves
    writes  passes/<old>-vs-<new>/pass.html
    writes  passes/<old>-vs-<new>/verdicts.json
    writes  passes/<old>-vs-<new>/crops/<side>-facet-NN.png   cropped copies

It never MODIFIES a render and never imports render code. The renders are
evidence produced by a different run, frequently by a run still in progress
somewhere else, and a review harness that can rewrite its own inputs is not a
review harness. The crops are NEW files under passes/; see write_crop for why
they are not written in place. `guard_write_path` turns that from a promise
into a check.

WHY CORRESPONDENCE IS COMPUTED AND NOT ASSUMED
    Facet 12 in the old artifact is not facet 12 in the new one. Indices are
    positions in an output list; they shift whenever a facet merges, splits,
    appears, or vanishes, and they shift silently. Pairing renders by index
    produces rows that look like a normal before/after while actually showing
    two unrelated pieces of roof.

    Facets own point index sets -- row numbers into the leveled cloud, stored
    one array per facet in the npz. Two facets are the same piece of roof to the
    extent that they own the same points. So correspondence here is set overlap
    and nothing else. That makes merges, splits, appearances and disappearances
    fall out of the arithmetic instead of being maintained by hand in a list
    that goes stale.

WHY THE GROUPING USES MUTUAL BEST MATCH AND NOT A THRESHOLD
    The obvious implementation links old i to new j when their overlap exceeds
    some cutoff. That cutoff is a tuned parameter with no principled value: set
    it low and unrelated facets that share a boundary strip get linked into one
    giant row; set it high and a genuine split whose halves each keep 40 percent
    of the parent stops being detected. Worse, a cutoff tuned so this pass looks
    tidy will silently mis-group the next pass, which is exactly the failure the
    log has recorded for scale-dependent thresholds elsewhere in this pipeline.

    So the topology is decided without one. An edge is drawn from every old
    facet to the new facet it shares the MOST points with, and from every new
    facet to the old facet it shares the most points with. Rows are the
    connected components of that graph. "Most" is a comparison, not a
    magnitude, so it needs no units and does not transfer badly between clouds.

    A 1-to-1 pairing is two mutual best matches agreeing. A merge is two old
    facets whose best match is the same new facet. A split is the mirror. A new
    facet has no incoming edge, a vanished facet has no outgoing one. All five
    layout cases come from the component shape, and no number was chosen.

    REPORT_FLOOR below is a threshold, but it only decides which additional
    non-best overlaps get PRINTED underneath a row. It never decides what gets
    grouped. That distinction is the whole point and the HTML states it.

WHY THE PIXEL DIFF IS NOT THE ANSWER
    Two renders can differ in pixels while the geometry is identical. Axis
    limits, colour scaling, annotation placement, font metrics and library
    versions all move pixels without moving a point. On the very first pair this
    harness was built against, eight facets had bit-identical point index sets
    and their renders still differed across four to eight percent of their
    pixels, because the artifact stamp in the title was a different length and
    the line labels had been laid out around a different set of neighbours.

    So each row prints the pixel diff NEXT TO the overlap fractions, and the
    overlap is the one that settles the question. A changed pixel flag means
    look closer. It does not mean something moved.
"""
import argparse
import hashlib
import html
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent

# Extra overlaps at or above this fraction are PRINTED under a row so leakage
# between neighbouring facets stays visible. This value never affects grouping;
# see the module docstring. 0.01 is a display convenience, not a tuned constant:
# below it the printed list fills with single-point boundary noise.
REPORT_FLOOR = 0.01

# Verdicts are free text. These are the coded options pass 1 offered, and a
# verdict consisting of nothing but one of them is refused, because pass 1 used
# them in contradictory senses across facets and that part of the record is now
# partly unusable. A code compresses an observation before anyone knows which
# distinction will matter, and the compression cannot be undone afterwards. The
# check is whole-field only: "the north edge is short" is fine, "short" is not.
PRESET_STRINGS = {
    "correct", "merge", "split", "spurious", "unsure",
    "tight", "short", "over", "ragged", "cut",
    "minor", "moderate", "major",
    "mistyped", "misplaced", "long",
    "n", "ne", "e", "se", "s", "sw", "w", "nw", "all", "multiple",
    "ok", "fine", "good", "bad", "pass", "fail", "yes", "no",
}


# --------------------------------------------------------------------------
# guards
# --------------------------------------------------------------------------

def guard_write_path(path):
    """Refuse to write anywhere that holds artifacts or existing review records.

    Assertion 5. The read-only contract is worth nothing if it is only stated
    in a docstring, so every write in this file goes through here first. A
    directory is off limits if it sits under reports/ or reviews/, or if it
    contains a canonical artifact, or if it is (or is inside) a review render
    set. Frozen artifacts are evidence and render sets may be in use by a run
    happening right now in another checkout.
    """
    path = Path(path).resolve()
    parts = [p.lower() for p in path.parts]
    for bad in ("reports", "reviews"):
        if bad in parts:
            raise SystemExit(
                f"REFUSED: {path} is under a {bad}/ directory. A visual pass "
                f"reads artifacts and renders; it never writes near them."
            )
    if "review" in parts:
        raise SystemExit(f"REFUSED: {path} is inside a review render set.")
    for parent in [path] + list(path.parents)[:3]:
        if parent.is_dir() and any(parent.glob("canonical-*.np*")):
            raise SystemExit(f"REFUSED: {parent} holds canonical artifacts.")
    return path


# --------------------------------------------------------------------------
# locating things
# --------------------------------------------------------------------------

def short_stamp(stamp):
    """`2026-07-26-r2` -> `r2`. Passes are named by artifact pair, not number."""
    trimmed = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", stamp)
    return trimmed or stamp


def load_artifact(dataset, stamp):
    """Load one artifact's facet metadata and its per-facet point index sets."""
    base = REPO / "reports" / dataset
    jpath = base / f"canonical-{stamp}.json"
    npath = base / f"canonical-{stamp}.npz"
    for p in (jpath, npath):
        if not p.exists():
            raise SystemExit(f"missing artifact file: {p}")

    meta = json.loads(jpath.read_text(encoding="utf-8"))
    z = np.load(npath)

    sets, arrays = {}, {}
    for key in z.files:
        m = re.fullmatch(r"facet_(\d+)", key)
        if not m:
            continue
        arr = z[key]
        idx = int(m.group(1))
        arrays[idx] = arr
        sets[idx] = set(arr.tolist())

    # Assertion 1, first half: these must be real point index sets, not a
    # stand-in derived from the facet numbering. Anything that fails here means
    # the npz is not what the replay block says it is.
    n_cloud = meta.get("replay", {}).get("source_cloud_n")
    for idx, arr in arrays.items():
        if arr.ndim != 1 or arr.size == 0:
            raise SystemExit(f"ANTI-NULL FAIL: facet_{idx} is not a non-empty 1-D index array")
        if not np.issubdtype(arr.dtype, np.integer):
            raise SystemExit(f"ANTI-NULL FAIL: facet_{idx} is {arr.dtype}, not integer indices")
        if arr.min() < 0 or (n_cloud and arr.max() >= n_cloud):
            raise SystemExit(
                f"ANTI-NULL FAIL: facet_{idx} indices fall outside the source cloud "
                f"(0..{n_cloud}); these are not row numbers into the leveled cloud"
            )
        if len(sets[idx]) != arr.size:
            raise SystemExit(f"ANTI-NULL FAIL: facet_{idx} contains duplicate point indices")

    if len(sets) != len(meta["facets"]):
        raise SystemExit(
            f"ANTI-NULL FAIL: {stamp} has {len(meta['facets'])} facets in json "
            f"but {len(sets)} index sets in npz"
        )

    return {
        "stamp": stamp,
        "short": short_stamp(stamp),
        "meta": meta,
        "sets": sets,
        "facets": {f["facet"]: f for f in meta["facets"]},
    }


def find_render_dir(dataset, stamp):
    """Find the render set for a stamp by reading what each set says it is.

    The render directory is NOT named after the artifact -- r2's renders live in
    review/2026-07-27. Guessing the directory from the stamp would work today
    and break the first time a set is re-rendered on a different date, so the
    directory is located by opening each review-data.json and reading its
    `review_of` field.
    """
    root = REPO / "reports" / dataset / "review"
    hits = []
    for data in sorted(root.glob("*/review-data.json")):
        try:
            j = json.loads(data.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if j.get("review_of") == f"canonical-{stamp}":
            hits.append((data.parent, j))
    if not hits:
        raise SystemExit(
            f"no render set declares review_of == canonical-{stamp}. "
            f"Looked in {root}"
        )
    if len(hits) > 1:
        raise SystemExit(
            f"{len(hits)} render sets claim canonical-{stamp}: "
            + ", ".join(str(h[0]) for h in hits)
        )
    return hits[0]


def render_provenance(path):
    """Which commit produced this render set, or an honest admission that we
    cannot tell. An undated render set compared against a dated one produces a
    diff nobody can attribute later, so the failure mode here is to say so
    rather than let the row imply the diff is trustworthy."""
    rel = os.path.relpath(path, REPO)
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%H%x1f%ad%x1f%s", "--date=short", "--", rel],
            cwd=REPO, capture_output=True, text=True, timeout=30,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", rel],
            cwd=REPO, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {"known": False, "why": "git is not available here"}

    if out.returncode != 0 or not out.stdout.strip():
        return {"known": False, "why": "these renders have no commit in this repository"}

    sha, date, subject = out.stdout.strip().split("\x1f", 2)
    uncommitted = [ln[3:] for ln in dirty.stdout.splitlines() if ln.strip()]
    if uncommitted:
        return {
            "known": False,
            "why": (f"{len(uncommitted)} file(s) in this render set differ from the "
                    f"last commit ({sha[:12]}); what is on disk is not what was committed"),
        }
    return {"known": True, "sha": sha, "short": sha[:12], "date": date, "subject": subject}


# --------------------------------------------------------------------------
# correspondence
# --------------------------------------------------------------------------

def correspond(old_sets, new_sets):
    """Group old and new facets into rows by point-index-set overlap.

    Returns (rows, pair_stats). See the module docstring for why this uses
    mutual best match rather than a cutoff.
    """
    inter = {}
    for i, a in old_sets.items():
        for j, b in new_sets.items():
            n = len(a & b)
            if n:
                inter[(i, j)] = n

    edges = set()
    for i, a in old_sets.items():
        best = [(n, j) for (ii, j), n in inter.items() if ii == i]
        if best:
            edges.add((i, max(best)[1]))
    for j, b in new_sets.items():
        best = [(n, i) for (i, jj), n in inter.items() if jj == j]
        if best:
            edges.add((max(best)[1], j))

    # connected components over the bipartite edge set
    adj_old, adj_new = {}, {}
    for i, j in edges:
        adj_old.setdefault(i, set()).add(j)
        adj_new.setdefault(j, set()).add(i)

    seen_old, seen_new, rows = set(), set(), []
    for start in sorted(old_sets):
        if start in seen_old:
            continue
        comp_o, comp_n, stack = set(), set(), [("o", start)]
        while stack:
            side, node = stack.pop()
            if side == "o":
                if node in comp_o:
                    continue
                comp_o.add(node)
                stack += [("n", x) for x in adj_old.get(node, ())]
            else:
                if node in comp_n:
                    continue
                comp_n.add(node)
                stack += [("o", x) for x in adj_new.get(node, ())]
        seen_old |= comp_o
        seen_new |= comp_n
        rows.append({"old": sorted(comp_o), "new": sorted(comp_n)})
    for j in sorted(new_sets):
        if j not in seen_new:
            seen_new.add(j)
            rows.append({"old": [], "new": [j]})

    for row in rows:
        row["case"] = classify(row)
        row["pairs"] = []
        for i in row["old"]:
            for j in row["new"]:
                n = inter.get((i, j), 0)
                row["pairs"].append({
                    "old": i, "new": j, "shared": n,
                    "frac_old": n / len(old_sets[i]),
                    "frac_new": n / len(new_sets[j]),
                    "in_row": True,
                })
        # leakage to facets outside this row, printed but never grouped
        row["leaks"] = []
        for i in row["old"]:
            for j in sorted(new_sets):
                if j in row["new"]:
                    continue
                n = inter.get((i, j), 0)
                if n and max(n / len(old_sets[i]), n / len(new_sets[j])) >= REPORT_FLOOR:
                    row["leaks"].append({
                        "old": i, "new": j, "shared": n,
                        "frac_old": n / len(old_sets[i]),
                        "frac_new": n / len(new_sets[j]),
                    })

    # Assertion 2: every old facet and every new facet appears in exactly one row.
    seen_o = [i for r in rows for i in r["old"]]
    seen_n = [j for r in rows for j in r["new"]]
    if sorted(seen_o) != sorted(old_sets) or len(seen_o) != len(set(seen_o)):
        raise SystemExit(f"ANTI-NULL FAIL: old facets not partitioned exactly once: {sorted(seen_o)}")
    if sorted(seen_n) != sorted(new_sets) or len(seen_n) != len(set(seen_n)):
        raise SystemExit(f"ANTI-NULL FAIL: new facets not partitioned exactly once: {sorted(seen_n)}")

    rows.sort(key=lambda r: (min(r["new"]) if r["new"] else min(r["old"]) + 0.5))
    for k, row in enumerate(rows):
        row["row_id"] = f"facet-row-{k}"
    return rows


def classify(row):
    no, nn = len(row["old"]), len(row["new"])
    if no == 1 and nn == 1:
        return "1-to-1"
    if no > 1 and nn == 1:
        return "merge"
    if no == 1 and nn > 1:
        return "split"
    if no == 0 and nn >= 1:
        return "new"
    if no >= 1 and nn == 0:
        return "vanished"
    return "tangled"


def frac(x):
    """Overlap fraction at full precision.

    17 decimal places is past what a float64 in [0,1] can carry, so a value
    printed as 1.00000000000000000 is EXACTLY 1.0 and not 0.9999999999999999
    rounded for display. That distinction is the whole reason the fractions are
    printed wide: "the same points" and "almost the same points" are different
    findings, and a %.4f table cannot tell them apart.
    """
    return f"{float(x):.17f}"


def is_exact_one(p):
    return p["frac_old"] == 1.0 and p["frac_new"] == 1.0


def overlap_table(rows):
    """The correspondence table, sorted so the weakest overlaps read first.

    Sorted ascending by the WEAKER of the two directions, because a pairing is
    only as solid as its worse side: a new facet that swallowed its predecessor
    whole still scores 1.0 on the old side while having gained a lot of points
    the old facet never owned. Anything that is not exactly 1.0000 both ways
    therefore appears above everything that is.

    Display only. This reads the rows correspond() already built and changes
    nothing about how they were built.
    """
    pairs = [dict(p, case=r["case"]) for r in rows for p in r["pairs"]]
    pairs.sort(key=lambda p: (min(p["frac_old"], p["frac_new"]),
                              max(p["frac_old"], p["frac_new"]), p["old"]))

    w = 19
    lines = [
        "",
        "correspondence overlap, all pairs, weakest first",
        "  fraction of old = shared / points owned by the OLD facet",
        "  fraction of new = shared / points owned by the NEW facet",
        "",
        f"  {'old':>4}  {'new':>4}  {'shared pts':>11}  "
        f"{'fraction of old':>{w}}  {'fraction of new':>{w}}  exact",
        f"  {'-'*4}  {'-'*4}  {'-'*11}  {'-'*w}  {'-'*w}  -----",
    ]
    for p in pairs:
        lines.append(
            f"  {p['old']:>4}  {p['new']:>4}  {p['shared']:>11,}  "
            f"{frac(p['frac_old']):>{w}}  {frac(p['frac_new']):>{w}}  "
            f"{'yes' if is_exact_one(p) else 'NO':>5}"
        )

    n_exact = sum(1 for p in pairs if is_exact_one(p))
    lines += [
        "",
        f"  {n_exact} of {len(pairs)} pairs are EXACTLY 1.0 in both directions "
        f"(same points, no gain, no loss).",
        f"  {len(pairs) - n_exact} of {len(pairs)} are not.",
    ]
    return "\n".join(lines)


CASE_NOTE = {
    "1-to-1": "one old facet, one new facet",
    "merge": "several old facets became one new facet",
    "split": "one old facet became several new facets",
    "new": "no predecessor: this facet did not exist in the old artifact",
    "vanished": "no successor: this facet is gone from the new artifact. THIS IS A FINDING.",
    "tangled": "N old to M new. Neither a clean merge nor a clean split; read the overlaps.",
}


# --------------------------------------------------------------------------
# pixel diff
# --------------------------------------------------------------------------

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pixel_diff(a, b):
    """Compare two render files. Never writes an image.

    Always given the ORIGINALS, never the crops: comparing crops would let a
    change in the crop rectangle masquerade as a change in geometry.
    """
    if not (a and b and Path(a).exists() and Path(b).exists()):
        return None
    ha, hb = sha256(a), sha256(b)
    out = {"hash_old": ha[:12], "hash_new": hb[:12], "hash_equal": ha == hb}
    A = np.asarray(Image.open(a).convert("RGB"), dtype=np.int16)
    B = np.asarray(Image.open(b).convert("RGB"), dtype=np.int16)
    if A.shape != B.shape:
        out.update(size_mismatch=True, shape_old=A.shape[:2], shape_new=B.shape[:2])
        return out
    d = np.abs(A - B)
    changed = (d != 0).any(axis=-1)
    out.update(
        size_mismatch=False,
        total_px=int(changed.size),
        changed_px=int(changed.sum()),
        changed_pct=100.0 * float(changed.mean()),
        max_channel_delta=int(d.max()),
        mean_abs_delta=float(d.mean()),
    )
    return out


_ROI_CACHE = {}


def roi_bbox(path, pad=0.08):
    """The rectangle holding the facet's actual drawing, excluding strays.

    WHY THIS EXISTS, and what the earlier version of it got wrong.

    review_render.py draws each per-facet close-up by zooming the WHOLE overview
    to one facet's extent, but the line and facet labels are placed at OVERVIEW
    data coordinates and matplotlib does not clip text to the axes. Labels
    belonging to lines nowhere near this facet still get drawn, far outside
    xlim/ylim, and fig.tight_layout() then tries to make room for all of them.
    When it cannot, it collapses the axes box instead. Facet 4 is the worst
    case: its axes box ends up roughly 320 px wide inside a 1950 px frame, so
    its roof is drawn at 213x240 px while facet 0 gets 916x1543 and facet 10
    gets 1513x979.

    The first attempt at this cropped to the union of ALL ink, which is exactly
    the wrong rectangle: the strays are ink, so the union still spans most of
    the frame and the crop barely helped. Facet 4 measured "15.9 percent of the
    frame used" under that rule when its real drawing is 1.7 percent of it.

    An earlier note here blamed a fixed figure size fighting set_aspect("equal").
    That was wrong. It came from a bounding box contaminated by the title text
    and the strays. Facet 4's points span 12.09 x 10.02 cloud units, an aspect
    of 1.21, which is unremarkable, and its extent is SMALLER than facet 0's.
    Aspect has nothing to do with it; the strays have everything to do with it.

    So the region of interest is the LARGEST connected ink component -- the
    drawn panel -- padded, then unioned with any component that overlaps that
    padded box, which keeps the labels genuinely sitting on this facet while
    dropping the ones scattered across empty space.

    A CROP CANNOT ADD DETAIL THE RENDER NEVER DREW. Facet 4 holds 213x240 real
    pixels of roof; enlarging that to a 700 px pane is a 2x upscale and will
    look soft. The only real fix is in review_render.py -- clip or drop
    out-of-view labels, or drop tight_layout -- and that file is off limits
    while another run is using it.
    """
    key = (str(path), pad)
    if key in _ROI_CACHE:
        return _ROI_CACHE[key]
    from scipy import ndimage
    a = np.asarray(Image.open(path).convert("RGB"))
    H, W = a.shape[:2]
    ink = (a < 250).any(axis=-1)          # the figure background is white
    lab, n = ndimage.label(ink)
    if n == 0:
        _ROI_CACHE[key] = None
        return None
    sizes = ndimage.sum(ink, lab, range(1, n + 1))
    boxes = ndimage.find_objects(lab)
    k = int(np.argmax(sizes))
    sl = boxes[k]
    y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
    # Panel plus a margin, and nothing else. An earlier version also unioned in
    # any ink component overlapping the padded box, meaning to keep labels
    # sitting on the facet. It kept the strays instead: they sit just outside
    # the panel, each one drags the box out far enough to touch the next, and
    # facet 4's crop came back with the label chain and a chopped title still
    # attached. Labels the render drew ON the facet are inside the panel box
    # already, so the union bought nothing and cost the whole fix.
    px, py = int(round(pad * (x1 - x0))), int(round(pad * (y1 - y0)))
    X0, X1, Y0, Y1 = x0 - px, x1 + px, y0 - py, y1 + py
    X0, Y0 = max(0, X0), max(0, Y0)
    X1, Y1 = min(W, X1), min(H, Y1)
    out = {"x0": X0, "y0": Y0, "x1": X1, "y1": Y1,
           "w": X1 - X0, "h": Y1 - Y0, "img_w": W, "img_h": H,
           "panel_w": x1 - x0, "panel_h": y1 - y0,
           "used_pct": 100.0 * (X1 - X0) * (Y1 - Y0) / (W * H),
           "gain": (W * H) / float((X1 - X0) * (Y1 - Y0))}
    _ROI_CACHE[key] = out
    return out


def write_crop(src, dst):
    """Write a cropped copy of a render into the pass output directory.

    This is the one place the harness creates an image, and it was added on
    request so the crop can be inspected as a file rather than only as a CSS
    transform in a browser.

    THE SOURCE IS NEVER TOUCHED. The crop is a NEW file under passes/, and the
    guard refuses any destination outside it. Overwriting the render in place
    was asked for and is deliberately not done: those PNGs are committed
    evidence, the pass header states which commit produced them, and rewriting
    them would make that provenance line false while colliding with whatever
    run is currently rendering. The original stays one click away from every
    pane.
    """
    roi = roi_bbox(src)
    if roi is None or roi["gain"] < 1.15:
        return None
    guard_write_path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im.crop((roi["x0"], roi["y0"], roi["x1"], roi["y1"])).save(dst)
    return roi


# --------------------------------------------------------------------------
# lines
# --------------------------------------------------------------------------

def line_rows(old_review, new_review, facet_map):
    """Pair intersection lines through the computed facet correspondence.

    A line is identified by the two facets it lies between, so the old line
    (13,14) matches the new line whose endpoints are the successors of old 13
    and old 14. Pairing lines by their own id would inherit exactly the index
    problem facets have.
    """
    old_lines = old_review.get("intersection_lines", [])
    new_lines = new_review.get("intersection_lines", [])
    new_by_key = {}
    for ln in new_lines:
        new_by_key.setdefault(frozenset(ln.get("between", [])), []).append(ln)

    rows, used = [], set()
    for ln in old_lines:
        key = frozenset(facet_map.get(f, f"old{f}") for f in ln.get("between", []))
        match = None
        for cand in new_by_key.get(key, []):
            if id(cand) not in used:
                match = cand
                used.add(id(cand))
                break
        rows.append({"old": ln, "new": match})
    for ln in new_lines:
        if id(ln) not in used:
            rows.append({"old": None, "new": ln})

    rows.sort(key=lambda r: -( (r["new"] or r["old"]).get("length_ft") or 0))
    for k, r in enumerate(rows):
        r["row_id"] = f"line-row-{k}"
        r["case"] = ("1-to-1" if r["old"] and r["new"]
                     else "new" if r["new"] else "vanished")
    return rows


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------

def build(dataset, old_stamp, new_stamp, out_dir=None, crop=True):
    old = load_artifact(dataset, old_stamp)
    new = load_artifact(dataset, new_stamp)
    old_dir, old_review = find_render_dir(dataset, old_stamp)
    new_dir, new_review = find_render_dir(dataset, new_stamp)

    rows = correspond(old["sets"], new["sets"])

    # one-to-one successor map, used only for line pairing
    facet_map = {}
    for row in rows:
        if len(row["old"]) == 1 and len(row["new"]) == 1:
            facet_map[row["old"][0]] = row["new"][0]

    def render_path(d, meta_facets, idx):
        name = meta_facets.get(idx, {}).get("render") or f"facet-{idx:02d}.png"
        # review-data.json is the record of what was rendered; fall back to the
        # naming convention only if it is silent.
        for data in (d / name, d / f"facet-{idx:02d}.png"):
            if data.exists():
                return data
        return None

    old_rd = {f["facet"]: f for f in old_review.get("facets", [])}
    new_rd = {f["facet"]: f for f in new_review.get("facets", [])}

    for row in rows:
        row["old_panes"] = [{
            "idx": i,
            "img": render_path(old_dir, old_rd, i),
            "facet": old["facets"].get(i, {}),
        } for i in row["old"]]
        row["new_panes"] = [{
            "idx": j,
            "img": render_path(new_dir, new_rd, j),
            "facet": new["facets"].get(j, {}),
        } for j in row["new"]]
        # The pixel diff always compares the ORIGINALS. Comparing crops would
        # let a change in the crop rectangle masquerade as a change in geometry.
        row["diff"] = (pixel_diff(row["old_panes"][0]["img"], row["new_panes"][0]["img"])
                       if row["case"] == "1-to-1" else None)

    lines = line_rows(old_review, new_review, facet_map)

    name = f"{old['short']}-vs-{new['short']}"
    out_dir = guard_write_path(Path(out_dir) if out_dir else REPO / "passes" / name)
    out_dir.mkdir(parents=True, exist_ok=True)

    ctx = {
        "name": name, "dataset": dataset,
        "old": old, "new": new,
        "old_dir": old_dir, "new_dir": new_dir,
        "old_prov": render_provenance(old_dir),
        "new_prov": render_provenance(new_dir),
        "rows": rows, "lines": lines,
        "out_dir": out_dir, "crop": crop,
    }

    # Assertion 4: verdict slots must cover every facet in each artifact.
    covered_new = sum(len(r["new"]) for r in rows)
    covered_old = sum(len(r["old"]) for r in rows)
    if covered_new != len(new["meta"]["facets"]) or covered_old != len(old["meta"]["facets"]):
        raise SystemExit(
            f"ANTI-NULL FAIL: rows cover {covered_old} old / {covered_new} new facets, "
            f"artifacts declare {len(old['meta']['facets'])} / {len(new['meta']['facets'])}"
        )

    # Crops are written as real files so they can be opened and inspected, not
    # only viewed through a CSS transform. They go under passes/, never over the
    # source render; see write_crop.
    if crop:
        n_crop = 0
        for row in rows:
            for side, panes in (("old", row["old_panes"]), ("new", row["new_panes"])):
                for pane in panes:
                    if pane["img"] is None:
                        continue
                    dst = out_dir / "crops" / f"{side}-facet-{pane['idx']:02d}.png"
                    got = write_crop(pane["img"], dst)
                    if got:
                        pane["crop"], pane["roi"] = dst, got
                        n_crop += 1
        ctx["n_crops"] = n_crop
    else:
        ctx["n_crops"] = 0

    html_path = guard_write_path(out_dir / "pass.html")
    html_path.write_text(render_html(ctx), encoding="utf-8")
    ctx["html_path"] = html_path
    ctx["verdicts_path"] = guard_write_path(out_dir / "verdicts.json")
    return ctx


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

def img_src(path, out_dir):
    if path is None:
        return None
    return os.path.relpath(path, out_dir).replace("\\", "/")


def prov_html(p, label):
    if p["known"]:
        return (f'<div class="prov ok"><b>{label} renders</b> produced by commit '
                f'<code>{p["short"]}</code> ({p["date"]}) &mdash; {html.escape(p["subject"])}</div>')
    return (f'<div class="prov unknown"><b>{label} renders: PROVENANCE UNKNOWN</b> &mdash; '
            f'{html.escape(p["why"])}. Do not read this row&rsquo;s diff as attributable.</div>')


def diff_html(d):
    if d is None:
        return '<div class="diff na">no pixel diff: this row is not a 1-to-1 pairing</div>'
    if d.get("size_mismatch"):
        return (f'<div class="diff changed"><b>hash: DIFFERENT</b> &nbsp; '
                f'image size changed {d["shape_old"]} &rarr; {d["shape_new"]}</div>')
    if d["hash_equal"]:
        return (f'<div class="diff same"><b>hash: IDENTICAL</b> ({d["hash_old"]}) &nbsp; '
                f'0 of {d["total_px"]:,} pixels differ. These are the same file.</div>')
    return (f'<div class="diff changed"><b>hash: DIFFERENT</b> '
            f'({d["hash_old"]} &rarr; {d["hash_new"]}) &nbsp; '
            f'{d["changed_px"]:,} of {d["total_px"]:,} pixels differ '
            f'({d["changed_pct"]:.2f}%), max channel delta {d["max_channel_delta"]}, '
            f'mean |delta| {d["mean_abs_delta"]:.2f}</div>')


def pane_html(pane, side, out_dir, crop=True):
    f = pane["facet"]
    src = img_src(pane["img"], out_dir)
    bits = []
    if f:
        bits.append(f'{f.get("kind","?")}')
        if f.get("pitch_deg") is not None:
            bits.append(f'pitch {f["pitch_deg"]:.2f}&deg;')
        if f.get("n_points"):
            bits.append(f'{f["n_points"]:,} pts')
        if f.get("quality_rms_over_spacing") is not None:
            bits.append(f'q {f["quality_rms_over_spacing"]:.4f}')
    meta = " &nbsp;|&nbsp; ".join(bits)
    if src is None:
        return (f'<div class="pane missing"><div class="panehead">{side} facet '
                f'{pane["idx"]}</div><div class="nopane">render file not found</div></div>')

    roi = pane.get("roi") if crop else None
    csrc = img_src(pane.get("crop"), out_dir) if crop and pane.get("crop") else None
    if csrc and roi:
        soft = ("" if roi["panel_w"] >= 700 else
                f' &middot; only {roi["panel_w"]}&times;{roi["panel_h"]} real pixels of '
                f'panel were drawn, so it enlarges soft')
        note = (f'<span class="cropnote">cropped &times;{roi["gain"]:.1f} &mdash; the '
                f'render drew into {roi["used_pct"]:.1f}% of its frame{soft}. '
                f'Click for the untouched original.</span>')
        img = f'<img src="{csrc}" loading="lazy">'
    else:
        note = ""
        img = f'<img src="{src}" loading="lazy">'
    return (f'<div class="pane"><div class="panehead">{side} facet {pane["idx"]}'
            f'<span class="pmeta">{meta}</span></div>{note}'
            f'<a href="{src}" target="_blank" title="open the full uncropped render">'
            f'{img}</a></div>')


def empty_pane_html(text):
    return (f'<div class="pane empty"><div class="panehead">&mdash;</div>'
            f'<div class="nopane">{text}</div></div>')


def render_html(ctx):
    out_dir = ctx["out_dir"]
    old, new = ctx["old"], ctx["new"]
    parts = []

    for row in ctx["rows"]:
        case = row["case"]
        crop = ctx.get("crop", True)
        left = ("".join(pane_html(p, "OLD", out_dir, crop) for p in row["old_panes"])
                or empty_pane_html("no predecessor<br>this facet is new"))
        right = ("".join(pane_html(p, "NEW", out_dir, crop) for p in row["new_panes"])
                 or empty_pane_html("no successor<br>this facet vanished"))

        ov = "".join(
            f'<tr><td>old {p["old"]}</td><td>new {p["new"]}</td>'
            f'<td>{p["shared"]:,}</td><td>{p["frac_old"]:.4f}</td>'
            f'<td>{p["frac_new"]:.4f}</td></tr>'
            for p in row["pairs"]) or '<tr><td colspan="5">no shared points</td></tr>'
        leaks = "".join(
            f'<tr class="leak"><td>old {p["old"]}</td><td>new {p["new"]}</td>'
            f'<td>{p["shared"]:,}</td><td>{p["frac_old"]:.4f}</td>'
            f'<td>{p["frac_new"]:.4f}</td></tr>'
            for p in row["leaks"])
        leak_note = ('<div class="leaknote">Rows below the line are overlaps with facets '
                     'OUTSIDE this row. They are printed, never grouped; grouping is mutual '
                     'best match and uses no cutoff.</div>') if leaks else ''

        geom_same = all(abs(p["frac_old"] - 1.0) < 1e-12 and abs(p["frac_new"] - 1.0) < 1e-12
                        for p in row["pairs"]) and case == "1-to-1"
        verdict_of_diff = ""
        if geom_same and row["diff"] and not row["diff"]["hash_equal"]:
            verdict_of_diff = ('<div class="caveatfire">Overlap is 1.0000 in both directions: '
                               'these two facets own <b>exactly the same points</b>. The pixel '
                               'difference above is annotation, layout or labelling, not '
                               'geometry. Nothing moved.</div>')

        # the same numbers the terminal table prints, at the same precision
        if row["pairs"]:
            hdr_ov = "".join(
                f'<span class="hov{"" if is_exact_one(p) else " notone"}">'
                f'{p["old"]}&rarr;{p["new"]} &nbsp;of old {frac(p["frac_old"])} '
                f'&nbsp;of new {frac(p["frac_new"])}'
                f'{"" if is_exact_one(p) else " &nbsp;NOT 1.0"}</span>'
                for p in row["pairs"])
        else:
            hdr_ov = '<span class="hov notone">no shared points with any facet</span>'

        parts.append(f"""
<section class="row {case}" id="{row['row_id']}">
  <h2>{case.upper()} &nbsp; old {row['old'] or '&mdash;'} &rarr; new {row['new'] or '&mdash;'}</h2>
  <div class="hovwrap">{hdr_ov}</div>
  <div class="casenote">{CASE_NOTE[case]}</div>
  {diff_html(row['diff'])}
  {verdict_of_diff}
  <table class="ov"><tr><th>old</th><th>new</th><th>shared pts</th>
    <th>fraction of old</th><th>fraction of new</th></tr>{ov}{leaks}</table>
  {leak_note}
  <div class="panes"><div class="side">{left}</div><div class="side">{right}</div></div>
  {verdict_block(row['row_id'], 'facet')}
</section>""")

    for row in ctx["lines"]:
        o, n = row["old"], row["new"]
        def ldesc(ln, tag):
            if ln is None:
                return f'<div class="pane empty"><div class="panehead">&mdash;</div><div class="nopane">{tag}</div></div>'
            return (f'<div class="pane lineinfo"><div class="panehead">{tag} line {ln["id"]}</div>'
                    f'<div class="linebody"><b>{ln.get("kind","?")}</b> between facets '
                    f'{ln.get("between")}<br>length {ln.get("length_ft","?")} ft</div></div>')
        parts.append(f"""
<section class="row line {row['case']}" id="{row['row_id']}">
  <h2>LINE &nbsp; {row['case'].upper()} &nbsp;
    {(n or o).get('kind','?')} between {(n or o).get('between')}</h2>
  <div class="casenote">Lines are paired through the computed facet correspondence,
    not by line id. Grade the crease against the facet renders above.</div>
  <div class="panes"><div class="side">{ldesc(o,'OLD')}</div>
    <div class="side">{ldesc(n,'NEW')}</div></div>
  {verdict_block(row['row_id'], 'line')}
</section>""")

    n_facet_rows = len(ctx["rows"])
    n_line_rows = len(ctx["lines"])
    row_ids = json.dumps([r["row_id"] for r in ctx["rows"]] + [r["row_id"] for r in ctx["lines"]])
    presets = json.dumps(sorted(PRESET_STRINGS))

    return f"""<!doctype html>
<meta charset="utf-8">
<title>visual pass {html.escape(ctx['name'])}</title>
<style>
 body{{font:15px/1.5 system-ui,sans-serif;margin:0;background:#111;color:#eee}}
 header{{position:sticky;top:0;background:#181818;border-bottom:2px solid #444;
   padding:7px 16px;z-index:20}}
 .hdrtop{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
 h1{{margin:0;font-size:14px;font-weight:700;white-space:nowrap}}
 h1 .sub{{font-weight:400}}
 #toggle{{margin-left:auto;background:#2a2a2a;color:#ddd;border:1px solid #555;
   border-radius:4px;padding:3px 10px;font:12px system-ui,sans-serif;cursor:pointer}}
 #toggle:hover{{background:#383838}}
 .terse{{font-size:11.5px;color:#8f8f8f;font-family:ui-monospace,monospace;
   white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
 .terse b{{color:#c8a44a}}
 #detail{{margin-top:8px}}
 #detail.hidden{{display:none}}
 .sub{{color:#aaa;font-size:12.5px}}
 .banner{{margin:6px 0;padding:7px 11px;border-radius:4px;font-size:12.5px}}
 .caveat{{background:#3a2f00;border-left:4px solid #d9a400}}
 .blind{{background:#2a2a3a;border-left:4px solid #7a7ad9}}
 .rule7{{background:#33202a;border-left:4px solid #c0506e}}
 .prov{{font-size:13px;padding:5px 10px;border-radius:3px;margin:4px 0}}
 .prov.ok{{background:#16261a;border-left:4px solid #3f8f52}}
 .prov.unknown{{background:#3a1a1a;border-left:4px solid #c04040;font-weight:600}}
 #status{{font-weight:700;padding:6px 12px;border-radius:4px;display:inline-block}}
 #status.incomplete{{background:#4a2020;color:#ffb0b0}}
 #status.complete{{background:#12331d;color:#9ff0b5}}
 #missing{{font-size:12px;color:#f0a0a0;max-height:70px;overflow:auto;margin-top:4px}}
 section.row{{border-top:1px solid #333;padding:20px;margin:0}}
 section.row.vanished{{background:#2a1414}}
 section.row.new{{background:#14202a}}
 section.row.merge,section.row.split,section.row.tangled{{background:#241f14}}
 h2{{font-size:16px;margin:0 0 4px}}
 .casenote{{color:#aaa;font-size:13px;margin-bottom:8px}}
 .hovwrap{{margin:2px 0 6px;display:flex;flex-wrap:wrap;gap:6px}}
 .hov{{font-family:ui-monospace,monospace;font-size:11.5px;padding:2px 8px;
   border-radius:3px;background:#12331d;color:#9ff0b5;white-space:nowrap}}
 .hov.notone{{background:#3a2a12;color:#ffcf8f;font-weight:700}}
 .diff{{font-size:13px;padding:6px 10px;border-radius:3px;margin:6px 0;font-family:ui-monospace,monospace}}
 .diff.same{{background:#12331d}} .diff.changed{{background:#33291a}} .diff.na{{background:#222;color:#999}}
 .caveatfire{{background:#1d2b3a;border-left:4px solid #4d90d9;padding:6px 10px;
   font-size:13px;margin:6px 0;border-radius:3px}}
 table.ov{{border-collapse:collapse;font-size:12px;margin:8px 0;font-family:ui-monospace,monospace}}
 table.ov th,table.ov td{{border:1px solid #383838;padding:2px 9px;text-align:right}}
 table.ov th{{background:#222;color:#bbb}}
 table.ov tr.leak td{{color:#999;border-top:2px solid #666}}
 .leaknote{{font-size:12px;color:#999;max-width:820px}}
 .panes{{display:flex;gap:14px;margin:12px 0}}
 .side{{flex:1;min-width:0;display:flex;flex-direction:column;gap:10px}}
 .pane{{border:1px solid #333;border-radius:4px;overflow:hidden;background:#0b0b0b}}
 .pane.empty{{border-style:dashed;border-color:#777}}
 .panehead{{background:#1e1e1e;padding:5px 9px;font-size:12px;font-weight:600}}
 .pmeta{{float:right;font-weight:400;color:#9a9a9a}}
 .pane img{{width:100%;display:block}}
 .cropbox{{position:relative;overflow:hidden;width:100%}}
 .cropbox img{{position:absolute;max-width:none;display:block}}
 .cropnote{{display:block;background:#22282e;color:#8fb8d9;font-size:11px;
   padding:2px 9px;border-bottom:1px solid #2e3742}}
 .nopane{{padding:38px 12px;text-align:center;color:#bbb;font-style:italic}}
 .linebody{{padding:14px;font-size:14px}}
 .vblock{{display:flex;gap:14px;margin-top:10px}}
 .vfield{{flex:1}}
 .vfield label{{display:block;font-size:12px;color:#bbb;margin-bottom:3px;font-weight:600}}
 textarea{{width:100%;box-sizing:border-box;min-height:76px;background:#0d0d0d;color:#eee;
   border:1px solid #444;border-radius:3px;padding:7px;font:14px/1.45 system-ui,sans-serif;
   resize:vertical}}
 textarea.filled{{border-color:#3f8f52}}
 textarea.rejected{{border-color:#c04040}}
 .rej{{color:#ff9a9a;font-size:12px;min-height:16px;margin-top:2px}}
 .hint{{font-size:11px;color:#888;margin-top:2px}}
</style>
<header>
 <div class="hdrtop">
  <h1>{html.escape(ctx['name'])}
    <span class="sub">{html.escape(ctx['dataset'])}</span></h1>
  <span id="status" class="incomplete">checking&hellip;</span>
  <button id="toggle" type="button">details</button>
 </div>
 <div class="terse" id="terse"><b>NOT BLIND</b> &middot; pixel diff can change without
   geometry changing &middot; <b>rule 7:</b> no parameter values &middot;
   {html.escape(old['stamp'])} &rarr; {html.escape(new['stamp'])}</div>
 <div id="missing"></div>
 <div id="detail" class="hidden">
  <div class="sub">OLD <code>{html.escape(old['stamp'])}</code>
    ({html.escape(str(os.path.relpath(ctx['old_dir'], REPO)))}) &nbsp;&rarr;&nbsp;
    NEW <code>{html.escape(new['stamp'])}</code>
    ({html.escape(str(os.path.relpath(ctx['new_dir'], REPO)))})</div>
  {prov_html(ctx['old_prov'], 'OLD')}
  {prov_html(ctx['new_prov'], 'NEW')}
  <div class="banner caveat"><b>PIXEL DIFF CAVEAT.</b> Two renders can differ in pixels
    while the geometry is identical &mdash; axis limits, colour scaling, annotation and
    label placement, font metrics and library versions all move pixels without moving a
    point. <b>A changed flag means look closer, not something moved.</b> The overlap
    fractions are computed from point index sets and are the ones that settle it.</div>
  <div class="banner blind"><b>THIS PASS IS NOT BLIND.</b> The old render is visible while
    the new one is graded, and which is which is labelled. Recorded as a property of this
    record.</div>
  <div class="banner rule7"><b>STANDING RULE 7.</b> Visual review can establish THAT
    something is wrong and WHAT it is physically. It can never set a parameter value.
    Describe what you saw, not what the fix should be.</div>
  <div class="banner caveat"><b>PANES ARE CROPPED TO THEIR CONTENT.</b> Some renders place
    their content in a small part of a mostly blank frame, so each pane is scaled to the
    rectangle that actually holds ink. Cropped panes say so and give the factor. Nothing
    inside the image is altered, and clicking any pane opens the full uncropped PNG.</div>
 </div>
</header>
<main>{''.join(parts)}</main>
<script>
const ROWS = {row_ids};
const PRESETS = new Set({presets});
const KEY = "visualpass:{html.escape(ctx['name'])}";
const N_FACET_ROWS = {n_facet_rows}, N_LINE_ROWS = {n_line_rows};
let served = false, saveTimer = null;

function why(v){{
  const t = (v||"").trim();
  if(!t) return "empty";
  if(PRESETS.has(t.toLowerCase())) return "that is a pass-1 preset code used on its own. "
    + "Free text only: say what you SAW.";
  return null;
}}

function state(){{
  const s = {{}};
  for(const id of ROWS){{
    for(const k of ["verdict","compare"]){{
      const el = document.getElementById(id+":"+k);
      if(el) s[id+":"+k] = el.value;
    }}
  }}
  return s;
}}

function refresh(){{
  const missing = [];
  for(const id of ROWS){{
    const el = document.getElementById(id+":verdict");
    const r = why(el.value);
    const msg = document.getElementById(id+":rej");
    el.classList.toggle("filled", !r);
    el.classList.toggle("rejected", !!r && el.value.trim().length>0);
    msg.textContent = (r && el.value.trim().length>0) ? ("REFUSED: "+r) : "";
    if(r) missing.push(id.replace("facet-row-","facet row ").replace("line-row-","line row ")
                        + (r==="empty" ? "" : " ("+r.split(".")[0]+")"));
  }}
  const st = document.getElementById("status");
  if(missing.length===0){{
    st.className = "complete";
    st.textContent = "COMPLETE \\u2014 " + N_FACET_ROWS + " facet rows and "
      + N_LINE_ROWS + " line rows all carry a verdict";
    document.getElementById("missing").textContent = "";
  }} else {{
    st.className = "incomplete";
    st.textContent = "NOT COMPLETE \\u2014 " + missing.length + " of "
      + ROWS.length + " rows lack an accepted verdict";
    document.getElementById("missing").textContent = "missing: " + missing.join(", ");
  }}
}}

function save(){{
  const s = state();
  try {{ localStorage.setItem(KEY, JSON.stringify(s)); }} catch(e) {{}}
  if(!served) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {{
    fetch("__save__", {{method:"POST", headers:{{"Content-Type":"application/json"}},
      body: JSON.stringify(s)}}).catch(()=>{{}});
  }}, 400);
}}

function restore(){{
  let s = null;
  try {{ s = JSON.parse(localStorage.getItem(KEY) || "null"); }} catch(e) {{}}
  if(!s) return;
  for(const [k,v] of Object.entries(s)){{
    const el = document.getElementById(k);
    if(el && !el.value) el.value = v;
  }}
}}

fetch("__ping__").then(r => {{ served = r.ok; }}).catch(()=>{{}});
fetch("__load__").then(r => r.ok ? r.json() : null).then(s => {{
  if(s) for(const [k,v] of Object.entries(s)){{
    const el = document.getElementById(k);
    if(el) el.value = v;
  }}
}}).catch(()=>{{}}).finally(() => {{ restore(); refresh(); }});

document.addEventListener("input", e => {{
  if(e.target.tagName === "TEXTAREA"){{ refresh(); save(); }}
}});

// The header carries standing caveats that must be present, but present is not
// the same as shouting: three fixed banners ate the top of every scroll. They
// collapse to one terse line and expand on demand, and the choice sticks.
const HKEY = KEY + ":hdr";
const detail = document.getElementById("detail");
const terse = document.getElementById("terse");
const toggle = document.getElementById("toggle");
function setHdr(open){{
  detail.classList.toggle("hidden", !open);
  terse.style.display = open ? "none" : "";
  toggle.textContent = open ? "hide details" : "details";
  try {{ localStorage.setItem(HKEY, open ? "1" : "0"); }} catch(e) {{}}
}}
toggle.addEventListener("click", () => setHdr(detail.classList.contains("hidden")));
let hopen = false;
try {{ hopen = localStorage.getItem(HKEY) === "1"; }} catch(e) {{}}
setHdr(hopen);
</script>
"""


def verdict_block(row_id, kind):
    what = ("what this render shows about the roof"
            if kind == "facet" else "what this crease looks like")
    return f"""
<div class="vblock">
  <div class="vfield">
    <label for="{row_id}:verdict">VERDICT &mdash; {what} (free text, required)</label>
    <textarea id="{row_id}:verdict" placeholder=""></textarea>
    <div class="rej" id="{row_id}:rej"></div>
    <div class="hint">Physical description only. No threshold, no parameter, no fix.</div>
  </div>
  <div class="vfield">
    <label for="{row_id}:compare">COMPARISON NOTE &mdash; how the new differs from the old
      (free text, separate field)</label>
    <textarea id="{row_id}:compare" placeholder=""></textarea>
    <div class="hint">Kept separate so nobody later has to guess which artifact an
      observation came from.</div>
  </div>
</div>"""


# --------------------------------------------------------------------------
# serving, so verdicts reach disk as they are typed
# --------------------------------------------------------------------------

def serve(ctx, port):
    """Serve the repo read-only and accept verdict writes.

    The document root is the repo so the same relative image paths work whether
    the file is opened directly or through the server. Only two paths accept a
    write, both inside the pass output directory, and both go through
    guard_write_path first.
    """
    vpath = ctx["verdicts_path"]
    rel = os.path.relpath(ctx["html_path"], REPO).replace("\\", "/")
    lock = threading.Lock()

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(REPO), **kw)

        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            leaf = self.path.rsplit("/", 1)[-1]
            if leaf == "__ping__":
                return self._json(200, {"ok": True})
            if leaf == "__load__":
                if vpath.exists():
                    d = json.loads(vpath.read_text(encoding="utf-8"))
                    return self._json(200, d.get("entries", {}))
                return self._json(200, {})
            return super().do_GET()

        def do_POST(self):
            if self.path.rsplit("/", 1)[-1] != "__save__":
                return self._json(404, {"error": "no"})
            n = int(self.headers.get("Content-Length", 0))
            try:
                incoming = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._json(400, {"error": "bad json"})

            # Assertion 3: refuse to record an empty verdict or a bare preset.
            accepted, refused = {}, {}
            for k, v in incoming.items():
                if k.endswith(":verdict"):
                    t = (v or "").strip()
                    if not t:
                        refused[k] = "empty"
                        continue
                    if t.lower() in PRESET_STRINGS:
                        refused[k] = f"bare preset string {t!r}"
                        continue
                accepted[k] = v

            with lock:
                guard_write_path(vpath)
                vpath.write_text(json.dumps({
                    "pass": ctx["name"],
                    "dataset": ctx["dataset"],
                    "old_artifact": ctx["old"]["stamp"],
                    "new_artifact": ctx["new"]["stamp"],
                    "old_renders": os.path.relpath(ctx["old_dir"], REPO).replace("\\", "/"),
                    "new_renders": os.path.relpath(ctx["new_dir"], REPO).replace("\\", "/"),
                    "old_render_commit": ctx["old_prov"],
                    "new_render_commit": ctx["new_prov"],
                    "blind": False,
                    "blind_note": "side by side; the grader saw the old render and knew "
                                  "which was which. Not blind evidence.",
                    "verdict_format": "free text only; no codes, no presets, no pass/fail",
                    "n_facet_rows": len(ctx["rows"]),
                    "n_line_rows": len(ctx["lines"]),
                    "entries": accepted,
                    "refused": refused,
                }, indent=1), encoding="utf-8")
            return self._json(200, {"saved": len(accepted), "refused": refused})

    class S(socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with S(("127.0.0.1", port), H) as srv:
        url = f"http://127.0.0.1:{srv.server_address[1]}/{rel}"
        # Flush explicitly. Python block-buffers stdout when it is not attached
        # to a terminal, so a backgrounded or piped run prints the URL nowhere
        # until the process exits -- which, for a server, is never. It looks
        # exactly like a hang.
        print(f"\n  open: {url}", flush=True)
        print(f"  verdicts stream to: {os.path.relpath(vpath, REPO)}", flush=True)
        print("  ctrl-c to stop\n", flush=True)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped. verdicts are on disk.")


# --------------------------------------------------------------------------
# self test
# --------------------------------------------------------------------------

def selftest(dataset, stamp):
    """Assertion 1, the half that can actually fail.

    Take one artifact, relabel its facets by a known permutation, and run
    correspondence between the original and the relabelled copy. Because
    correspondence is computed from point index sets, it must recover the
    permutation exactly. An implementation that paired by index number would
    return the identity mapping and fail here loudly.

    This is the anti-null: a correspondence routine that quietly fell back to
    indices would otherwise produce a clean-looking 1-to-1 result on every pass
    forever, and nothing in the output would look wrong.
    """
    art = load_artifact(dataset, stamp)
    n = len(art["sets"])
    perm = {i: (i * 7 + 3) % n for i in range(n)}
    if len(set(perm.values())) != n:
        raise SystemExit("selftest is broken: the permutation is not a bijection")
    if all(perm[i] == i for i in perm):
        raise SystemExit("selftest is void: the permutation is the identity")

    shuffled = {perm[i]: art["sets"][i] for i in art["sets"]}
    rows = correspond(art["sets"], shuffled)

    bad = []
    for row in rows:
        if len(row["old"]) != 1 or len(row["new"]) != 1:
            bad.append(f"row {row['old']}->{row['new']} is not 1-to-1")
            continue
        i, j = row["old"][0], row["new"][0]
        if perm[i] != j:
            bad.append(f"old {i} paired to new {j}, permutation says {perm[i]}")
        p = row["pairs"][0]
        if abs(p["frac_old"] - 1.0) > 1e-12 or abs(p["frac_new"] - 1.0) > 1e-12:
            bad.append(f"old {i} -> new {j} overlap {p['frac_old']}/{p['frac_new']}, expected 1.0")
    if bad:
        raise SystemExit("ANTI-NULL FAIL: correspondence did not recover the "
                         "relabelling:\n  " + "\n  ".join(bad))

    off = sum(1 for i in perm if perm[i] != i)
    print(f"  PASS  correspondence recovered a {n}-facet relabelling "
          f"({off} of {n} facets moved). It is reading point index sets, not indices.")

    # The control the test needs to not be void: index pairing must FAIL here.
    if all(perm[i] == i for i in perm):
        raise SystemExit("void")
    print(f"  POWER CHECK  an index-based implementation returns identity on this "
          f"input and would fail {off} of {n} pairings. The test could have gone "
          f"the other way.")

    # Assertion 5 must also be able to fire.
    for probe in (REPO / "reports" / dataset, REPO / "reports" / dataset / "review",
                  REPO / "reviews" / dataset):
        try:
            guard_write_path(probe / "pass.html")
        except SystemExit:
            continue
        raise SystemExit(f"ANTI-NULL FAIL: guard_write_path allowed a write into {probe}")
    print("  PASS  guard_write_path refuses every artifact and review directory tried.")


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dataset", default="big_house")
    ap.add_argument("--old", help="older artifact stamp, e.g. 2026-07-26-r2")
    ap.add_argument("--new", help="newer artifact stamp, e.g. 2026-07-30-grid-adopted")
    ap.add_argument("--out", help="output directory (default passes/<old>-vs-<new>)")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-crop", action="store_true",
                    help="show each render in its full frame instead of cropping the "
                         "pane to the rectangle that holds content")
    ap.add_argument("--no-serve", action="store_true",
                    help="build the HTML and exit; verdicts then buffer in the browser "
                         "instead of streaming to disk")
    ap.add_argument("--selftest", action="store_true",
                    help="run the anti-null assertions against --new and exit")
    args = ap.parse_args()

    if args.selftest:
        stamp = args.new or args.old
        if not stamp:
            ap.error("--selftest needs --new (or --old) to name an artifact")
        print("anti-null assertions:")
        selftest(args.dataset, stamp)
        return

    if not (args.old and args.new):
        ap.error("--old and --new are both required")

    print("anti-null assertions:")
    selftest(args.dataset, args.new)

    ctx = build(args.dataset, args.old, args.new, args.out, crop=not args.no_crop)

    cases = {}
    for r in ctx["rows"]:
        cases[r["case"]] = cases.get(r["case"], 0) + 1
    print(f"\nbuilt {ctx['name']}")
    print(f"  {len(ctx['rows'])} facet rows: "
          + ", ".join(f"{v} {k}" for k, v in sorted(cases.items())))
    print(f"  {len(ctx['lines'])} line rows")
    print(f"  {len(ctx['rows']) + len(ctx['lines'])} verdicts required, all free text")
    print(overlap_table(ctx["rows"]))
    print()
    for label, p in (("OLD", ctx["old_prov"]), ("NEW", ctx["new_prov"])):
        print(f"  {label} renders: "
              + (f"commit {p['short']} ({p['date']})" if p["known"]
                 else f"PROVENANCE UNKNOWN - {p['why']}"))
    print(f"  html: {os.path.relpath(ctx['html_path'], REPO)}")
    if ctx.get("n_crops"):
        print(f"  crops: {ctx['n_crops']} written to "
              f"{os.path.relpath(ctx['out_dir'] / 'crops', REPO)} "
              f"(new files; no source render was modified)")

    if args.no_serve:
        print("\n  --no-serve: open the file directly. Verdicts will buffer in the "
              "browser and NOT reach disk. Re-run without --no-serve to persist them.")
        return
    serve(ctx, args.port)


if __name__ == "__main__":
    main()
