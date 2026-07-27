### 2026-07-14: Ground truth is audit-only, never a pipeline input; outputs are pre-registered by commit

**Decision:** The pipeline's permitted inputs are exactly three: the point cloud, thresholds derived from the cloud, and one tape-measured scale distance (on big_house, and only there, that tape may be taken on the roof; see the exception entry). All other field measurements (inclinometer pitches, extra tape checks) exist only to score outputs after they are frozen. Enforcement is procedural: (1) run with frozen thresholds, (2) write per-facet area and pitch in cloud units, the eave brackets, and the chosen scale span's identity and cloud-unit value to an output file, (3) commit, and that hash is the pre-registration, (4) only then measure the real roof, (5) the comparison goes in a NEW file and the pre-registered output is never edited. Retuning after seeing roof data is legitimate but becomes a second pre-registered run with its own commit, and both runs are reported.

**Why:** big_house is climbable; future properties are not. Roof access is therefore an audit channel, and any roof-derived number that leaks into a parameter makes the validation circular and the pipeline non-portable. Because roof numbers are physically obtainable here, the discipline cannot rest on intent; the commit hash makes it checkable by a third party.

**Rejected:** Using roof measurements to calibrate an erosion correction, the most tempting use of them and the exact leak this rule exists to stop. Trusting intent without the commit protocol.

**Evidence:** Protocol decision from the 2026-07-14 planning session; nothing to measure yet. The first pre-registration commit will be the first evidence it is being followed.

**Cost if wrong:** If the procedure is bypassed even once, silently, the validation becomes uninterpretable, and the validation is the deliverable.
