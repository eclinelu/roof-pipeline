# Tests for the visual-pass harness.
#
# The r2-vs-grid-adopted pass is 29 clean 1-to-1 rows, so running it exercises
# ONE of the five required layout cases. The other four -- merge, split, new,
# vanished -- are built but never touched by that artifact pair, and a layout
# that has never once been executed is a layout that does not work. These tests
# drive all five through synthetic index sets, where the right answer is known
# by construction rather than by inspection.
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import visual_pass as vp


def s(*ranges):
    """A point index set built from half-open ranges."""
    out = set()
    for lo, hi in ranges:
        out |= set(range(lo, hi))
    return out


def cases(rows):
    return sorted((r["case"], tuple(r["old"]), tuple(r["new"])) for r in rows)


def test_one_to_one():
    rows = vp.correspond({0: s((0, 100))}, {0: s((0, 100))})
    assert cases(rows) == [("1-to-1", (0,), (0,))]
    p = rows[0]["pairs"][0]
    assert p["frac_old"] == 1.0 and p["frac_new"] == 1.0


def test_merge_two_old_into_one_new():
    old = {0: s((0, 100)), 1: s((100, 200))}
    new = {0: s((0, 200))}
    rows = vp.correspond(old, new)
    assert cases(rows) == [("merge", (0, 1), (0,))]
    # both halves report as half of the merged facet, and all of themselves
    fr = {p["old"]: (p["frac_old"], p["frac_new"]) for p in rows[0]["pairs"]}
    assert fr == {0: (1.0, 0.5), 1: (1.0, 0.5)}


def test_split_one_old_into_two_new():
    old = {0: s((0, 200))}
    new = {0: s((0, 100)), 1: s((100, 200))}
    rows = vp.correspond(old, new)
    assert cases(rows) == [("split", (0,), (0, 1))]


def test_new_facet_has_no_predecessor():
    rows = vp.correspond({0: s((0, 100))}, {0: s((0, 100)), 1: s((500, 600))})
    assert ("new", (), (1,)) in cases(rows)


def test_vanished_facet_has_no_successor():
    # THE case index pairing hides: old 1 disappears, new 1 is something else.
    old = {0: s((0, 100)), 1: s((500, 600))}
    new = {0: s((0, 100))}
    rows = vp.correspond(old, new)
    assert ("vanished", (1,), ()) in cases(rows)


def test_vanished_is_not_disguised_as_one_to_one():
    # Index pairing would call this two 1-to-1 rows and hide both findings.
    old = {0: s((0, 100)), 1: s((500, 600))}
    new = {0: s((0, 100)), 1: s((900, 1000))}
    got = cases(vp.correspond(old, new))
    assert ("vanished", (1,), ()) in got
    assert ("new", (), (1,)) in got
    assert not any(c[0] == "1-to-1" and c[1] == (1,) for c in got)


def test_indices_are_never_used_for_pairing():
    # Same geometry, labels reversed. An index-based implementation returns
    # 0->0 and 1->1; a set-based one must return 0->1 and 1->0.
    old = {0: s((0, 100)), 1: s((100, 200))}
    new = {0: s((100, 200)), 1: s((0, 100))}
    rows = vp.correspond(old, new)
    assert cases(rows) == [("1-to-1", (0,), (1,)), ("1-to-1", (1,), (0,))]


def test_every_facet_lands_in_exactly_one_row():
    old = {0: s((0, 100)), 1: s((100, 200)), 2: s((900, 950))}
    new = {0: s((0, 200)), 1: s((300, 400))}
    rows = vp.correspond(old, new)
    assert sorted(i for r in rows for i in r["old"]) == [0, 1, 2]
    assert sorted(j for r in rows for j in r["new"]) == [0, 1]


def test_boundary_leakage_does_not_create_a_row():
    # Facets that share a thin boundary strip must stay in separate rows: the
    # report floor decides what is PRINTED, never what is GROUPED.
    old = {0: s((0, 100)), 1: s((98, 200))}
    new = {0: s((0, 100)), 1: s((98, 200))}
    rows = vp.correspond(old, new)
    assert cases(rows) == [("1-to-1", (0,), (0,)), ("1-to-1", (1,), (1,))]
    assert any(lk["new"] == 1 for lk in rows[0]["leaks"])


