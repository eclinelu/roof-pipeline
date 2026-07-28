### 2026-07-28: CONSTRAINT DISCOVERED THE HARD WAY: raster-based connectivity has a THIRD parameter nobody chose, and it can move a facet by half

**Decision: any future connectivity or plan-grid filter must treat the raster's
ORIGIN PHASE as a parameter, and must either sweep it or be made invariant to
it.** It is recorded as a standing constraint rather than as a note, because it
was not visible from the design and would not have been found by reading the
code.

**Evidence:** `reports/big_house/grid-phase-2026-07-28.json`.

---

## WHAT WAS FOUND

`connected_core` bins plan coordinates into a raster whose origin is
`xy.min(axis=0)`: wherever the extreme point of that particular point set
happens to sit. Shifting the origin by a fraction of a cell moves every cell
boundary, so two points that shared a cell under one alignment fall into
different cells under another. **Connectivity on a raster is not phase
invariant.**

Over eight sub-cell phase offsets, at the sweep's own five connectivity scales,
on the eight main facets:

    worst case   facet 3 at 2.5 x spacing
                 kept fraction ranges 0.5186 to 0.9978
                 a swing of 407,429 points, HALF THE FACET

The production run happens to land at the good end: at the default origin facet
3 keeps 99.77 pct. **A half-cell shift of an arbitrary alignment would have
deleted 48 pct of it instead.** Facet 6 at 2.0 x spacing swings 0.0340 (13,687
points) and facet 2 at 1.5 x spacing swings 0.0262 (18,175 points).

**For comparison, the two parameters the sweep DID vary moved facet coverage by
0.03 percentage points over the whole 20-point grid.** The unswept parameter is
capable of moving a single facet's membership by half. It is not a second-order
nuisance; on the worst facet it is the largest term.

---

## WHY THIS MATTERS FOR THE PLATEAU RULE SPECIFICALLY

`decisions/2026-07-27-m1a-connectivity-preregistration.md` requires a plateau in
both swept parameters before any value is adopted. A grid that is flat in two
dimensions while a third, unmeasured dimension swings a facet by half **is not a
plateau; it is a plateau in two of three dimensions.** Had the sweep produced a
flat region, adopting from it would have been adopting a value valid for one
arbitrary raster alignment.

The M1a pass stopped for an independent reason (no plateau,
`2026-07-28-m1a-result-no-plateau.md`), so nothing was adopted and no harm was
done. **The constraint is logged anyway, precisely because it did not bite this
time.** A hazard recorded only when it causes damage is recorded too late.

---

## THE RULE

Any filter that rasterises coordinates and then reasons about ADJACENCY or
CONNECTIVITY must do one of:

1. **Sweep the phase** alongside its other parameters, and report the spread as
   a first-class number; or
2. **Be invariant by construction**, for example by working on a point-domain
   neighbourhood graph rather than a raster, where there is no grid and
   therefore no phase; or
3. **Fix the origin to something meaningful rather than incidental** (a site
   datum, a global grid), which does not remove the sensitivity but at least
   makes the choice deliberate, auditable and identical across facets and
   across sites.

Option 2 is the honest fix and was rejected for cost during M1a: a radius graph
over a 1.5-million-point facet is hundreds of millions of edges. That cost
argument is still true, and it is now a known debt rather than an invisible one.

**This generalises beyond connectivity.** The same hazard exists anywhere a
continuous quantity is discretised and then reasoned about topologically:
`coverage_masks`, `residual_blobs` and the plan-cell area accounting all bin on
a raster whose origin comes from the data's extent. Whether any of them is
phase-sensitive has NOT been measured. Recorded as an open question, not as an
accusation.

---

## HOW IT WAS FOUND, WHICH IS THE PART WORTH REMEMBERING

Not by design review. Assertion A2 of the sweep failed on its first run, on all
8 facets, by large margins (1 component against 78). The two labelling
algorithms were then shown to agree EXACTLY on identical input. The
disagreement was that the verifier re-derived the grid origin from the SUBSET it
was handed, while the filter had derived it from the full set. **The assertion
was accidentally varying the phase, and that accident is what measured it.**

**A first attempt to quantify it measured nothing and looked like a triumph.**
That probe shifted the POINTS by sub-cell offsets. Since the default origin is
the input's own minimum, translating the points translated the origin with them
and the binning was bit-identical every time. It reported a spread of exactly
0.000000 on all 40 facet-scale pairs with three passing sanity checks. **A null
result looked STRONGER than a real one, because zero spread is cleaner than any
true measurement.** Only an explicit `origin` argument exposed the real
sensitivity.

**Consequent addition to the silent-failure standing rule
(`2026-07-27-silent-failure-standing-rule.md`), which this entry does not
amend but does extend in practice:** a probe that perturbs a parameter and
reports the effect must carry an ANTI-NULL CHECK asserting that at least one
perturbation changed at least one output. Every check the failed probe carried
was a well-formedness check (in range, reproduces the reference,
integer-invariant), and all of them pass happily on a probe that is perturbing
nothing. The standing rule's existing wording ("an assertion built from
something known INDEPENDENTLY of its own result") is satisfied by those checks
and still missed this, which is why the case is named explicitly.

---

## ONE STRICT CHECK THAT FAILS, WITH ITS MAGNITUDE, KEPT STRICT

The probe asserts that an INTEGER cell offset must change nothing bit for bit,
since shifting the origin by whole cells is a relabelling rather than a
regridding. **It FAILS**, at 1 point out of 1,538,098 on facet 0 at 1.5 x
spacing, with a kept-fraction delta of 6.5e-07 and a component count differing
by 1.

The cause is floating point: `(x - lo + 3*cell)/cell` and `(x - lo)/cell + 3`
can differ in the last bit for a point lying exactly on a cell boundary, and
`floor()` then sends it to the neighbouring cell.

**The check was NOT relaxed to make it pass.** It records its magnitude
alongside its verdict and a `material` flag against a 1e-5 threshold on kept
fraction, which reads False. A strict check that fails by a known, measured,
negligible amount is more useful than a loose check that passes, because the
next time it fails the magnitude is the diagnosis.

---

**Rejected:**

- **Treating the A2 failure as a filter bug.** It was not; the two algorithms
  agree exactly on identical input. Reporting it as a filter bug would have
  been a false alarm that cost the pass its credibility.
- **Relaxing A2 to compare only against itself.** That would have removed the
  accident that found the phase sensitivity in the first place.
- **Declaring the filter robust on the strength of the first phase probe.** Its
  zero spread was a measurement of nothing.

**Cost if wrong:** if phase sensitivity is somehow an artifact of measuring on
canonical POST-TRIM points rather than the PRE-TRIM membership the filter really
sees, the constraint is stricter than necessary and costs one extra swept
dimension on future work. That is cheap next to the alternative, which is
adopting a parameter value that holds only for one accidental alignment.

**Attribution:** the finding, both instrument errors, the anti-null rule, the
decision to keep the integer check strict and report its magnitude, and the
generalisation to the other rasterised stages are Claude's. No part of this was
predicted in advance by anyone.
