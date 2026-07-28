### 2026-07-28: AMENDMENT to the M1a pre-registration: the coupling has two channels, P2 gets a real assertion, and the sweep grid is finally written down

**Status: AMENDMENT, appended before the fix was written and before any sweep
was run.** It does not edit
`decisions/2026-07-27-m1a-connectivity-preregistration.md`, which stands as
committed at `2b28704`. Four changes, all made with no outcome quantity in
hand.

---

## 1. THE P6/P8 CORRECTION IS ACCEPTED, AND ITS OWN REASONING HAD A FLAW

**Emmett, verbatim in substance:** the committed entry says `_point_plane_dist`
"reads the PLANE, not the membership list", and in the same sentence says it
reads `facet["normal"]` through `facet["points"].mean(axis=0)`. **That mean IS
the membership list.** Removing 26,753 strays from facet 0, many of them 11 to
53 ft out, moves the plane's ANCHOR POINT as well as its normal.

He is right, and the source confirms it exactly
(`roofkit/segment.py:331-336`):

    def _point_plane_dist(points, facet):
        n = np.asarray(facet["normal"], float)
        n = n / np.linalg.norm(n)
        return np.abs((points - facet["points"].mean(axis=0)) @ n)

Both `facet["normal"]` and `facet["points"].mean(axis=0)` are recomputed from
the kept set. **Coverage therefore responds to membership through TWO channels,
not one.** The committed entry's CONCLUSION survives untouched (the residual
does not grow by 79,038, and P6 correctly claims no direction), but its
description of the mechanism was single-channel and is corrected here.

### The refinement, Claude's: only PART of the centroid motion is a channel

A centroid displacement that lies IN the plane moves the anchor without moving
the plane. Reporting raw displacement alone would overstate the second channel.
Writing `c` for the centroid and `n` for the unit normal, the change in a point
`p`'s signed distance decomposes EXACTLY and ADDITIVELY:

    d_new(p) - d_old(p)  =  (p - c_old) . (n_new - n_old)     ROTATION channel
                          + (c_old - c_new) . n_new           OFFSET channel

- The **rotation channel** vanishes at the centroid and grows LINEARLY with
  in-plane radius. This is the leverage term already argued under P7.
- The **offset channel** is a single scalar per facet, IDENTICAL at every point
  of the facet. It is the along-normal component of the centroid displacement,
  i.e. the change in the plane's `d` coefficient.

This is why the two must not be pooled into "the plane moved": one is uniform
and one is proportional to distance, so **which dominates depends entirely on
where the strays are.** Emmett's expectation, recorded before the numbers
exist, is that the offset channel may dominate for facets whose strays are far
out and one-sided. That is a real physical mechanism: a one-sided stray mass
drags the mean toward itself, and when the strays sit on one side only, the
mean displacement does not cancel.

### What the sweep must report, per facet, at every grid point

    normal_change_deg          angle between n_old and n_new, degrees, 4 dp
    centroid_shift_in          |c_new - c_old|, inches (full 3D magnitude)
    centroid_shift_normal_in   (c_old - c_new) . n_new, inches  <- THE OFFSET
                                                                    CHANNEL
    rotation_at_stray_radius_in  the rotation channel evaluated at THIS
                                 facet's own farthest-stray radius, inches

The fourth number exists so the two channels are compared **at the distance
where the strays actually sit**, rather than compared as an angle against a
length, which is not a comparison. Reported separately, never summed into one
"plane movement" figure.

---

## 2. FULL 5 x 4 GRID. THE TWO-STAGE PILOT IS REJECTED

**Emmett's decision and his reason, stated directly:** an hour of unattended
compute is cheap next to a design in which the fine region is SELECTED FROM A
PILOT, because that selection is itself a step that would need pre-registering,
and it is a place to choose the answer.

That is the same argument the plateau rule already makes one level down. A
pilot-then-refine design smuggles a free parameter (where to refine) into a
procedure whose entire purpose is to have no free parameters chosen by
outcome. Rejected.

---

## 3. P2 GETS A REAL ASSERTION. THE COMMITTED ONE WAS A PREDICTION