def test_tangled_is_reported_not_forced():
    # Both old facets' largest share went to new 0, but new 1's largest share
    # came from old 0. The best-match edges cross, so this is neither a clean
    # merge nor a clean split and must be reported as its own case rather than
    # rounded into one of the four tidy ones.
    old = {0: s((0, 100)), 1: s((100, 200))}
    new = {0: s((0, 60), (100, 170)), 1: s((60, 100), (170, 200))}
    rows = vp.correspond(old, new)
    assert [r["case"] for r in rows] == ["tangled"]
    assert rows[0]["old"] == [0, 1] and rows[0]["new"] == [0, 1]
    assert len(rows[0]["pairs"]) == 4


@pytest.mark.parametrize("case", ["1-to-1", "merge", "split", "new", "vanished", "tangled"])
def test_every_case_has_a_layout_note(case):
    assert case in vp.CASE_NOTE


def test_frac_distinguishes_exactly_one_from_nearly_one():
    # The point of printing wide: "the same points" and "almost the same points"
    # are different findings, and %.4f cannot tell them apart.
    assert vp.frac(1.0) == "1.00000000000000000"
    nearly = 1.0 - 2 ** -53
    assert vp.frac(nearly) != vp.frac(1.0)
    assert round(nearly, 4) == 1.0  # a 4-decimal table would have called it 1.0


def test_overlap_table_sorts_weakest_first_and_counts_exact_pairs():
    rows = [
        {"case": "1-to-1", "pairs": [{"old": 0, "new": 0, "shared": 10,
                                      "frac_old": 1.0, "frac_new": 1.0}]},
        {"case": "1-to-1", "pairs": [{"old": 1, "new": 1, "shared": 5,
                                      "frac_old": 0.5, "frac_new": 0.9}]},
        # scores 1.0 on the old side but gained points: the weaker side rules
        {"case": "1-to-1", "pairs": [{"old": 2, "new": 2, "shared": 8,
                                      "frac_old": 1.0, "frac_new": 0.8}]},
    ]
    out = vp.overlap_table(rows)
    # data rows are the ones carrying the exact-match column
    order = [ln.split()[0] for ln in out.splitlines()
             if ln.rstrip().endswith(("yes", "NO"))]
    assert order == ["1", "2", "0"]
    assert "1 of 3 pairs are EXACTLY 1.0 in both directions" in out
    assert "2 of 3 are not" in out


def test_overlap_table_is_display_only():
    # It must not mutate the rows it reads.
    old = {0: s((0, 100)), 1: s((100, 200))}
    new = {0: s((0, 100)), 1: s((100, 190))}
    rows = vp.correspond(old, new)
    before = json.dumps(rows, sort_keys=True, default=str)
    vp.overlap_table(rows)
    assert json.dumps(rows, sort_keys=True, default=str) == before


def test_real_pass_has_exactly_eight_bit_identical_pairs():
    # The 8 main facets are untouched by the grid fix; the 21 recovered ones
    # all moved. If that ratio ever changes, this is the alarm.
    old = vp.load_artifact("big_house", "2026-07-26-r2")
    new = vp.load_artifact("big_house", "2026-07-30-grid-adopted")
    rows = vp.correspond(old["sets"], new["sets"])
    pairs = [p for r in rows for p in r["pairs"]]
    exact = [p for p in pairs if vp.is_exact_one(p)]
    assert len(pairs) == 29
    assert sorted(p["old"] for p in exact) == list(range(8))


