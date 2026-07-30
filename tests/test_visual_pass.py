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


def test_html_renders_all_five_layout_cases():
    # Drives render_html over a context holding every case, so a template break
    # in the merge/split/new/vanished branches fails here rather than silently
    # producing a page with an empty pane where a finding should be.
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
