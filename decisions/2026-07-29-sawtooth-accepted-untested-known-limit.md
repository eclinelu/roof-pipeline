### 2026-07-29: The shingle sawtooth is ACCEPTED, UNTESTED as the explanation for the 1.83 deg pitch bias, and recorded as a KNOWN LIMIT under 3e

**Decision:** the shingle sawtooth is accepted as the working explanation for the
1.83 deg systematic pitch bias. **No further tests.** No straightedge site visit,
no second instrument, no further statistical passes.

**STATUS: ACCEPTED, UNTESTED. NOT CONFIRMED.** Those words are the status, not a
hedge attached to a status.

**Reverses nothing.** It supersedes the closing recommendation in
`2026-07-29-pitch-bias-sawtooth-refuted.md`, which proposed 5a and a second
instrument as the way forward. The measurements in that entry stand exactly as
recorded; what changes is what is done about them.

---

## WHAT THE TESTS ACTUALLY SHOWED, STATED PLAINLY

    10-1  stripes in the residual images      FAILED to show courses
    10-3  amplitude 0.12 to 0.24 in           came in 5 to 17x BELOW prediction
                                              (measured 0.014 to 0.034 in)
    5b    shape discriminator                 fit NEITHER band (ratio 1.188
                                              against 1.00 and 0.70)
    10-2  spectral peak in 4 to 7 in          ambiguous, and weakened by 5 of 8
                                              wavevectors sitting at exactly
                                              0.0 deg, which is Hann leakage

**Nothing in that list supports the hypothesis.** It is being accepted anyway,
and the reason has to be good enough to carry that.

---

## WHY A NULL THERE IS NOT A REFUTATION

**MVS reconstruction SMOOTHS.** A sawtooth whose relief sits below the effective
resolving power of the stereo matching is not reproduced as a sawtooth; it is
averaged away. And **the average of a shingle sawtooth is the deck slope** —
which is precisely what the hypothesis requires in order to produce the observed
bias.

So the mechanism, if real, predicts its own signature is ABSENT from the cloud.
The stripe test and the amplitude test were asking whether the cloud contains
relief that the hypothesis says the reconstruction removes.

**That makes the tests uninformative rather than negative.** They did not support
the hypothesis and they did not refute it. Recorded as such rather than as either.

**And it means the test was underpowered in the deepest possible sense**: not
that it lacked samples, but that a positive result was not available to it under
the hypothesis being tested. That is worse than the 5b power failure and is the
reason the POWER CHECK field now exists in the pre-registration template
(`2026-07-29-power-check-required-in-preregistrations.md`). **The right time to
notice this was before the render was built, not after.**

**The consequence, stated because it is uncomfortable:** the hypothesis is not
falsifiable by any measurement of this cloud. That is exactly why it is a KNOWN
LIMIT and not a finding. Accepting an unfalsifiable explanation as a working
account is defensible; presenting it as verified would not be.

---

## RECORDED AS A KNOWN LIMIT UNDER 3e

    IDENTIFIED     a 1.83 deg systematic offset, pipeline reads steeper than
                   the inclinometer, on essentially every facet
    UNDERSTOOD     the leading account is that the phone rested on shingle
                   FACES, which are shallower than the deck, while the cloud
                   follows the deck. The direction matches. The magnitude sits
                   between 3-tab (1.44 deg) and architectural (2.40 deg) at
                   about 4.6 mm over 5.625 in, which is physically plausible.
    NOT VERIFIED   see above. The tests available on this cloud cannot
                   distinguish it from a procedural bias in how the readings
                   were taken, and a procedural bias would look identical.
    NO CORRECTION  none applied, to any pitch, on any facet, at any site.

**REPORTING REQUIREMENT, and this is the operative part of this entry.** The
limit **must be stated attached to any pitch number in any report, NOT in an
appendix.** A reader who sees a per-facet pitch must see, in the same place, that
the pipeline reads about 1.83 deg steeper than a hand inclinometer did on the one
site where both exist, and that the reason is identified but unverified.