def test_roi_is_the_drawn_panel_not_the_union_of_all_ink(tmp_path):
    # THE bug this replaced: cropping to the union of all ink keeps the strays,
    # because strays are ink. The ROI must be the largest connected component.
    from PIL import Image
    import numpy as np
    a = np.full((400, 400, 3), 255, np.uint8)
    a[100:300, 120:280] = 0          # the drawn panel, 160x200
    a[20:30, 10:40] = 0              # a stray label far away
    a[370:380, 350:390] = 0          # and another
    p = tmp_path / "t.png"
    Image.fromarray(a).save(p)
    r = vp.roi_bbox(p, pad=0.0)
    assert (r["x0"], r["y0"], r["w"], r["h"]) == (120, 100, 160, 200)
    assert r["panel_w"] == 160 and r["panel_h"] == 200
    # the union of ALL ink would have spanned nearly the whole frame
    ink = (np.asarray(Image.open(p).convert("RGB")) < 250).any(-1)
    ys, xs = np.where(ink)
    union_area = (xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)
    assert union_area > 4 * (r["w"] * r["h"])


def test_roi_ignores_strays_entirely(tmp_path):
    # The box must be panel-plus-padding and nothing else, whether or not a
    # stray sits nearby. The first attempt unioned in any overlapping component,
    # so each stray reached the next and the whole label chain came along.
    from PIL import Image
    import numpy as np

    def box(with_strays):
        a = np.full((400, 400, 3), 255, np.uint8)
        a[100:300, 120:280] = 0                  # the panel
        if with_strays:
            a[305:315, 130:170] = 0              # just below it
            a[320:330, 140:180] = 0              # and reaching further
            a[340:350, 150:190] = 0
        p = tmp_path / f"t{int(with_strays)}.png"
        Image.fromarray(a).save(p)
        r = vp.roi_bbox(p, pad=0.08)
        return (r["x0"], r["y0"], r["x1"], r["y1"])

    assert box(True) == box(False)               # strays change nothing
    # panel spans x 120..280 (w 160, pad 13) and y 100..300 (h 200, pad 16)
    assert box(False) == (107, 84, 293, 316)


def test_roi_is_a_no_op_on_a_full_frame(tmp_path):
    from PIL import Image
    import numpy as np
    p = tmp_path / "full.png"
    Image.fromarray(np.zeros((100, 100, 3), np.uint8)).save(p)
    assert vp.roi_bbox(p, pad=0.0)["gain"] == pytest.approx(1.0)


def test_write_crop_never_touches_the_source(tmp_path):
    src = vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted/facet-04.png"
    before = vp.sha256(src)
    dst = vp.REPO / "passes" / "tmp-selftest" / "crops" / "c.png"
    try:
        roi = vp.write_crop(src, dst)
        assert roi is not None and dst.exists()
        assert vp.sha256(src) == before          # source byte-identical
        from PIL import Image
        with Image.open(dst) as im:
            assert (im.width, im.height) == (roi["w"], roi["h"])
        assert im.width < 600                     # actually cropped
    finally:
        if dst.exists():
            dst.unlink()
        for d in (dst.parent, dst.parent.parent):
            if d.exists() and not any(d.iterdir()):
                d.rmdir()


def test_write_crop_refuses_to_write_next_to_the_renders():
    src = vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted/facet-04.png"
    for bad in (src,                                              # in place
                src.parent / "facet-04-cropped.png",              # beside it
                vp.REPO / "reports/big_house/facet-04.png",
                vp.REPO / "reviews/big_house/facet-04.png"):
        with pytest.raises(SystemExit):
            vp.write_crop(src, bad)


def test_facet_4_is_the_render_outlier_and_the_roi_recovers_it():
    # The reason cropping exists. If review_render.py is ever fixed, facet 4's
    # panel grows and this test failing is the signal to revisit the crop.
    d = vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted"
    roi = {i: vp.roi_bbox(d / f"facet-{i:02d}.png") for i in range(29)}
    panel_px = {i: r["panel_w"] * r["panel_h"] for i, r in roi.items()}
    assert min(panel_px, key=panel_px.get) == 4
    assert roi[4]["panel_w"] < 300 and roi[4]["panel_h"] < 300
    assert sorted(panel_px.values())[1] > 8 * panel_px[4]   # nothing is close
    assert roi[4]["gain"] > 20.0


