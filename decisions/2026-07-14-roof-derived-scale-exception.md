### 2026-07-14: Roof-derived scale is a big_house exception; the wall instrument is retired for this dataset

**Decision:** For big_house, the scale span is derived from roof geometry and taped on the roof. This is an exception, logged so it cannot quietly become the pattern: future properties get scale from the ground (longest building face at grade, footprint corner-to-corner diagonal, fixed ground feature pair, in that priority order), because future roofs will not be climbable and roof measurements there are audit-only.

**Why:** The wall finder failed because most walls have no coverage at all (nadir grid capture, trees prevented low flight), not because of thresholds; no code fixes absent data, and there is no refly. The roof is this cloud's best-reconstructed geometry by a wide margin (8 planes, sub-centimeter scatter), and the fit-from-good-data principle points the scale instrument at it. The 2026-07-14 candidate span (face 7 to the 0/2/4 facade plane) is retired along with the corner instrument.

**Rejected:** Recapturing with wall-oriented flight (no refly available). Ground control markers (same). Deriving scale from ground features on this dataset before exhausting the roof, which is strictly better-reconstructed geometry.

**Evidence:** wall_recon.py runs of 2026-07-14 (8 faces, all ~E/W, zero corner contact) plus Emmett's field knowledge of which walls the capture could see. Roof quality numbers from the 7a runs.

**Cost if wrong:** If the roof-derived span carries hidden edge bias into the scale multiplier, every area is wrong by its square. The recon's bias accounting (see the bracket entry) exists to surface that before the tape is chosen.
