### 2026-07-30: CORRECTION: big_house was reconstructed at `pc_quality=medium`, not `high`, and the 67.14 / 60.10 capture comparison is confounded by that

**Decision:** Correct two claims in the record. Nothing is retracted and no
measurement is withdrawn; both figures remain true of their own clouds. What
changes is what they are allowed to be used as evidence for.

**Corrects, and does not reverse:**
`2026-07-30-ultra-becomes-the-odm-default.md`, written earlier the same day,
which states that `--pc-quality ultra` replaces `high`. That is right for
bungalow and cove_house and WRONG for big_house. It is corrected here rather
than edited there, because the log is append only.

**What the ODM logs actually record.** Read from each dataset's own `log.json`,
which is ODM's record of the fully resolved options for the run that produced
the cloud:

| dataset | `pc_quality` | `skip_3dmodel` | role |
| --- | --- | --- | --- |
| **big_house** | **medium** | False | DEVELOPMENT site, every frozen artifact |
| **bungalow** | **high** | True | HELD-OUT validation |
| **cove_house** | **high** | True | HELD-OUT validation |
| tyco_house | medium | False | not in the current scope |

All four ran ODM 3.6.0 with `feature_quality=high` and
`min_num_features=10000`.

**Correction 1: the baseline was medium, so ultra is a TWO-step jump for
big_house and a one-step jump for bungalow.** Every committed big_house artifact
(`canonical-2026-07-26-r2`, `canonical-2026-07-28-grid`,
`canonical-2026-07-30-grid-adopted`, the 2026-07-18 scored deliverable, every
capture metric) was computed on a `medium` cloud. The skill file
`.claude/skills/odm-run/SKILL.md` also says "previously `high`" as of commit
`155d2c1`; that sentence describes the skill's own documented default, which was
never the setting big_house was actually built at.

**Correction 2, the one that matters: the raw-versus-raw capture comparison
cannot separate capture habits from reconstruction setting.** The record
currently reads, in `STATE.md` and in the 2026-07-29 capture recompute, that
raw-vs-raw gives **bungalow 67.14 pct against big_house 60.10 pct**, "so the
operator-and-habits reading survives, bungalow still the better capture by about
7 points."

Those two clouds were built at DIFFERENT `pc_quality`: bungalow at `high`,
big_house at `medium`. A one-step `pc_quality` difference is a plausible cause
of a gap of that size on its own. **Capture habits and reconstruction setting
are therefore fully confounded in that 7-point gap, and the measurement cannot
attribute it to either.**

**This does NOT say the operator-and-habits reading is wrong.** It says the
comparison is not evidence for it. The reading may well be right and may be
supported by other observations; what it cannot lean on is this number. The
phrase "recomputed on the same config" in the 2026-07-29 work is accurate about
the ANALYSIS config, which was genuinely held fixed on both sides, and it is
that accuracy which made the reconstruction difference easy to miss: the
sentence is true, and the thing it does not mention is the thing that matters.

**Why this was missed until now:** nothing in the analysis chain reads
`pc_quality`. The capture probe recomputes both sides through one code path with
one set of parameters and correctly reports that it did, so every assertion it
carries passes. The confound sits UPSTREAM of the first line of project code, in
the artifact the project treats as its input. This is the silent-failure shape
(`2026-07-27-silent-failure-standing-rule.md`) one level further out than any
assertion so far reaches: the diagnostic verified everything it could see, and
the difference was outside its field of view.

**Consequence, and the new requirement:** **any figure derived from a point
cloud must state the `pc_quality` of the cloud it came from, and no two such
figures may be differenced unless those settings match.** This is now written
into `.claude/skills/odm-run/SKILL.md`. It applies retrospectively: the
pre-2026-07-30 capture numbers stay in the record as true of their own clouds
and stop being usable as cross-site evidence.

**Evidence:** `C:\odm\datasets\<dataset>\log.json`, `options.pc_quality`, for
all four datasets, read directly. ODM's `log.json` is already established in
this project as ground truth for what a run actually did
(`.claude/skills/odm-run/SKILL.md`, the PoissonRecon section).

**Cost if wrong:** near zero. If the settings were somehow misread, the fix is a
third entry and no measurement moved. The cost of NOT recording it is a
confounded number continuing to circulate as a clean cross-site finding, which
is precisely the failure this log exists to prevent.

**What this changes about the ultra work in progress:** nothing about the plan.
Rebuilding big_house and bungalow at ultra is what puts the sites on ONE
reconstruction setting for the first time, which is the condition under which a
cross-site capture comparison becomes meaningful at all. It does change the
reporting: the big_house comparison is medium-to-ultra, the bungalow one is
high-to-ultra, and those two deltas are not comparable to each other either.

**Attribution.** Emmett directed that the record be corrected by a new entry
once the discrepancy was reported. The discovery, the confound analysis and the
"state the pc_quality of both sides" requirement are mine. Emmett has not stated
a view on whether the operator-and-habits reading survives without this number.
