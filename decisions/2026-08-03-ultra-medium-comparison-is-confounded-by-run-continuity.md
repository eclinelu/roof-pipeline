### 2026-08-03: OPEN DEFECT: the ultra-against-medium density comparison is CONFOUNDED. The pair differs in `pc_quality` AND in run continuity, so 4.23x is not attributable to quality alone

**Defect:** The canonical medium cloud came from a RESUMED run: its `rerun_from`
lists `odm_filterpoints` through `odm_postprocess`. The 2026-08-03 ultra run was
clean, on a freshly prepared dataset. The two runs therefore differ in **two**
respects, not one: the `pc_quality` option, and whether the run computed its
early stages or reused them.

First reported inside
`decisions/2026-08-03-ultra-is-conditional-on-the-memory-configuration.md`.
Promoted here to a tracked open defect because it constrains what may be said
about every number in that comparison.

**What the comparison MAY claim:**

- The ultra cloud contains **90,151,819 points** and the medium canonical cloud
  **21,325,293**, a ratio of **4.23x**. These are counts read from the two
  artifacts and are not in question.
- The two clouds cover the **same scene volume**. This was measured rather than
  assumed: a header-extent assertion failed at 31.9 pct on Z, and rather than
  widen the threshold the question was put to the data, where the p1-p99 spans
  agree to 0.6 pct on X, 0.3 pct on Y and 0.0 pct on Z, with the p1-p99 Z span
  equal at 8.25 in both. The header gap is outlier reach.
- Ultra completed once on this machine under a specific memory configuration.

**What the comparison MAY NOT claim:**

- **That `pc_quality` caused the 4.23x.** It is the leading candidate and it is
  not isolated. A resumed run reuses stage outputs computed earlier, under
  whatever code, options and inputs were in force at that time, and those
  outputs are upstream of densification. The density ratio is therefore
  attributable to the PAIR of differences, not to the option.
- **That any defect is fixed.** Per the standing density rule, a defect that
  vanishes on a denser cloud is DENSITY-DEPENDENT, not fixed.
- **Any accuracy improvement.** big_house is the development site and carries no
  accuracy claim. More points is a density fact.

**Why this is worth an entry rather than a footnote.** The run was checked for
"one change only" by diffing the two `log.json` option dictionaries, 91 options
per side, exactly one difference, `pc_quality: medium -> ultra`. That check is
sound and it is **not sufficient**, and the gap is the instructive part: an
option diff compares what the two runs were ASKED to do. It cannot see that one
of them did not actually execute its early stages. Continuity is not an option
and so does not appear in the dict being diffed. A control that looks complete
and is blind in one direction is more dangerous than no control, because it
licenses the causal claim it cannot support.

**POWER CHECK, could this have come out the other way.** Yes. `rerun_from` is a
recorded field in the medium run's `log.json`, and had it been absent or empty
the comparison would have been clean-against-clean and there would be no
confound to log. The claim is read off the run record and is falsifiable against
it. The confound is also removable by experiment: a clean medium run on the same
dataset would isolate `pc_quality`, and its density either lands near 21.3
million, which would leave continuity doing little work, or it does not, which
would show continuity matters. **That run is NOT proposed or scheduled here.**

**Cost if wrong:** low as recorded, because this entry withdraws no number. It
narrows a claim rather than replacing one. The cost of NOT recording it is a
causal statement, "ultra gives 4.23x the points", entering the record with
nothing marking that it was never isolated.

**Not done here:** no ODM run is launched, no cloud is rebuilt, and the analysis
pass on the ultra cloud is not started.

**Attribution.** The `rerun_from` observation is from the ultra reconstruction
session. The reading that an option diff is structurally blind to run continuity
is mine. The instruction to state the may and may-not boundary is Emmett's.
