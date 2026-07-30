### 2026-07-30: CONSTRAINT DISCOVERED: the published per-facet areas do not recompute today, on facets that are provably identical. Reported, not fixed

**Decision:** Record, and change nothing. No area is recomputed, no area code is
touched, and the published **3,559.3 ft^2** stands exactly as frozen on
2026-07-18. This entry exists so the gap is on the record BEFORE any future area
work starts, rather than being rediscovered inside it.

**Why:** This surfaced as a side effect of the P1 area cross-check in the
2026-07-30 grid-adoption pre-registration, which was explicitly labelled there
as a check on the AREA FUNCTION rather than as confirmation of facet identity.
It did its job: it found something, and what it found is not what anyone
expected.

**Evidence:**

The 8 main facets are **provably the same facets** they were on 2026-07-18. The
frozen `preregistered-2026-07-18.json` stores per-facet point counts, and all
eight are IDENTICAL to `canonical-2026-07-26-r2` and to the new
`canonical-2026-07-30-grid-adopted`:

    1538098, 1154335, 693991, 850268, 744303, 669484, 403109, 297583

The pitches agree too (21.188 vs 21.1883, 33.067 vs 33.0669, ...). Main
discovery has been stable since 2026-07-18, which is itself worth knowing and
is the reassuring half of this entry.

Recomputing slope area today on those same points and the same stored planes
does NOT reproduce the stored areas:

| facet | stored 2026-07-18 ft^2 | alpha = 4 x per-facet spacing | alpha = 4 x global spacing |
| --- | --- | --- | --- |
| 0 | 487.4 | 502.45 (+15.05) | 511.78 (+24.38) |
| 1 | 776.2 | 790.81 (+14.61) | 784.24 (+8.04) |
| 2 | 349.7 | 357.44 (+7.74) | 366.39 (+16.69) |
| 3 | 602.9 | 606.17 (+3.27) | 603.39 (+0.49) |
| 4 | 326.5 | 327.17 (+0.67) | 328.70 (+2.20) |
| 5 | 211.7 | 212.84 (+1.14) | 215.29 (+3.59) |
| 6 | 383.1 | 383.30 (+0.20) | 376.43 (-6.67) |
| 7 | 421.8 | 421.79 (-0.01) | 404.23 (-17.57) |
| **total** | **3559.3** | **3602.0 (+42.7, +1.2 pct)** | **3590.5 (+31.2, +0.9 pct)** |

**NEITHER convention reproduces the published numbers**, and the residuals do
not share a sign pattern, so this is not a single scale factor. `alpha_mult` is
**4.0 in both** the 2026-07-18 freeze's config and today's, so the multiplier is
not the difference either. Something in the alpha-shape area path changed
between 2026-07-18 and now, and this entry does NOT identify what.

**Three explanations were tested and killed, which is why this is logged as
open rather than solved:**

1. *Different facet membership.* REFUTED: point counts are identical on all 8.
2. *Different alpha multiplier.* REFUTED: 4.0 in both configs.
3. *A per-facet versus global spacing convention.* REFUTED: computed both, and
   neither matches. Per-facet is closer on facets 3 to 7 and worse on 0 and 2.

**Cost if wrong:** contained today, potentially expensive later. Nothing
currently published depends on recomputing these areas: 3,559.3 ft^2 is a frozen
2026-07-18 number, it is quoted as-is, and prediction P2 confirmed this pass did
not disturb it. The exposure is FUTURE. `STATE.md` already records that no
measured area exists for big_house and that area has never been validated
against ground truth, so this adds a second reason to distrust an area
comparison across time: the number and the code that would regenerate it have
drifted apart by about 1.2 percent, which is the same order as the differences
an area validation would be trying to resolve.

**Explicitly NOT concluded:** that the current area code is wrong, or that the
2026-07-18 area was wrong. Only that they disagree on identical inputs, and that
the disagreement is unexplained. Assigning blame needs the 2026-07-18 code path,
which was not reconstructed in this pass and should not be reconstructed inside
an adoption pass.

**Next action when area work resumes:** reconstruct the 2026-07-18 `facet_area`
call from that commit and diff it against today's before any area number is
recomputed or compared. Until then, quote 3,559.3 ft^2 as a frozen figure and do
not regenerate it.

**Attribution.** The instruction to cross-check areas at 0.1 ft^2 against the
scored 2026-07-18 comparison, and the ruling that this tests the area function
rather than confirming bit-identity, are Emmett's. The finding, the three killed
explanations and the reading above are mine. Emmett has not stated a view on the
cause.
