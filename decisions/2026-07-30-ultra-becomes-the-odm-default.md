### 2026-07-30: `--pc-quality ultra` becomes the ODM default, both held-out sites are rebuilt on it, and a defect that vanishes on a denser cloud is DENSITY-DEPENDENT rather than fixed

**Decision:** `--pc-quality ultra` is the production ODM setting from now on,
replacing `high`. big_house is reprocessed into a SEPARATE dataset
`big_house_ultra`, and bungalow is reconstructed at ultra as well. **Only
`--pc-quality` changes.** `--feature-quality` stays at `high`,
`--min-num-features` and every other flag stay at ODM's defaults.

**Why:** Capture quality was established as PERMANENT and per-site: big_house
and bungalow both measure capture-sparse, blob 0's region reads 68.18 pct
density-testable against 83.37 pct for the rest of the roof, and that shortfall
is explicitly the part an analysis change cannot repair. No segmentation,
threshold or boundary work can add points that were never reconstructed. If
density is the binding constraint on several open mechanisms, then the cheapest
correct move is to stop paying for the sparse cloud everywhere downstream and
rebuild once at the density the project actually needs. Runtime roughly doubles,
once, at reconstruction; the alternative is discovering the shortfall repeatedly
in analysis, or re-flying, which costs a flight.

Reasoning is mine, assembled from findings Emmett has already accepted; he
directed the change rather than stating this justification.

**Rejected:**

| Option | Why it lost |
| --- | --- |
| Keep `high` as default, escalate to `ultra` per site | This was the previous rule. It makes density an ad hoc per-site decision, so no two sites are guaranteed comparable, and it defers the cost to the moment it is most expensive to pay. |
| Rebuild big_house in place | Destroys the only cloud every committed artifact was computed on. Every frozen number becomes unreproducible. A separate `big_house_ultra` dataset costs disk and nothing else. |
| Raise `--feature-quality` too | Two changed flags cannot be attributed. This project's method is attributing a change to its cause, so it changes one thing. |
| Leave bungalow at `high` | Would leave the two held-out validation sites on DIFFERENT reconstruction settings, making the one comparison the project gets between them uninterpretable. |

**THE REVISED DENSITY-DEPENDENT RULE.** A defect that is present on the `high`
cloud and VANISHES on the ultra cloud is recorded **DENSITY-DEPENDENT** and
reported as a **known limit conditional on point density**. It does **NOT**
block the freeze and does **NOT** block the queue.

It is explicitly **NOT** recorded as closed, fixed, or improved. Two reasons,
both of which have to hold for the weaker disposition to be honest:

1. **The mechanism was never identified.** "It stopped appearing when I added
   points" is not a cause. A defect whose cause is unknown can recur for the
   same unknown reason.
2. **Cloud density is not uniform**, neither across one roof nor across sites.
   big_house's own roof already spans 68.18 to 83.37 pct density-testable. A
   defect that disappears where the cloud is dense says nothing about the same
   defect where it is thin, and the held-out sites have their own densities that
   no big_house result can speak for.

**What this replaces.** Under the previous ordering, `high` was production and
`ultra` was an escalation, so a defect that vanished only at ultra had been
observed off the production configuration and could not be dispositioned at all;
it stayed open and blocking. Making ultra production is what creates room for
the middle verdict. **Emmett did not state the prior rule in these words; this
is my reconstruction of what the ordering implied**, recorded so the revision has
something explicit to revise.

**Dispositions are decided AT THE PASS, not at the run.** A reconstruction run
produces a cloud; it does not adjudicate a mechanism. **M1b, M2, M3, M4, M5, M6
and M7 are not closed, fixed, or improved by anything in this entry**, and no
run in this pass may declare them so.

**Bungalow is RECONSTRUCTION ONLY.** The cloud is produced and the work stops
there. No pipeline run, no coverage, no area, no pitch, no facets, and the cloud
is not opened in analysis. bungalow is HELD-OUT VALIDATION with exactly ONE
scored attempt, and spending it here would spend it on a reconstruction change
rather than on the pipeline.

**A COMPARABILITY BREAK, stated so it cannot be missed later.** The raw-versus-raw
capture comparison **bungalow 67.14 pct, big_house 60.10 pct** was computed on
NON-ULTRA clouds. It is **not comparable to any figure produced after this
point.** The same applies to every other density, coverage and capture number in
the record predating this entry, including big_house's 82.72 pct
density-testable and the 227,964 one-point cells. Those remain true OF THEIR OWN
CLOUD and are not superseded; they simply cannot be differenced against an ultra
figure. Any future comparison must state the `--pc-quality` of both sides.

**NO SCORED PREDICTIONS IN THIS ENTRY, deliberately.** This is not an oversight
and it is not an exemption from the pre-registration discipline. An ODM
reconstruction predicts nothing on its own: the honest prior for "what will the
ultra cloud's point count be" is "more", which is unfalsifiable and would be a
pre-registration that could only pass. Under the POWER CHECK rule
(`2026-07-29-power-check-required-in-preregistrations.md`), a prediction that
cannot separate its hypotheses is worse than no prediction, because pre-registering
it makes an empty verdict harder to dismiss. **Scored predictions are therefore
DEFERRED to the analysis pass**, where there is a frozen prior to predict against
and the answer can genuinely go either way.

**The plan-view render gate before ultra is SKIPPED BY DECISION.** Skipped
deliberately, not overlooked. Stated by Emmett on 2026-07-30.

**Evidence:** capture metrics on the adopted grid, `reports/big_house/
capture-refixed-2026-07-29-roof.json` and the 2026-07-30 adoption artifact:
density-testable 82.72 pct, one-point cells 227,964, p10 points per occupied
cell 1.0, blob 0's region 68.18 pct against 83.37 pct elsewhere. The
irreparability of a capture gap by analysis is from
`2026-07-27-erosion-refuted-and-interior-retraction.md` and the blob 0 entries.
The runtime doubling is ODM's documented behaviour and the skill's own table,
not measured by this project until this pass.

**Cost if wrong:** moderate and mostly recoverable. If ultra turns out not to
help, the cost paid is reconstruction time and disk; every pre-ultra cloud and
artifact still exists and is still canonical until something replaces it. The
genuine risk is subtler: making ultra the default means future work is done on
denser clouds than the two held-out sites were captured for, so a pipeline tuned
on ultra big_house could carry an unstated density assumption into a site whose
capture cannot support it. That is exactly what the DENSITY-DEPENDENT
disposition exists to keep visible.

**Affected instruction layers, swept in this pass:** `.claude/skills/odm-run/
SKILL.md` updated in commit `155d2c1` (default flipped to ultra, one-flag rule
and the comparability warning written in). `CLAUDE.md` and the decision log were
checked for the stale `odm_filterpoints` instruction the task expected to find a
third copy of; **there is none**, repo-wide there are exactly two occurrences of
`end-with odm_filterpoints` and both already say NOT to use it.

**Attribution.** The decision to make ultra the default, to reprocess both sites,
to keep bungalow reconstruction-only, the revised density-dependent rule, the
skipped render gate, and the deferral of scored predictions are all Emmett's.
The justification above, the reconstruction of what the rule replaces, the
rejected-options table and the comparability-break framing are mine.
