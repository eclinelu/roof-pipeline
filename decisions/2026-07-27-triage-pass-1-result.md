### 2026-07-27: Triage pass 1 result: seven mechanisms, and the pre-registration covered a quarter of them

**Result:** The first visual review of `canonical-2026-07-26-r2` was triaged under
the protocol in `2026-07-27-defect-triage-protocol.md`. Seven candidate
mechanisms, plus five defects that fit none of them.

**THE NUMBER THAT MATTERS MOST, AND IT IS NOT FLATTERING TO THE
PRE-REGISTRATION: 42 of 56 catalogued defect instances, 75 percent, fit NEITHER
H1 NOR H2.** H1 accounts for 11 and H2 for 3.

This is logged before any fix is written, and it is logged as an INADEQUACY
rather than a confirmation, because that is what it is. H1 and H2 were
pre-registered by Emmett before the review was read, which is exactly the
discipline that makes them the two mechanisms most at risk of being
over-attributed to. Both turned out to be real. Both together explain a quarter
of what was found. **The largest mechanism by facet count was not pre-registered
at all.**

**Mechanisms, ranked by facets explained, each assigned a stage under 3b:**

    M1  membership by distance to an UNBOUNDED plane      stage 1   11 facets
        M1a thin remote slivers                                     8 (all main)
        M1b bulk absorption of adjacent structure                   3 (8, 9, 10)
    M4  boundary stops inside the real edge               stage 4   17 facets
    M5  boundary ragged where the real edge is straight   stage 4   12 facets
    M3  one real plane fitted as TWO facets               stage 2   10 facets
    M2  dormer surfaces never discovered                  stage 2    3 surfaces
    M6  outline crosses a correctly-found ridge           stage 4    2 facets
    M7  neighbours disagree on a shared boundary          stage 4    1 facet

M4 is the largest and was not anticipated. M2 and M3 are opposite failures on the
same structures: H2 predicted dormer planes being ABSORBED, and M3 is dormer
planes being SPLIT IN TWO.

**M1 was corroborated by an instrument that was not looking for it.** The
per-facet close-up for facet 4 rendered nearly blank. The renderer sets its axis
limits from `points.min()` and `points.max()`, so a facet whose points span far
more ground than it covers zooms out to nothing. Measured across all 29 facets
(`reports/big_house/fragments-2026-07-27.json`, read only):

    group                  core point fraction   extent inflation   farthest stray
    8 main facets (0-7)         96.2 - 99.9 %      1.21 - 2.40        11.6 - 53.4 ft
    recovered 8, 9, 10          66.1 - 73.6 %      1.82 - 2.90         7.4 - 11.6 ft
    recovered 11-28 (ex 20)     99.1 - 100  %      1.00 - 1.09         0.0 -  0.8 ft

Facet 0 resolves into 1,076 connected components; facet 2 into 634. The last row
is the control and it holds: the facets the review called clean measure clean.

**M1a and M1b are NOT merged, and the reason is measured rather than argued.**
They are orthogonal in the data: M1a is a very small fraction of points a very
long way out, M1b is a quarter to a third of points a short way out. A
connectivity filter removes M1a and leaves M1b untouched, because M1b's absorbed
regions are spatially contiguous with the facet. Same root cause, different
signatures, different fixes.

**Intersection lines get no work item under 3b, but the pattern is diagnostic.**
All 6 lines verdicted "does not exist" and all 5 verdicted "short" are between
MAIN facets; all 6 verdicted "correct" are between DORMER facets. That partition
is the M1a partition exactly, which makes the line errors look DOWNSTREAM of M1a
rather than independent.

**FIVE DEFECTS FIT NO MECHANISM AND ARE RECORDED UNATTRIBUTED.** A mechanism that
absorbs everything explains nothing, so these are left outside rather than
tidied away: facet 4 never assessed (instrument defect, itself caused by M1a);
facets 8 and 23 sitting on a different, patched roof material, the same class as
blob 0; facet 5's ragged curve through the MIDDLE of the facet where M4 and M5
are both edge phenomena; facet 1's outline that encloses nothing, an open contour
rather than a remote closed sliver; and explicit bad capture on facets 6, 21, 25,
26, 27, 28, which is a capture limit and not a segmentation mechanism.

**Two recording defects found, neither in the pipeline.** The `merge` identity
code was used in two opposite senses, and six line rows carry unambiguous notes
("does not exist") with no verdict recorded because the validator only checked
facet rows for that shape. Both are being corrected before pass 2.

**Answering the open question raised in the review about `facet_area`.**
`facet_area` runs over the WHOLE point set, not the largest connected component,
so remote slivers do contribute. But alpha is 4 x the facet's own median spacing,
so a triangle bridging a 50 ft gap has a circumradius far above alpha and is
rejected. The slivers add their own local area; they do not add the span between
them. **The larger exposure is not area. It is the plane fit**, since normal,
pitch and quality all come from the contaminated membership.

**Next pass is M1a**: stage 1, 8 facets, the largest mechanism at the earliest
stage. M1b waits, per one-mechanism-per-pass, and because a connectivity filter
does not touch it.

**Queue note, not acted on:** the 25/26 dormer has its NORTH side fitted as two
facets (M3) and its SOUTH side never discovered (M2). Over-segmentation and
non-discovery on the same structure. Facet 8 appears in both M1b and the M3 pair
8+23. M2 and M3 are NOT merged by assertion; recorded because something about
dormer geometry may produce both.

**Evidence:** `reviews/big_house/review-2026-07-27.json` (28 of 29 facets, 12 of
18 lines, facet 16 skipped deliberately); `reports/big_house/fragments-2026-07-27.json`.

**Attribution:** the triage protocol, the demand for an explicit unattributed
list, the demand for a count outside H1 and H2, the instruction not to merge
plausibly-identical mechanisms by assertion, and the ranking of M1a as the next
pass are Emmett's. The mechanism list, the fragment measurement and the reading
of `facet_area` are Claude's. The review verdicts are Emmett's throughout.