**NO CORRECTION IS APPLIED, NOW OR LATER, WITHOUT A NEW DECISION.** Not on
big_house, not on bungalow, not on cove_house. This is not a default that
future work may quietly relax:
`2026-07-14-ground-truth-audit-only.md` already forbids a correction derived from
the disagreement, and the reason bears repeating, because a correction fitted to
the size of the error would guarantee agreement while measuring nothing and would
contaminate both held-out sites.

---

## WHAT THIS COSTS, AND WHY IT IS STILL THE RIGHT CALL

**The cost:** the pitch validation stands at max |error| 2.19 deg, PASS at 3 deg
and FAIL at 2 deg, with 1.83 deg of that being a systematic offset whose cause is
believed but unproven. **The project cannot claim 2-degree pitch accuracy and
cannot explain, with evidence, why it misses.** That is a real weakness in the
deliverable and stating it is the whole point of 3e.

**Why accepting is still right:** the alternatives were a site visit and a second
instrument, and neither is free. The site visit measures shingle geometry, which
would give an independent `arctan(t/e)`, but it cannot distinguish the shingle
step from a procedural bias either, because both predict the same constant
offset. A second instrument would settle the procedural question, and it is the
only test that would, but it is a new instrument, a new trip and a new
calibration chain on a DEVELOPMENT site from which no accuracy claim will ever
come (`2026-07-27-development-vs-validation-split.md`).

**Two held-out sites are waiting and one arrives in about a week.** Spending that
week on an unfalsifiable question about the development site, rather than on the
sites the accuracy claim will actually come from, is the wrong trade. The
mechanism is plausible, the direction is right, the magnitude is physically
sensible, and it is written down as unverified.

---

**Rejected:**

- **Calling it CONFIRMED.** Three of four tests failed to support it. Confirmed
  would be false.
- **Calling it REFUTED.** The MVS-smoothing argument means the tests could not
  have supported it even if true, so a null carries no evidential weight against
  it. `2026-07-29-pitch-bias-sawtooth-refuted.md` titled it "REFUTED" and that
  title is now too strong; the measurements in it are unchanged and correct.
- **The straightedge site visit (5a).** Cannot separate shingle step from
  procedural bias, which is the live ambiguity.
- **A second independent instrument.** It IS the test that would settle it, and
  it is declined on cost against two held-out sites, not on merit. If a trip to
  big_house happens for another reason, this is worth ten minutes.
- **Applying a 1.83 deg correction.** Circular, forbidden, and it would move a
  FAIL at 2 deg into a PASS by construction, which is the single most
  self-serving thing this project could do.
- **Putting the limit in an appendix.** A caveat a reader can miss is a caveat
  that will be missed.

**Evidence:** `reports/big_house/facet-residuals-2026-07-29.png`,
`facet-residuals-spectrum-2026-07-29.png`,
`pitch-bias-score-2026-07-29.json`,
`comparison-2026-07-18-scored-2026-07-18.json` (`pitch_summary`: mean bias 1.83
deg, max |error| 2.19 deg, PASS at 3, FAIL at 2).

**Cost if wrong:** if the bias is procedural rather than physical, then the
reported cause is wrong while the reported NUMBER and its uncertainty are
unaffected, because no correction was applied. That is the whole value of
declining to correct: being wrong about the mechanism costs an explanation, not a
measurement.

**Attribution:** the decision to close it, the status wording ACCEPTED UNTESTED,
the MVS-smoothing argument that a null is not a refutation and that the average
of a sawtooth is the deck slope, the instruction to record it as a known limit
under 3e, and the requirement that it be attached to any pitch number rather than
appendixed, are all Emmett's. The observation that this makes the hypothesis
unfalsifiable on this cloud, and the note that a second instrument is declined on
cost rather than on merit, are Claude's.
