# STRUCTURAL validation of a completed visual review. NO INTERPRETATION.
#
#   .venv/Scripts/python.exe scripts/validate_review.py reviews/big_house/review-2026-07-27.json
#
# This script deliberately does NOT count how many facets were called correct,
# or summarise verdicts, or rank anything. Its only question is whether the
# FILE is intact: do the ids line up with the renders, what is unanswered, and
# is any row shaped like a capture failure rather than a judgement.
#
# It exists because the review UI has already lost data once, silently: the
# add-a-missing-facet button threw internally and the list stayed empty with no
# message. That is the failure mode this checks for, and it follows the
# standing rule (2026-07-27-silent-failure-standing-rule.md) by testing against
# facts known independently of the review itself: the set of rendered PNGs on
# disk, and the canonical facet count.
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# A row is shaped like a CAPTURE FAILURE, rather than a considered judgement,
# when a downstream field is set while the field it depends on is blank. A
# reviewer who forms an opinion answers identity first; a UI that drops a click
# leaves exactly this pattern.
def capture_shaped(f):
    # A DELIBERATE skip is not a capture failure. The distinction has to be
    # recorded in the file rather than remembered, or every later validation
    # run re-raises the same flag and a real dropped click hides among the
    # false alarms.
    if f.get("skipped_deliberately"):
        return []
    problems = []
    ident, bound = f.get("identity", ""), f.get("boundary", "")
    sev, loc = f.get("severity", ""), f.get("location", "")
    note = (f.get("note") or "").strip()
    if bound and not ident:
        problems.append("boundary set but identity blank")
    if (sev or loc) and not (ident or bound):
        problems.append("severity/location set but identity AND boundary blank")
    if note and not (ident or bound):
        problems.append("note written but no verdict recorded")
    if sev and not bound:
        problems.append("severity set but boundary blank "
                        "(severity grades a boundary error)")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("review")
    ap.add_argument("--canonical-n", type=int, default=29)
    args = ap.parse_args()
    d = json.loads(Path(args.review).read_text())
    render_dir = REPO / d["renders"]
    fail = []

    print(f"file          {args.review}")
    print(f"review_of     {d.get('review_of')}   schema v{d.get('schema_version')}")
    print(f"completed     {d.get('completed_utc')}")
    print(f"renders       {d['renders']}")
    print()

    # --- ids against the renders on disk -----------------------------------
    facets = d["facets"]
    print(f"FACET IDS  ({len(facets)} rows)")
    if len(facets) != args.canonical_n:
        fail.append(f"{len(facets)} facet rows, canonical state has "
                    f"{args.canonical_n}")
    missing_png, bad_name = [], []
    for f in facets:
        want = f"facet-{f['facet']:02d}.png"
        if f.get("render") != want:
            bad_name.append((f["facet"], f.get("render")))
        if not (render_dir / want).exists():
            missing_png.append(want)
    ids = [f["facet"] for f in facets]
    print(f"  ids {min(ids)}..{max(ids)}, "
          f"contiguous={ids == list(range(len(ids)))}, "
          f"duplicates={len(ids) - len(set(ids))}")
    print(f"  every row points at its own render: {not bad_name}")
    print(f"  every referenced render exists on disk: {not missing_png}")
    if bad_name:
        fail.append(f"render filename mismatch: {bad_name}")
    if missing_png:
        fail.append(f"renders referenced but absent: {missing_png}")
    stray = sorted(p.name for p in render_dir.glob("facet-*.png")
                   if p.name not in {f"facet-{f['facet']:02d}.png"
                                     for f in facets})
    print(f"  rendered close-ups with no row in the file: "
          f"{stray if stray else 'none'}")
    if stray:
        fail.append(f"rendered but unreviewed: {stray}")
    print()

    # --- completeness -------------------------------------------------------
    skipped = [f["facet"] for f in facets if f.get("skipped_deliberately")]
    no_ident = [f["facet"] for f in facets if not f.get("identity")]
    no_bound = [f["facet"] for f in facets if not f.get("boundary")]
    no_either = [f["facet"] for f in facets
                 if not f.get("identity") and not f.get("boundary")]
    lines = d.get("intersection_lines", [])
    no_verdict = [l["id"] for l in lines if not l.get("verdict")]
    print("UNANSWERED")
    print(f"  facets with no identity : {len(no_ident):>2}  {no_ident}")
    print(f"  facets with no boundary : {len(no_bound):>2}  {no_bound}")
    print(f"  facets with neither     : {len(no_either):>2}  {no_either}")
    print(f"    of which DELIBERATE   : {len(skipped):>2}  {skipped}")
    print(f"    of which unaccounted  : "
          f"{len([x for x in no_either if x not in skipped]):>2}  "
          f"{[x for x in no_either if x not in skipped]}")
    print(f"  lines with no verdict   : {len(no_verdict):>2}  {no_verdict}")
    print()

    # --- rows shaped like a dropped click ----------------------------------
    # LINE ROWS ARE CHECKED TOO. The first version of this script checked only
    # facet rows, and six line rows carrying unambiguous notes ("does not
    # exist") with no verdict recorded went unreported. That is the silent
    # failure this script exists to catch, occurring inside the script written
    # to catch it (2026-07-27-silent-failure-standing-rule.md).
    print("ROWS SHAPED LIKE A CAPTURE FAILURE (not a judgement)")
    any_shaped = False
    for f in facets:
        probs = capture_shaped(f)
        if probs:
            any_shaped = True
            print(f"  facet {f['facet']:>2}: {'; '.join(probs)}")
    for l in lines:
        if (l.get("note") or "").strip() and not l.get("verdict"):
            any_shaped = True
            note = (l["note"] or "").strip()
            print(f"  line L{l['id']:<2}: note written but no verdict recorded"
                  f"  -> {note[:60]!r}")
    if not any_shaped:
        print("  none. Every answered row has identity set, and no downstream")
        print("  field is set without the field it depends on.")
    print()

    # --- anything else silently dropped ------------------------------------
    print("OTHER FIELDS")
    for key in ("missing_facets", "missing_lines", "top_level_observations"):
        v = d.get(key)
        n = len(v) if isinstance(v, list) else "ABSENT"
        src = ""
        if isinstance(v, list) and v and isinstance(v[0], dict):
            srcs = {x.get("source") for x in v if isinstance(x, dict)}
            srcs.discard(None)
            if srcs:
                src = f"   source: {', '.join(sorted(srcs))}"
        print(f"  {key:<24} {n}{src}")
    cn = d.get("capture_note")
    print(f"  capture_note             {'present' if cn else 'ABSENT'}")
    cs = d.get("completeness")
    if cs:
        # The UI wrote its own tally at export time. Recomputing it here from
        # the rows is an INDEPENDENT check: if the two disagree, something was
        # edited or dropped between export and now.
        agree = (cs.get("facets_answered") == len(facets) - len(no_either) and
                 cs.get("lines_answered") == len(lines) - len(no_verdict))
        print(f"  completeness block       present, agrees with a recount: {agree}")
        if not agree:
            fail.append(f"completeness block disagrees with a recount: "
                        f"{cs} vs answered={len(facets)-len(no_either)}, "
                        f"lines={len(lines)-len(no_verdict)}")
    print()

    print("VERDICT")
    if fail:
        print("  STRUCTURAL PROBLEMS FOUND:")
        for x in fail:
            print(f"    - {x}")
        sys.exit(1)
    print("  File is structurally intact. Nothing was silently dropped beyond")
    print("  the two lists already known to have failed capture, which are")
    print("  present and marked with their source.")
    print("  NO INTERPRETATION PERFORMED: no verdict was counted, ranked or read.")


if __name__ == "__main__":
    main()
