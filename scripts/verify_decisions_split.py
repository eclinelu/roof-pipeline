"""Prove that no pre-split decision entry has ever been edited.

DECISIONS.md used to be one file: a "Current state" block on top, then an
append-only log of decision entries newest-first. It was split into STATE.md
(the state block) and decisions/<date>-<slug>.md (one file per entry).

Those entries are evidence. The whole point of an append-only log is that
nobody quietly edits it, so the claim has to be provable rather than merely
promised. This script rebuilds the ORIGINAL 29-entry block from the split
pieces and diffs it against the last committed version of DECISIONS.md, which
git keeps forever even though the file no longer exists in the working tree.

WHY IT CHECKS THE ORIGINAL ENTRIES AND NOT THE WHOLE FILE (changed 2026-07-26).
The first version reassembled the entire original file, every indexed entry
plus the current STATE.md, and diffed the lot. That could only ever pass at
the exact moment of the split:

  - Appending a new decision made the rebuilt file longer than the original,
    so the check failed the first time the log was used as intended. A
    verification that fails when you use the thing correctly gets switched off,
    and then it protects nothing.
  - STATE.md is explicitly OVERWRITE-IN-PLACE. Diffing it against a historical
    snapshot asserts it never changed, which is the opposite of its contract.

The durable invariant is narrower and stronger: the entries that existed at
the split are byte-identical and still in the same relative order, and every
entry added since sits ABOVE them in the index (append at the top, newest
first). That claim stays checkable for the life of the project, which is the
only kind of claim worth automating.

Run it any time you want the proof again:

    python scripts/verify_decisions_split.py

Exit code 0 means no pre-split entry has been edited, reordered, renamed or
dropped, and every later entry was appended above them. Non-zero means one of
those things happened.
"""
import difflib
import io
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The original file's h1 and the separator between its blocks. These are the
# only two pieces of the original that live in neither STATE.md nor an entry
# file, so they are recorded here to make reassembly exact.
TITLE = "# Decisions and State\n\n"
SEP = "\n\n---\n\n"
INDEX_MARKER = "## Entries (newest first)"


def git(*args):
    return subprocess.run(
        ["git", "-C", REPO] + list(args),
        capture_output=True, text=True, check=True,
    ).stdout


def read(path):
    with io.open(path, encoding="utf-8", newline="") as f:
        return f.read()


def original_from_git():
    """The last committed DECISIONS.md, found without hardcoding a commit hash.

    Walks back through the commits that touched the file and takes the newest
    one where it still EXISTS. The newest such commit is the deletion commit
    once the split is committed, and the file is already gone there, so simply
    taking the newest match would break the day the deletion lands.
    """
    revs = git("rev-list", "HEAD", "--", "DECISIONS.md").split()
    for rev in revs:
        exists = subprocess.run(
            ["git", "-C", REPO, "cat-file", "-e", f"{rev}:DECISIONS.md"],
            capture_output=True,
        ).returncode == 0
        if exists:
            blob = subprocess.run(
                ["git", "-C", REPO, "show", f"{rev}:DECISIONS.md"],
                capture_output=True, check=True,
            ).stdout.decode("utf-8")
            return rev, blob
    sys.exit("DECISIONS.md not found anywhere in history; cannot verify.")


def index_names():
    """The entry filenames, in the order the index lists them (newest first).

    Order comes from the index, not from sorting filenames: several entries
    share a date, so filename order cannot recover the sequence."""
    readme = read(os.path.join(REPO, "decisions", "README.md"))
    head, _, listing = readme.partition(INDEX_MARKER)
    if not listing:
        sys.exit("decisions/README.md is missing its entry index.")
    names = re.findall(r"^- \[.+?\]\((.+?\.md)\)$", listing, re.M)
    if not names:
        sys.exit("decisions/README.md index lists no entries.")
    # The log's own header, restored to the blank line that separated it from
    # the first entry in the original file.
    return names, head.rstrip("\n") + "\n\n"


