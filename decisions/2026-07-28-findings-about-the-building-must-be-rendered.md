### 2026-07-28: STANDING RULE R6: a finding ABOUT THE BUILDING must be rendered before it is adopted

**Decision:** any finding that makes a claim about the physical roof must be
RENDERED before it is adopted. Numbers locate a finding; a picture confirms it.

**The line, because it is not "render everything":**

    ABOUT THE INSTRUMENT   raster phase, bin pitch, determinism, index
                           bookkeeping, assertion coverage. Legitimately and
                           entirely numeric. A picture adds nothing.

    ABOUT THE BUILDING     what a surface is, where a facet ends, why a
                           measurement disagrees with a tape, whether a region
                           is roof. MUST be rendered before adoption.

**Why (Emmett, stated directly):** three items in one session had drifted back
to pure scalar diagnosis, which is the failure mode the visual review was
adopted to fix. The specific case: the 1.83 deg systematic pitch bias is a claim
about a physical shingle surface and was heading toward adoption **on a scatter
plot alone**.

---

**This is the same principle as the existing site rules, pointed the other way.**
`2026-07-27-development-vs-validation-split.md` sets the standing limit that
visual review establishes THAT something is wrong and WHAT it is physically, and
can NEVER set a parameter value. R6 is the complement: **a number can locate a
physical claim but cannot confirm it.** Together they say the eye and the
arithmetic each have a job the other cannot do, and neither substitutes.

**What "rendered" means here:** an image of the thing being claimed, in a frame
where the claim would be visible if true and visibly absent if false, with a
scale bar in real units. Not a plot of a derived statistic. A scatter of
per-facet error against pitch is a plot; an image of per-point residuals laid
out on the facet is a render.

**Why the distinction has teeth rather than being a style preference:** a
derived statistic has already chosen what to keep. A scatter of eight facet
means can be fitted by several physical stories at once, and the plot cannot
distinguish them because the information that would has been averaged away
before it was drawn. The render carries the spatial structure, which is usually
the discriminating evidence, and it can falsify a hypothesis the summary
statistic would have supported.

---

**Applied immediately to three live items, which is what prompted the rule:**

- **The grid fix (`2026-07-28-adopt-exact-pitch-and-declared-lattice-origin.md`)
  moves 6 points of coverage.** Those cells have LOCATIONS. A thin rim around
  every facet is discretisation; patches in facet interiors is something else.
  The number cannot tell them apart and the render can, so the render happens
  before the number is published.
- **M1a is being deprioritized while still real.** Before closing it, the
  removed components get drawn in place. Choosing to live with a defect is a
  decision that should be taken looking at the defect, not at its area in square
  units.
- **The pitch bias hypothesis** predicts stripes at the shingle exposure in the
  per-facet residuals. That is an image-shaped prediction and it should live or
  die on an image.

---

**Rejected:**

- **Requiring a render for every finding.** It would make instrument work
  needlessly slow and would devalue the rule where it matters. The
  building/instrument line is the whole content.
- **Treating a plot of a derived statistic as satisfying the rule.** That is
  exactly what was about to happen with the pitch bias, and the reason it does
  not satisfy the rule is given above.
- **Rendering AFTER adoption as documentation.** The rule is a gate, not a
  write-up step. A picture produced after the decision cannot change it.

**Cost if wrong:** some renders will be uninformative and the effort is wasted.
That is cheap next to adopting a physical claim that a picture would have
refuted, which this project has already done once: boundary erosion was proposed
and withdrawn, and blob 0 needed a physical inspection to settle what three
numeric mechanisms could not.

**Attribution:** the rule, the building-versus-instrument line, the observation
that three items in this session had drifted back to scalar diagnosis, and the
specific charge that the pitch bias was heading for adoption on a scatter plot,
are all Emmett's. The framing as the complement of the existing visual-review
limit, and the argument for why a derived statistic cannot discharge the
obligation, are Claude's.
