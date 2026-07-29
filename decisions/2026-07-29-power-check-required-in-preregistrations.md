### 2026-07-29: TEMPLATE CHANGE: every pre-registered prediction carries a POWER CHECK alongside its direction

**Decision:** the pre-registration template gains a required **POWER CHECK**
field. For each prediction, alongside its DIRECTION, the entry must state what
would have to be true for the test to SEPARATE its hypotheses at all: the spread
of the data against the size of the effect, and the number of independent
samples. **The arithmetic is done before the run, not after.**

**Layer changed, listed as the decision-log skill requires for propagation:**
`.claude/skills/decision-log/SKILL.md`, new section "PRE-REGISTRATION entries:
two extra required fields". Recorded here so the template change and its reason
are in the append-only log and not only in an overwritable skill file.

**This is a template change, not a one-off note about one bad test.**

---

## THE FAILURE THAT PROMPTED IT

`2026-07-29-preregistration-pitch-bias-mechanism.md` pre-registered a shape
discriminator with scoring bands fixed before the number existed, which is
exactly the discipline this project has been building. It was still worthless,
and for a reason nobody checked:

    what the two hypotheses predict     ratio 1.00 (constant) vs 0.70 (stretch)
    the difference to be detected       0.30
    within-cluster spread of the data   1.02 deg on the steep cluster alone
    independent samples                 FOUR facets per cluster
    standard error on a cluster mean    about 0.19 deg

**The test could not have separated its hypotheses whatever the answer came out
to be.** It duly returned "NEITHER SHAPE FITS", which looks like a result and
carries no information.

**And pre-registering it made that worse, not better.** A verdict that is
pre-registered, scored against bands fixed in advance, and reported without
reinterpretation, arrives wearing every marker of rigour this project uses to
decide what to trust. The rigour was real and the content was empty. **A rigorous
procedure applied to an underpowered test launders noise into a finding.**

---

## THE SECOND, WORSE INSTANCE, FOUND THE SAME DAY

The stripe test in the same pre-registration was underpowered in a deeper way:
not short of samples, but **unable to produce a positive result at all under the
hypothesis it was testing.** MVS reconstruction smooths, so a sawtooth below the
resolving power is averaged away, and the hypothesis requires exactly that
averaging in order to produce the bias. The test asked whether the cloud contains
relief that the mechanism says the reconstruction removes.

See `2026-07-29-sawtooth-accepted-untested-known-limit.md`. **The power check
must therefore cover both kinds:** is the effect large enough relative to the
noise and the sample size, AND is a positive result available at all under the
hypothesis.

---

## WHY IT BELONGS IN THE TEMPLATE RATHER THAN IN A HABIT

Both failures were invisible until after the run, and both were cheap arithmetic
beforehand. A field in the template is checked every time; a habit is checked
when someone remembers, and the sessions where it matters most are the ones with
the most going on.

**Same family as the silent-failure standing rule
(`2026-07-27-silent-failure-standing-rule.md`), one level up.** That rule asks
whether a diagnostic could notice it was measuring the wrong thing. This asks
whether a test could notice which of its own hypotheses is true. **Both fail
silently, and both fail in the reassuring direction**, which is what makes them
worth structural enforcement rather than good intentions.

The register's row-7 and row-8 class is the same shape again at the instrument
level: a perturbation aligned with the defect's own period cannot see the defect.
Three instances, three levels, one pattern: **a test whose design forecloses the
answer it is looking for.**

---

## WHAT THE FIELD LOOKS LIKE IN PRACTICE

Not a formal statistical apparatus. Two or three lines per prediction:

    P3 PITCH, direction: none claimed.
       POWER CHECK: per-facet pitch is measured to 4 dp and the frozen numbers
       carry 0.81 deg of headroom, so any delta above about 0.001 deg is
       separable and the test has ample power. 8 independent facets.

    5b SHAPE, direction: ratio 1.00 vs 0.70.
       POWER CHECK: FAILS. Within-cluster spread 1.02 deg, 4 facets per
       cluster, standard error 0.19 deg on each mean, against a 0.30
       separation in the ratio. This test cannot distinguish the hypotheses.
       Either find more facets or do not run it.

**A prediction whose power check FAILS is not automatically dropped.** It is run
and reported with the failure attached, or it is redesigned, and either is
better than discovering it afterwards. What is forbidden is reporting its verdict
as though it meant something.

---

**Rejected:**

- **Treating the 5b failure as a one-off to note in the results entry.** It was
  already noted there; noting it again would change nothing about the next
  pre-registration.
- **A full statistical power calculation.** Overkill for eight facets and a
  barrier to actually doing it. The useful version is arithmetic on the back of
  an envelope, which is all that was needed here.
- **Adding it as guidance prose rather than a required field.** The project's own
  evidence is that rules the agent is asked to remember get dropped under load,
  and the fix is structural: the silent-failure rule works because every probe
  carries a named assertion, not because everyone means well.

**Evidence:** `reports/big_house/pitch-bias-score-2026-07-29.json` for the 5b
numbers; `decisions/2026-07-29-pitch-bias-sawtooth-refuted.md` for the scoring;
`reports/silent-failures/README.md` rows 7 and 8 for the instrument-level
instance of the same pattern.

**Cost if wrong:** the field adds a few lines to each pre-registration and could
occasionally discourage a cheap test that would have been worth running anyway.
Since a failed power check does not forbid running the test, only reporting its
verdict as meaningful, that cost is close to zero.

**Attribution:** the instruction to log the power finding as a template change
rather than a one-off, the observation that a pre-registered test which cannot
separate its own hypotheses produces a confident-looking result meaning nothing,
and the placement of it as the same family as the silent-failure rule one level
up, are all Emmett's. The two-kinds distinction (insufficient samples versus no
positive result available under the hypothesis), the worked example format, and
the note that a failed power check does not forbid running the test, are Claude's.
