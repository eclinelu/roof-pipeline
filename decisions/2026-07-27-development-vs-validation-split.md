### 2026-07-27: big_house becomes the DEVELOPMENT site; bungalow and cove_house are held out for validation

**Decision:** big_house is the DEVELOPMENT site. Visual inspection of it is
unlimited, iteration on it is unlimited, and NO ACCURACY CLAIM EVER COMES FROM
IT. bungalow and cove_house are HELD-OUT VALIDATION sites: the rules are frozen
before either is run, and each is scored ONCE.

**Why, stated as the failure it responds to.** Four errors were made in a single
working session on 2026-07-27, two by Claude and two by Emmett: a re-peel
contaminated by RANSAC stream position, a wrong claim that the completeness
invariant predated the 2026-07-18 freeze, an "inflation" reading of alpha-shape
area that was backwards, and an instruction not to attribute a fringe of
footprint cells that turned out to be real. Every one of them was an attempt to
reason about the geometry of a physical roof through summary statistics.

The one time anyone looked at a picture, blob 0 resolved in a single glance, AND
the same picture carried a second finding (the unassigned fringe around the
facets) that no amount of residual analysis had surfaced. The instrument was not
the problem. Looking was missing.

So visual review becomes a first-class instrument, and it is quarantined to one
site.

**THE COST IS SMALLER THAN IT LOOKS.** big_house was never going to validate
area. Its tape measurement gave a LENGTH, used to set scale; no measured AREA
exists for that property. The scored artifact says so in its own words: "NO
measured area exists for this property, so area itself is NOT validated against
ground truth" (`comparison-2026-07-18-scored-2026-07-18.json`). Giving up an
accuracy claim that was never available costs nothing.

What the frozen big_house artifact keeps being good for is real and unaffected:
cloud-unit geometry, the scale cross-check at +1.92 percent, the pitch comparison
against inclinometer readings, reproducibility, and the whole record of how the
pipeline was built. None of that depends on treating it as unseen.

**THE COST THAT IS REAL: roger is lost.** That leaves exactly TWO held-out sites
and ONE attempt at each. There is no third chance and no site in reserve. Every
rule must be frozen before bungalow runs, and a rule changed after seeing
bungalow spends cove_house. This is the binding constraint on everything that
follows and it should be stated in any report that quotes a validation number.

**COVERAGE ON big_house BECOMES A DEVELOPMENT READOUT, NOT A SCORE.** Every rule
change driven by visual review will raise it, because visual review finds
unexplained real roof and rules that claim it move cells from unexplained to
explained. A number that can only go up under the process generating it is not a
score. It stays useful as a pointer to where to look next, which is what it will
be used for.

Its value as a DETECTOR is not lost, it is relocated: facet coverage on bungalow
and cove_house, computed once each after the rule freeze, is a real measurement
of completeness on unseen data. That is where the 88.40 percent number's
descendants get to mean something.

The published 88.40 percent on `canonical-2026-07-26-r2` STANDS as the frozen
historical number for that state. It is not restated, not recomputed, and not
superseded by anything found during development. It is what the pipeline scored
on the day, and the entry confirming blob 0 as real roof
(`2026-07-27-blob0-confirmed-roof.md`) is the evidence that the detector worked.

**THE STANDING LIMIT ON THE INSTRUMENT, which is what keeps this honest.**

Visual review can establish THAT something is wrong and WHAT it is physically. It
can NEVER set a parameter value.

Every fix still needs a mechanism that would have been true if Emmett had never
looked, and every threshold still needs its own plateau test. Looking tells you
where to point the instrument. It is not the instrument.

The precedent is already on record and was set before this decision:
`2026-07-14-ground-truth-audit-only.md` (ground truth is audit-only, never a
pipeline input) and `2026-07-27-blob0-confirmed-roof.md`, where Emmett's eye
identified blob 0 as real roof and NOT ONE THRESHOLD MOVED. The eye supplied a
fact about the building. It supplied no number.

The same day supplied the counter-example that shows the limit has teeth. A
boundary-erosion fix, proposed from a real measured profile, was tested as a
population property across all 29 facets and REFUTED: the quality bar falls by
0.239 under symmetric erosion while blob 0's score moves by 0.001, so it never
passes at any width (`boundary-erosion-population-2026-07-27.json`). Visual
review said blob 0 is roof, and that remains true. It said nothing about how to
admit it, and the first mechanism proposed turned out to be wrong.

**Rejected:**
- Keeping big_house as a validation site and rationing inspection of it.
  Rationing is not enforceable and not checkable by a later reader. A site is
  either seen or it is not.
- Treating cove_house as a second development site because it is already
  reconstructed. That would leave one held-out site, and a single validation site
  gives no way to tell a real result from a lucky one.
- Declaring this after the review pass. The declaration has to be committed
  BEFORE anyone looks, or it is a description of what happened rather than a
  constraint on it.

**Cost if wrong:** if big_house turns out to be the only site that ever produces
a usable cloud, this decision forfeits the project's only accuracy claim.
Mitigation: the frozen 2026-07-18 artifact and its scale and pitch results are
untouched and stay quotable, with their existing caveats.

**Evidence:** `comparison-2026-07-18-scored-2026-07-18.json` (the `area_claim`
field); `boundary-erosion-population-2026-07-27.json`; the 2026-07-27 session
record.

**Attribution:** the decision, the development/validation split, the four listed
reasons and the standing limit on visual review are Emmett's, stated directly.
The framing of the four-error diagnosis and the wording are Claude's. That roger
is lost is Emmett's statement.
