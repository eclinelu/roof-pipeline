### 2026-07-27: Two permanent changes to the review loop, from pass 2 onward: a blind diff, and free text instead of multiple choice

**Decision:** Two changes to how every future review pass works, adopted after
pass 1 and applying from pass 2.

---

**A. EVERY PASS PRODUCES A DIFF AGAINST THE PREVIOUS ARTIFACT, AND THE DIFF IS
HIDDEN BY DEFAULT.**

Per facet: point count, pitch, plan area, gross area, quality and component
count, each as old value, new value, delta. Plus a VISUAL diff, the previous
outline and the new outline overlaid on the same render, so a boundary that
moved is visible as movement rather than inferred from two pictures. Plus a
summary naming the facets that changed by more than noise and the facets that did
not change at all.

**THE DIFF SITS BEHIND A TOGGLE, DEFAULT OFF**, exactly like the pitch and area
numbers.

**Why the toggle is the important half.** The reviewer grades the new render
BLIND, then reveals. Emmett's reason, stated directly: if he sees "facet 3
changed" before grading facet 3, his verdict is about the diff rather than about
the roof. A diff shown before the judgement turns a review into a check on
whether the fix did what it intended, which is a different and much weaker
question than whether the outline matches the building. It is the same principle
already applied to pitch and area, and the same principle as
ground-truth-is-audit-only (`2026-07-14-ground-truth-audit-only.md`), applied to
the reviewer rather than to the code.

The facets that did NOT change are as important as the ones that did, which is
why they are named rather than omitted. A fix that was supposed to be a no-op on
18 control facets is only checkable if the no-op is stated.

---

**B. THE REVIEW UI DROPS THE MULTIPLE CHOICE. ONE FREE-TEXT BOX PER FACET,
NOTHING ELSE.** Same for lines and for missing facets.

**PASS 1 IS THE EVIDENCE, AND IT IS UNAMBIGUOUS. EVERY TIME THE CODE AND THE NOTE
DISAGREED, THE NOTE WAS RIGHT.**

    the `merge` code was used in two OPPOSITE senses: "this is half of one real
      plane" (M3) and "this facet absorbed foreign material" (M1b). Facets 9 and
      10 meant the second; the schema defined only the first.

    facets 21 and 26 carry `correct` while their own partners' notes describe
      them as halves of a split pair.

    six line rows carry no verdict and the unambiguous note "does not exist".

The structured field lost information that the free text kept. It did not merely
fail to capture nuance; it recorded, in machine-readable form, the OPPOSITE of
what the reviewer meant, in a field that downstream analysis would have trusted
over the prose.

A structured vocabulary has to be right before the first use, and pass 1 shows it
was not. Designing a better vocabulary from one pass would be fitting the
categories to what was already seen, which is the same error as fitting a
threshold to a result.

**Kept:** the render close-ups, the overview inset, the numbers toggle, keyboard
next and previous, and autosave.

---

**THE CONSEQUENCE, HANDLED EXPLICITLY RATHER THAN ABSORBED.**

Mechanism attribution now runs through Claude reading Emmett's prose. That is
already what happened in the pass 1 triage, where the mechanism list was built
from the notes and not from the codes. **The change makes it visible instead of
incidental, and it needs its own rule, because an interpretation step that nobody
declared is exactly where a reviewer's judgement gets quietly replaced.**

The rule:

- Claude PROPOSES an attribution for each note and SHOWS IT for confirmation.
- Never infer a verdict from wording silently.
- Never fill a blank because the note seems clear.

The third clause already held in practice and is being generalised, not
invented: the six line rows with "does not exist" notes were left blank rather
than scored `spurious`, because reconstructing a reviewer's verdict from their
prose is the analyst substituting a judgement for the reviewer's. That was the
right call on six rows and it is now the rule everywhere.

**A known cost, stated rather than discovered.** Free text removes the ability to
count verdicts directly, so pass-over-pass comparison of "how many facets were
correct" is no longer mechanical. That is accepted: pass 1 showed the counts were
partly wrong anyway, and a mechanical count of a miscoded field is worse than an
honest reading of prose. The stopping rule in
`2026-07-27-defect-triage-protocol.md` is unaffected, because it counts NEW
MECHANISMS, not verdicts.

---

**Rejected:**
- Keeping the codes and adding an `absorbed` option. Fixes the one collision that
  was noticed and leaves the general problem, which is that a fixed vocabulary
  built before the failure modes are known will keep mismatching them. The
  `absorbed` code is still added for pass 2 as a way of flagging the pass 1 rows,
  but it is not the answer.
- Codes plus mandatory free text. Pass 1 already had both, and the codes still
  captured the opposite of what the notes said. When the two disagree the code is
  the one downstream analysis reads first, which is the wrong default.
- Showing the diff alongside the render with a warning not to look. A warning is
  not a control.

**Cost if wrong:** if free text turns out to be too loose to attribute reliably,
the loss is one pass of attribution effort and the notes remain fully readable.
Nothing is destroyed, because prose is the more complete record in either case.

**Evidence:** `reviews/big_house/review-2026-07-27.json`, specifically the
`schema_note_for_pass_2` block recording the three code/note disagreements, and
the six line rows with notes and no verdict.

**Attribution:** both changes, the blind-diff requirement and its reason, the
decision to drop multiple choice, the reading that the note was right every time
it disagreed with the code, and the three-clause rule on attribution, are
Emmett's, stated directly. The rejected alternatives and the note on the counting
cost are Claude's.