**Emmett's criticism, and it is correct.** The committed P2 says facets 11-28
are untouched by construction so a direct no-op proves nothing, then
substitutes the INDIRECT effect ("recovered facet identity should be broadly
stable"). That is a PREDICTION, not an assertion: it can move for legitimate
reasons, so it cannot fail loudly, and the silent-failure standing rule
(`2026-07-27-silent-failure-standing-rule.md`) is therefore not satisfied.

### Ruling on the three candidates he offered

| candidate | verdict | reason |
|---|---|---|
| kept set is a strict subset of the original membership; total points never increases | REJECTED as primary | guaranteed by the fix's own structure. The filter only ever deletes from the pre-trim membership mask, so this cannot fail unless the index bookkeeping is broken. Kept as a cheap companion, not as the assertion. |
| every kept point is reachable from the main body in steps no longer than the connectivity scale, verified independently of the code that built the components | ADOPTED, restated | the right idea. Taken as its CONTRAPOSITIVE for cost, see below. |
| no facet's refitted normal changes by more than a sanity bound | REJECTED | a bound on the RESULT. Whatever value it took would have to be justified, and any justification available now would come from the numbers the sweep is supposed to produce. |

### THE CHOSEN ASSERTION (A1): POINT-DOMAIN SEPARATION

> For every facet, at every grid point: the minimum plan distance between the
> KEPT point set and the REMOVED point set is strictly greater than the
> connectivity scale.

Computed with a `cKDTree` built on the smaller of the two sets and queried with
the other. It reads **only raw XY coordinates and the output partition.** It
touches none of: the occupancy raster, the cell indices, `scipy.ndimage.label`,
the component sizes, or the `argmax` that selects the main body.

**Why it is independent of the result.** It is provable from the DEFINITION of
a connectivity cut at scale `s`: if two points lie within `s` of each other
then their cell indices differ by at most one on each axis, so they are
8-adjacent and by construction in the same component, so they cannot be on
opposite sides of the cut. The statement is therefore true no matter how many
points survive, which component was selected, whether a plateau exists, or what
happens to pitch, coverage, the bar, blob 0 or the facet count. **Nothing the
sweep is scored on can make it pass or fail.**

**Why it fails loudly for the failure that matters.** If the binning is
transposed, off by one in its origin, using the wrong cell size, or partitioning
on anything other than plan connectivity, removed points land immediately
beside kept points and the minimum distance collapses below `s`. That is
precisely "the filter is measuring or doing the wrong thing".

**Why the contrapositive rather than the reachability form:** a breadth-first
search over 1.5 million points, repeated 8 facets x 20 grid points, is not
affordable; the separation statement is one nearest-neighbour query and is
exactly as sharp for this failure mode.

### Two companions, because A1 alone has two blind spots

**A2, SINGLE COMPONENT, closing the blind spot that A1 permits a kept set that
is itself in two well-separated pieces.** The kept set is re-labelled by a
hand-written union-find over a hash map of occupied cells, and must come out as
exactly ONE component (at fraction 1.0). Different algorithm and different data
structure from the raster scanline labelling the filter uses, so a bug in one
does not reproduce in the other.

**A3, THE NO-OP TRIPWIRE, and this is the most dangerous omission in the
committed entry.** If the filter is never actually invoked (a flag defaulting
off, an import shadowed, an exception swallowed upstream) then every grid point
returns the baseline, every reported quantity is identical everywhere, and the
sweep displays **a perfect plateau**. The report would then read "plateau
found" on a fix that did nothing. So:

> At connectivity scale 2.5 x spacing, the number of points removed must be
> non-zero on all 8 main facets.

Its independence is that it is an assertion against a COMMITTED PRIOR
MEASUREMENT, not against an expectation:
`reports/big_house/fragments-2026-07-27.json`, written by `probe_fragments.py`,
records 8 of 8 main facets carrying multiple components at exactly that cell
size. Zero removals contradicts a published artifact produced by different
code. This is now independently re-verified: `probe_component_sizes.py` (new,
2026-07-28) reproduces those component counts facet by facet from the same
canonical state through a separately written code path, and the agreement is
written into its output as a cross-check.

---

## 4. THE SWEEP GRID VALUES, WHICH THE COMMITTED ENTRY NEVER CONTAINED

**Disclosed rather than quietly filled in (Claude).** The committed
pre-registration fixes both parameters by NAME, fixes their TRANSFERABLE FORM
(multiples of median spacing; a fraction of the facet's largest component),
fixes the reported quantities and fixes the stop-if-no-plateau rule. **It never
records the five values or the four values.** There is no "5 x 4 as written" in
the document; the 20 comes from arithmetic on the estimated runtime.

That is a real gap in a freeze. A pre-registration that names a swept parameter
without fixing its value is not frozen on that axis, and whoever fills it in
does so having already read every prior result. It is recorded here rather than
resolved silently.

### How the values were fixed, and why this is not selection by effect

The distinction relied on:

    INPUT property   how many connected components a facet's membership falls
                     into, and how large they are. A fact about the point
                     cloud. Unchanged by anything the fix does.
    OUTCOME          pitch delta, facet coverage, the quality bar, blob 0's
                     candidate, the facet count. What the sweep is SCORED on.

Choosing a sweep RANGE so it spans the region where a parameter can do anything
at all reads the first. Choosing a VALUE because of its effect on the second is
the error the plateau rule exists to prevent. `probe_component_sizes.py` is
constrained to the first: it does not import `roofkit.coverage` or
`roofkit.measure` and therefore CANNOT compute any scored quantity. Its output
is `reports/big_house/component-sizes-2026-07-28.json`.

### What it showed (input facts only)

- **The fraction axis is nearly inert above 1e-2.** At 2.5 x spacing and
  coarser, every one of the 8 main facets keeps exactly ONE component at
  fractions 1.0, 0.5 and 0.1. Sweeping 1.0 / 0.5 / 0.1 / 0.05 would have spent
  four runs computing the same answer four times. The axis only becomes live
  between about 1e-2 and 1e-4.
- **The connectivity axis has a hard floor.** At 1.0 x spacing the facets
  SHATTER: facet 7's largest component holds 21,294 of ~290,000 points, facet
  6's holds 86,290 of ~400,000. A filter keeping only the largest component
  there would delete 90+ percent of real roof. That is the catastrophic failure
  the committed entry named under "main body", now shown to be present on this
  building rather than hypothetical.
- **Facet 3 splits almost exactly in half at 2.0 x spacing** (second component
  is 0.9237 of the largest) and merges by 2.5. This is the pre-registered
  count-versus-area guard's live case: two near-equal components where the
  wrong choice deletes half a facet. It is flagged in advance, not discovered
  afterwards.

### THE GRID, fixed here, before any fit was run

    connectivity scale   1.5, 2.0, 2.5, 3.5, 5.0   x median point spacing
    minimum component    1.0, 0.01, 0.001, 0.0001  x largest component points

    5 x 4 = 20 full pipeline runs.

**Basis, stated so it can be attacked:** the connectivity values give two points
in the region where components are still merging (1.5, 2.0) and three in the
region where they are not (2.5, 3.5, 5.0), so a plateau has three points to
stand on and is not inferred from two. 2.5 is included because it is the
canonical coverage cell and makes the sweep commensurable with every existing
artifact. 1.0 is EXCLUDED as a candidate setting and characterised in the probe
instead, because it is already known to destroy 90 percent of two facets and no
plateau could include it. The fraction values span the live range across three
orders of magnitude and include 1.0, which is the committed entry's own
"largest by point count" definition of the main body.

---

**NOTHING IS ADOPTED FROM THIS RUN.** `canonical-2026-07-26-r2` stays canonical
and published facet coverage stays 88.40 pct until a successor is deliberately
adopted in a later task. This is Emmett's instruction, restated here so the
sweep's output cannot be mistaken for a new baseline.

**Evidence:** `roofkit/segment.py:331-336` for the two-channel reading;
`reports/big_house/fragments-2026-07-27.json` and
`reports/big_house/component-sizes-2026-07-28.json` for the component facts;
`decisions/2026-07-27-silent-failure-standing-rule.md` for the rule P2 was
failing.

**Cost if wrong:** the amendment adds reporting and assertions and narrows the
grid; if the grid values are badly chosen the cost is one hour of compute and a
sweep that has to be re-run with a different range, which is recoverable
because nothing is adopted from it.

**Amends (does not reverse):**
`decisions/2026-07-27-m1a-connectivity-preregistration.md`.

**Attribution:** the two-channel correction, the insistence that the channels
be reported separately rather than pooled, the expectation that the centroid
channel may dominate for far one-sided strays, the rejection of the two-stage
pilot with its reason, and the ruling that the committed P2 was a prediction
rather than an assertion, are all Emmett's, stated before the fix was written.
The exact additive rotation/offset decomposition and the observation that only
the along-normal component of centroid motion is a channel are Claude's. The
choice of A1 and its independence argument, the two companion assertions
including the no-op tripwire, the discovery that the committed entry contained
no grid values, and the grid values themselves with their stated basis, are
Claude's.