def entry_text(name):
    """One entry file, minus the trailing newline. Files are stored with one
    for hygiene; the original file had none between an entry and its `---`."""
    text = read(os.path.join(REPO, "decisions", name))
    assert text.endswith("\n"), name
    return text[:-1]


def entry_header(text):
    """The `### YYYY-MM-DD: title` line that identifies an entry."""
    m = re.search(r"^### (\d{4}-\d{2}-\d{2}: .+)$", text, re.M)
    return m.group(1) if m else None


def main():
    rev, original = original_from_git()
    names, log_header = index_names()

    # The entries the original file contained, in its order.
    original_headers = re.findall(r"^### (\d{4}-\d{2}-\d{2}: .+)$", original, re.M)

    on_disk = sorted(
        f for f in os.listdir(os.path.join(REPO, "decisions"))
        if f.endswith(".md") and f != "README.md"
    )
    print(f"original: DECISIONS.md at commit {rev[:9]}  "
          f"({len(original_headers)} entries, {len(original)} bytes)")
    print(f"now:      {len(names)} entries indexed, {len(on_disk)} files on disk")

    if len(set(names)) != len(names):
        print("FAIL: an entry file is listed twice in the index")
        return 1
    if on_disk != sorted(names):
        print("FAIL: decisions/ contents do not match the index")
        print("  only on disk:", sorted(set(on_disk) - set(names)))
        print("  only indexed:", sorted(set(names) - set(on_disk)))
        return 1

    # Map each indexed file to the entry it holds, then split the index into
    # the pre-split entries and everything appended since.
    by_header, missing_header = {}, []
    for name in names:
        h = entry_header(entry_text(name))
        if h is None:
            missing_header.append(name)
        else:
            by_header.setdefault(h, name)
    if missing_header:
        print("FAIL: entry file(s) with no `### date: title` heading:",
              missing_header)
        return 1

    absent = [h for h in original_headers if h not in by_header]
    if absent:
        print(f"FAIL: {len(absent)} pre-split entr(ies) no longer on disk:")
        for h in absent:
            print("   ", h)
        return 1

    original_names = [by_header[h] for h in original_headers]
    new_names = [n for n in names if n not in set(original_names)]
    print(f"          {len(original_names)} pre-split, {len(new_names)} added since")

    # APPEND-ONLY ORDER: everything added since the split must sit ABOVE every
    # pre-split entry in the index. Newest first is the log's contract, so a new
    # entry appearing below an old one means the index was not appended to, it
    # was rearranged.
    first_old = min(names.index(n) for n in original_names)
    late = [n for n in new_names if names.index(n) > first_old]
    if late:
        print("FAIL: entr(ies) added after the split are listed BELOW a "
              "pre-split entry, so the index was reordered rather than "
              "appended to:", late)
        return 1

    # THE INVARIANT: rebuild the pre-split entry block, in the original order,
    # and diff it against what the original file actually held. STATE.md is
    # deliberately excluded: it is overwrite-in-place, so it has no losslessness
    # claim to make.
    _, _, original_log = original.partition(SEP)
    rebuilt_log = log_header + SEP.join(entry_text(n) for n in original_names) + "\n"

    diff = list(difflib.unified_diff(
        original_log.splitlines(keepends=True),
        rebuilt_log.splitlines(keepends=True),
        fromfile=f"DECISIONS.md entry block (git {rev[:9]})",
        tofile="decisions/* pre-split entries, reassembled",
        n=1,
    ))

    print()
    if diff:
        print("DIFF -- a pre-split entry HAS been edited:")
        sys.stdout.writelines(diff)
        return 1

    print(f"DIFF: empty. All {len(original_names)} pre-split entries are "
          f"byte-for-byte identical and in their original order;")
    print(f"      {len(new_names)} later entr(ies) appended above them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
