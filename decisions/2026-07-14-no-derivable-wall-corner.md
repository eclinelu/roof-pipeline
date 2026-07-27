### 2026-07-14: Constraint discovered: this cloud has no derivable wall corner; parallel-plane separation is the scale instrument

**Decision:** The scale span for big_house is the perpendicular separation between wall face 7 and the near-coplanar 0/2/4 facade plane (~6.93 cloud units, three readings 6.931/6.934/6.960 whose 26 mm spread is the real offset within the coplanar family), pending Emmett's reachability check. The corner-to-corner instrument is retired for this dataset: it has no target.

**Why:** The north/south-facing wall sets never reconstructed (nadir grid capture; confirmed with relaxed gates and 30 RANSAC peels, not just default thresholds), and every geometrically possible corner pair failed contact validation with zero points near the intersection line: the reconstructed walls do not physically adjoin. A parallel-plane separation needs no corner anywhere; taping it flat across a connecting face introduces only sec(skew), and the skew is measured from the cloud when the connecting face reconstructed, not assumed.

**Rejected:** Deriving corners by extrapolating wall planes to intersections without contact support (a jog or plane change beyond the reconstructed patch would be invisible). Relaxing corner gates further (the walls are absent, not filtered).

**Evidence:** wall_recon.py runs of 2026-07-14: 8 wall faces, scatter 0.003-0.006 cu, all facing ~E/W; corner contact counts 0/0 for every candidate pair; split-half repeatability of the candidate span 0.9-2.4 mm; predicted error ~0.15% linear, ~0.3% on area, versus 2-6% for clicked corners.

**Cost if wrong:** If the taped faces do not match the derived planes (proud corner trim, hidden jogs), the scale factor carries a centimeter-scale systematic; the three near-coplanar readings 26 mm apart exist to catch exactly that, and the trim construction is recorded at taping time.