def test_a_cropped_pane_says_so_and_admits_when_it_will_look_soft():
    src = vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted/facet-04.png"
    roi = vp.roi_bbox(src)
    pane = {"idx": 4, "facet": {}, "img": src,
            "crop": vp.REPO / "passes" / "a-vs-b" / "crops" / "new-facet-04.png",
            "roi": roi}
    out = vp.pane_html(pane, "NEW", vp.REPO / "passes" / "a-vs-b", crop=True)
    assert "cropnote" in out and "cropped" in out
    assert "enlarges soft" in out              # 247px panel, honest about it
    assert "untouched original" in out
    # the href must point at the ORIGINAL render; only the <img> is the crop
    href = out.split('href="')[1].split('"')[0]
    imgsrc = out.split('<img src="')[1].split('"')[0]
    assert href.endswith("review/2026-07-30-grid-adopted/facet-04.png")
    assert imgsrc.endswith("crops/new-facet-04.png")


def test_crop_can_be_turned_off():
    src = vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted/facet-04.png"
    pane = {"idx": 4, "facet": {}, "img": src,
            "crop": vp.REPO / "passes" / "a-vs-b" / "crops" / "new-facet-04.png",
            "roi": vp.roi_bbox(src)}
    out_dir = vp.REPO / "passes" / "a-vs-b"
    assert "cropnote" in vp.pane_html(pane, "NEW", out_dir, crop=True)
    assert "cropnote" not in vp.pane_html(pane, "NEW", out_dir, crop=False)


def test_header_collapses_but_keeps_the_standing_caveats():
    ctx = _mini_ctx()
    out = vp.render_html(ctx)
    assert 'id="detail" class="hidden"' in out      # collapsed by default
    assert 'id="toggle"' in out and 'id="terse"' in out
    # the three standing notices must survive collapsing, in full
    for must in ("PIXEL DIFF CAVEAT", "THIS PASS IS NOT BLIND", "STANDING RULE 7",
                 "PANES ARE CROPPED TO THEIR CONTENT"):
        assert must in out
    # and their headlines must be visible while collapsed
    terse = out.split('id="terse"')[1].split("</div>")[0]
    assert "NOT BLIND" in terse and "rule 7" in terse
    # completeness status is never hidden behind the toggle
    assert out.index('id="status"') < out.index('id="detail"')


def test_download_button_exists_and_carries_a_self_standing_record():
    # The file:// route has no server, so the page itself must be able to emit
    # the same record the served path writes. Anything missing here silently
    # produces a second-class record that looks fine until someone reads it.
    ctx = _mini_ctx()
    out = vp.render_html(ctx)
    assert 'id="save"' in out and "function buildRecord" in out
    meta = json.loads(re.search(r"const META = (\{.*?\n\});", out, re.S).group(1))
    for k in ("pass", "dataset", "old_artifact", "new_artifact", "blind",
              "blind_note", "verdict_format", "old_render_commit",
              "new_render_commit", "n_facet_rows", "n_line_rows"):
        assert k in meta, k
    assert meta["blind"] is False          # never silently becomes blind evidence


def test_downloaded_record_cannot_launder_a_refused_verdict():
    # Opening the file must not be a way around the empty/preset refusal.
    out = vp.render_html(_mini_ctx())
    body = out.split("function buildRecord")[1].split("document.getElementById(\"save\")")[0]
    assert "why(v)" in body and "refused[" in body
    assert "entries[id" in body
    # a refused verdict is diverted, never also written into entries
    assert body.index("refused[") < body.index("entries[id")


def test_into_review_is_explicit_and_never_the_default():
    bad = vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted/review.html"
    with pytest.raises(SystemExit):
        vp.guard_write_path(bad)                       # default still refuses
    assert vp.guard_write_path(bad, allow_artifact_dir=True) == bad.resolve()


