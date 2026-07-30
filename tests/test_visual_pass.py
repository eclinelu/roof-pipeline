# Tests for the visual-pass harness.
#
# The r2-vs-grid-adopted pass is 29 clean 1-to-1 rows, so running it exercises
# ONE of the five required layout cases. The other four -- merge, split, new,
# vanished -- are built but never touched by that artifact pair, and a layout
# that has never once been executed is a layout that does not work. These tests
# drive all five through synthetic index sets, where the right answer is known
# by construction rather than by inspection.
import json
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


def test_content_bbox_finds_the_ink_and_reports_the_gain(tmp_path):
    from PIL import Image
    import numpy as np
    a = np.full((200, 400, 3), 255, np.uint8)
    a[20:60, 100:300] = 0                     # 200x40 of ink in a 400x200 frame
    p = tmp_path / "t.png"
    Image.fromarray(a).save(p)
    bb = vp.content_bbox(p, pad=0)
    assert (bb["x0"], bb["y0"], bb["w"], bb["h"]) == (100, 20, 200, 40)
    assert bb["used_pct"] == pytest.approx(10.0)
    assert bb["gain"] == pytest.approx(10.0)


def test_content_bbox_is_a_no_op_on_a_full_frame(tmp_path):
    from PIL import Image
    import numpy as np
    a = np.zeros((100, 100, 3), np.uint8)
    p = tmp_path / "full.png"
    Image.fromarray(a).save(p)
    bb = vp.content_bbox(p, pad=0)
    assert bb["gain"] == pytest.approx(1.0)


def test_crop_css_maps_the_content_rect_onto_the_pane():
    # The browser math, checked in Python: with a pane C px wide, the content
    # rectangle must land at (0,0) and exactly fill the pane.
    bb = {"x0": 721, "y0": 25, "w": 1093, "h": 440, "img_w": 1950, "img_h": 1650}
    C = 700.0
    img_w_px = C * (100.0 * bb["img_w"] / bb["w"]) / 100.0
    scale = img_w_px / bb["img_w"]
    box_h = C * bb["h"] / bb["w"]                       # from aspect-ratio w/h
    left_px = C * (-100.0 * bb["x0"] / bb["w"]) / 100.0
    top_px = box_h * (-100.0 * bb["y0"] / bb["h"]) / 100.0
    assert left_px == pytest.approx(-bb["x0"] * scale)  # content x0 lands at 0
    assert top_px == pytest.approx(-bb["y0"] * scale)   # content y0 lands at 0
    assert bb["w"] * scale == pytest.approx(C)          # and fills the pane
    assert bb["h"] * scale == pytest.approx(box_h)


def test_facet_4_is_the_render_outlier_and_the_crop_recovers_it():
    # The reason cropping exists. If review_render.py is ever fixed, facet 4's
    # frame usage rises and this test failing is the signal to drop the crop.
    d = vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted"
    used = {i: vp.content_bbox(d / f"facet-{i:02d}.png")["used_pct"] for i in range(29)}
    assert min(used, key=used.get) == 4
    assert used[4] < 20.0
    assert sorted(used.values())[1] > 40.0          # nothing else is close
    assert vp.content_bbox(d / "facet-04.png")["gain"] > 5.0


def test_crop_can_be_turned_off():
    pane = {"idx": 4, "facet": {},
            "img": vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted/facet-04.png"}
    out_dir = vp.REPO / "passes" / "a-vs-b"
    assert "cropbox" in vp.pane_html(pane, "NEW", out_dir, crop=True)
    assert "cropbox" not in vp.pane_html(pane, "NEW", out_dir, crop=False)
    # either way the full render stays one click away
    for c in (True, False):
        assert "facet-04.png\" target=\"_blank\"" in vp.pane_html(pane, "NEW", out_dir, crop=c)


def test_a_cropped_pane_always_says_it_is_cropped():
    # A review instrument that silently alters what you see is worse than one
    # that shows you a bad frame.
    pane = {"idx": 4, "facet": {},
            "img": vp.REPO / "reports/big_house/review/2026-07-30-grid-adopted/facet-04.png"}
    out = vp.pane_html(pane, "NEW", vp.REPO / "passes" / "a-vs-b", crop=True)
    assert "cropbox" in out and "cropnote" in out and "cropped" in out


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
    assert out.count(":compare") >= 2 * (len(rows) + 2)
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
