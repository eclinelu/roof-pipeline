### 2026-07-27: CANDIDATE, NOT ADOPTED: facet boundaries should be straight lines, and a shared boundary should be ONE line

**Status: CANDIDATE. Nothing is adopted, nothing is built, nothing acts on
this.** It is logged BEFORE the M1a sweep reports so that it is on record as an
architectural hypothesis rather than as something reverse-engineered to fit the
M1a result. It does not change the current pass.

---

**THE PROPOSAL (Emmett's).** Facet boundaries should be STRAIGHT LINES. A
boundary shared with a neighbouring facet should be ONE line, not two
independent outlines that happen to run near each other. Dormer facets should
meet along their ridge, and this generalises to every shared edge on the
building, not just dormers.

---

**SCOPE IT ADDRESSES, read off the pass 1 triage
(`2026-07-27-triage-pass-1-result.md`).**

    M6  outline crosses a correctly-found ridge         2 facets   eliminated by construction
    M7  neighbours disagree on a shared boundary        1 facet    eliminated by construction
    M5  boundary ragged where the real edge is straight 12 facets  eliminated by construction
    M4  boundary stops inside the real edge             24 facets  PARTIAL, see below

M6 and M7 cannot exist once a shared boundary is a single line: M7 is by
definition two outlines disagreeing, and M6 is an outline crossing a line that
would instead be its own terminator. M5 cannot exist once boundaries are
straight, because raggedness is precisely non-straightness.

M4 is addressed only where "short" means the boundary stops before a SHARED
edge. Where it stops before a FREE edge there is no neighbour to intersect and
regularization supplies nothing.

---

**WHY IT IS NOT NEXT. The dependency is real, not procedural (Claude's
argument).**

1. Shared edges come from plane-plane intersection. Plane-plane intersection
   comes from the normals. M1a contaminates the normals. The evidence is
   already in the record and it is unusually clean: every wrong line is between
   MAIN facets and every correct line is between DORMER facets, which is
   exactly the M1a fragmentation partition. Building intersection geometry on
   contaminated normals would produce straight lines in the wrong places, which
   is worse than ragged lines in the right places because it looks finished.
2. Three dormer surfaces are undiscovered (M2). Two dormers therefore have only
   ONE side of their ridge present. A shared boundary cannot be computed with a
   facet that does not exist.
3. Five facet pairs lie on the same plane (M3). Plane-plane intersection is
   degenerate for a coplanar pair: there is no unique line.

So the order is M1a, then M2 and M3, then this, then the remaining boundary
work.

---

**THIS IS A MODEL CHANGE, NOT A BUG FIX. Recorded that way deliberately.**

It imposes a PRIOR: a roof is a polyhedron with planar facets meeting at
straight edges. That prior is nearly always true for residential roofs, and it
is what EagleView and Scanifly ship.

It changes the measurement from "measure the cloud" to "fit a model to the
cloud", and therefore changes what a reported error MEANS. Under the current
approach an error is a disagreement between the cloud and the tape. Under a
fitted model an error is a disagreement between the model and the tape, and the
model can be right where the cloud is absent. Those are different quantities
and a report that conflates them is not honest.

---

**THE COST, STATED NOW WHILE IT IS INCONVENIENT (Claude's).**

**REGULARIZATION CAN HIDE CAPTURE FAILURES.** A facet that stops short of the
ridge because the drone never saw that strip gets extended to the ridge BY
ASSUMPTION. The area then becomes correct and the gap vanishes from coverage.
That would break the detector that found blob 0: the entire coverage instrument
works by noticing regions no facet explains, and regularization's job is to
make facets explain more.

**MITIGATION, to be carried into any implementation and not renegotiated
later:** keep BOTH outputs permanently.

    measured extent   the unregularized boundary, from the points only
    regularized model the polyhedron fit
    divergence        the difference between them, as its own reported number

"X sq ft, of which N percent is inferred across capture gaps" is a better
deliverable than either number alone. It is also the only form in which the
blob 0 detector survives, because the divergence layer is where a capture hole
goes when the model paves over it.

---

**TWO SUB-PROBLEMS OF DIFFERENT DIFFICULTY. Split explicitly, because solving
the easy one will look like solving both.**

    SHARED edges  ridge, hip, valley. Geometrically DETERMINED once the
                  normals are clean: intersect two planes, get a line. Little
                  freedom, little to tune.

    FREE edges    eave, rake, gable end. No neighbour to intersect, so
                  straightness can be ENFORCED but POSITION still has to come
                  from the points. This is where the fringe question and the
                  larger half of M4 live, and Diagnostic E is still held on it.

**The shared-edge half will look like it solved everything. The free-edge half
is where the area actually is.** A demo that closes every ridge and valley will
be visually convincing and will move the total by comparatively little.

---

**Rejected (implicitly, by not being the proposal):** regularizing each facet's
outline independently to a straight-sided polygon. That fixes M5 and leaves M7
untouched, because two independently straightened outlines still disagree along
the edge they share. The single-line requirement is the load-bearing part of
the proposal, not the straightness.

**Evidence:** `decisions/2026-07-27-triage-pass-1-result.md` for the mechanism
counts; `reviews/big_house/review-2026-07-27.json` for the line verdicts and
the main/dormer partition; `decisions/2026-07-27-blob0-confirmed-roof.md` for
what the coverage detector currently catches and would stop catching.

**Cost if wrong:** as a CANDIDATE, zero, because nothing is built. If it were
adopted and the prior turned out not to hold on some roof (a genuinely curved
or irregular surface), the regularized number would be confidently wrong while
the measured-extent number stayed right, which is the reason both are kept.

**Attribution:** the proposal, the requirement that a shared boundary be ONE
line, and the observation that it extends to every facet on the building rather
than only to dormers, are Emmett's. The dependency argument (that this must
follow M1a, M2 and M3, and why) and the hide-capture-failures cost with its
both-outputs mitigation are Claude's. The shared-edge / free-edge split and the
warning that the shared half will look like it solved everything were stated in
Emmett's instruction and are recorded as given.