def test_paths_in_the_review_folder_build_all_resolve():
    # Placed in the render folder, NEW panes are siblings and OLD panes sit one
    # directory up. A broken relative path here means a page full of dead images.
    d = vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted"
    page = d / "review.html"
    if not page.exists():
        pytest.skip("review-folder build not present")
    p = page.read_text(encoding="utf-8")
    refs = (re.findall(r'<img src="([^"]+)"', p)
            + re.findall(r'<a href="([^"]+)" target', p))
    assert refs
    missing = [r for r in refs if not (d / r).exists()]
    assert missing == [], missing


def test_guard_refuses_artifact_and_review_directories():
    repo = vp.REPO
    for bad in [repo / "reports" / "big_house" / "x.html",
                repo / "reports" / "big_house" / "review" / "x.html",
                repo / "reports" / "big_house" / "review" / "2026-07-27" / "x.html",
                repo / "reviews" / "big_house" / "x.html"]:
        with pytest.raises(SystemExit):
            vp.guard_write_path(bad)


def test_guard_allows_the_pass_output_directory():
    assert vp.guard_write_path(vp.REPO / "passes" / "a-vs-b" / "pass.html")


def test_preset_strings_are_refused_as_bare_verdicts():
    # The pass-1 codes, used on their own, are exactly what this refuses.
    for bad in ("correct", "SHORT", " tight ", "unsure", "major", "NW"):
        assert bad.strip().lower() in vp.PRESET_STRINGS
    # ...but a real free-text observation containing one of those words is fine.
    for good in ("the north edge stops short of the real eave by about a foot",
                 "outline is correct along the ridge but ragged at the west gutter"):
        assert good.strip().lower() not in vp.PRESET_STRINGS


def _mini_ctx():
    """A context covering every layout case, for driving render_html."""
    def pane(idx):
        return {"idx": idx, "img": None, "facet": {"kind": "recovered", "pitch_deg": 12.0,
                                                   "n_points": 1000,
                                                   "quality_rms_over_spacing": 2.0}}
    rows = []
    for k, (case, o, n) in enumerate([("1-to-1", [0], [0]), ("merge", [1, 2], [1]),
                                      ("split", [3], [2, 3]), ("new", [], [4]),
                                      ("vanished", [4], []), ("tangled", [5, 6], [5, 6])]):
        rows.append({"case": case, "old": o, "new": n, "row_id": f"facet-row-{k}",
                     "pairs": [], "leaks": [], "diff": None,
                     "old_panes": [pane(i) for i in o], "new_panes": [pane(j) for j in n]})
    ctx = {
        "name": "a-vs-b", "dataset": "big_house", "out_dir": vp.REPO / "passes" / "a-vs-b",
        "old": {"stamp": "A"}, "new": {"stamp": "B"},
        "old_dir": vp.REPO / "reports" / "big_house" / "review" / "2026-07-27",
        "new_dir": vp.REPO / "reports" / "big_house" / "review" / "2026-07-27",
        "old_prov": {"known": True, "short": "abc", "date": "2026-01-01", "subject": "x"},
        "new_prov": {"known": False, "why": "uncommitted"},
        "rows": rows,
        "lines": [{"row_id": "line-row-0", "case": "1-to-1",
                   "old": {"id": 0, "kind": "ridge", "between": [1, 3], "length_ft": 5.0},
                   "new": {"id": 0, "kind": "ridge", "between": [1, 3], "length_ft": 5.0}},
                  {"row_id": "line-row-1", "case": "vanished",
                   "old": {"id": 1, "kind": "hip", "between": [2, 4], "length_ft": 3.0},
                   "new": None}],
    }
    return ctx


def test_html_renders_all_five_layout_cases():
    # Drives render_html over a context holding every case, so a template break
    # in the merge/split/new/vanished branches fails here rather than silently
    # producing a page with an empty pane where a finding should be.
    ctx = _mini_ctx()
    rows = ctx["rows"]
    out = vp.render_html(ctx)
    assert "no predecessor" in out and "no successor" in out
    assert "THIS IS A FINDING" in out
    for case in ("1-to-1", "merge", "split", "new", "vanished", "tangled"):
        assert f'class="row {case}"' in out
    # every row gets both fields, and neither is a dropdown
    assert out.count(":verdict") >= 2 * (len(rows) + 2)
    assert ":compare" not in out          # one field, not two
    assert "<select" not in out and "datalist" not in out
    # PROVENANCE UNKNOWN must be stated, not implied
    assert "PROVENANCE UNKNOWN" in out
    assert "NOT BLIND" in out


