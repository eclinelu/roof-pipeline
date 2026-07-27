### 2026-07-14: Scale span is derived from wall-plane geometry, never from clicked corners; reconnaissance runs before the tape

**Decision:** Cloud-side scale endpoints are never clicked. Spans are derived from plane fits to well-reconstructed wall interiors (the ridge instrument's logic pointed at walls), and wall_recon.py runs BEFORE the tape measurement so the tape goes to the edge the cloud measures best. The predicted error of a candidate is computed from its split-half repeatability plus the tape's centimeter, and the choice is made on that number.

**Why:** A corner in a point cloud is a fuzzy cluster where two fuzzy surfaces meet, and ODM reconstructs edges worse than surfaces; clicking one samples the scene's worst data (est. 5-15 cm per end, 2-6% on area, alone exceeding the 5% budget). A plane fit to thousands of surface points puts the derived geometry at millimeter repeatability. The cloud is the fixed thing and the tape is the flexible thing, so the measurement site is chosen by the instrument, not by habit.

**Rejected:** Taping first and reconstructing whatever was taped. Clicking endpoints with a repeat-click spread as the error bar (quantifies the noise instead of removing it).

**Evidence:** Split-half repeatability 0.9-2.4 mm on a ~7 m span (2026-07-14 runs). The click-spread control experiment (measure_scale.py --click-spread) is still to be run so the old instrument's error is measured, not estimated.

**Cost if wrong:** If wall surfaces are systematically biased (vegetation shadowing, siding relief), plane-derived spans inherit it invisibly; the tape comparison itself is the check, since a factor far from 1.0 beyond GPS-plausible scale error would expose it.