def test_the_real_pass_is_all_one_to_one_and_covers_facet_4():
    # M3 is not fixed as of 2026-07-30, so the five split pairs are still split
    # and this pass must contain no merge rows. If a later change merges them,
    # this test failing is the correct alarm, not a nuisance.
    old = vp.load_artifact("big_house", "2026-07-26-r2")
    new = vp.load_artifact("big_house", "2026-07-30-grid-adopted")
    rows = vp.correspond(old["sets"], new["sets"])
    assert len(rows) == 29
    assert {r["case"] for r in rows} == {"1-to-1"}
    assert any(r["old"] == [4] and r["new"] == [4] for r in rows)
    for pair in (8, 23), (12, 24), (21, 28), (22, 27), (25, 26):
        assert all(any(r["new"] == [p] for r in rows) for p in pair)


def test_main_facets_have_identical_index_sets_but_renders_differ():
    # The caveat, on real data: facets 0-7 own EXACTLY the same points in both
    # artifacts and their PNGs still differ. If this ever stops being true the
    # caveat text should be re-read, not silently kept.
    old = vp.load_artifact("big_house", "2026-07-26-r2")
    new = vp.load_artifact("big_house", "2026-07-30-grid-adopted")
    for i in range(8):
        assert old["sets"][i] == new["sets"][i], f"facet {i} geometry changed"
    d = vp.pixel_diff(
        vp.REPO / "reports/big_house/review/2026-07-27/facet-04.png",
        vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted/facet-04.png")
    assert d["hash_equal"] is False
    assert d["changed_px"] > 0


def test_there_is_exactly_one_verdict_field_per_row():
    # The comparison note is gone. Comparing the two images IS the verdict, and
    # the first completed pass proved it: 47 verdicts filled, 1 comparison note.
    out = vp.render_html(_mini_ctx())
    assert ":compare" not in out
    assert "COMPARISON NOTE" not in out
    assert out.count("VERDICT &mdash;") == 8      # 6 facet rows + 2 line rows
    assert "old against new" in out               # the verdict asks for the comparison


def test_line_section_opens_with_an_overview_comparison():
    ctx = _mini_ctx()
    d = vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted"
    ctx["overview_old"] = {"idx": "overview", "img": d / "overview.png", "facet": {}}
    ctx["overview_new"] = {"idx": "overview", "img": d / "overview.png", "facet": {}}
    ctx["overview_diff"] = None
    out = vp.render_html(ctx)
    assert 'id="overview-row"' in out
    # it must sit AFTER the last facet row and BEFORE the first line row
    assert out.index('id="facet-row-5"') < out.index('id="overview-row"')
    assert out.index('id="overview-row"') < out.index('id="line-row-0"')
    # and it is a reference, not a graded row
    ov = out.split('id="overview-row"')[1].split("</section>")[0]
    assert ":verdict" not in ov
    assert "not counted toward completeness" in ov


def test_overview_is_absent_when_there_is_no_overview_render():
    ctx = _mini_ctx()
    out = vp.render_html(ctx)
    assert 'id="overview-row"' not in out


def test_provenance_tracks_the_pngs_not_the_directory():
    # Writing the pass INTO the render folder made the folder's newest commit
    # the pass's own, and the header then credited the wrong commit for the
    # renders. The pathspec must be the PNGs.
    import inspect
    src = inspect.getsource(vp.render_provenance)
    assert "facet-*.png" in src and "overview.png" in src
    d = vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted"
    prov = vp.render_provenance(d)
    if prov["known"]:
        # the renders were committed by the grid-adoption commit, not by any
        # later commit that merely added a review page beside them
        assert prov["short"] == "7811b3bce38a", prov
