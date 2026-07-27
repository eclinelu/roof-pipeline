### 2026-07-12: ODM must run past odm_filterpoints to produce a point cloud

**Decision:** Do not stop ODM at `--end-with odm_filterpoints`.

**Why:** `odm_filterpoints` does not write `odm_georeferenced_model.laz`. A later stage does. Two full runs were completed with the early stop and neither produced a point cloud.

**Rejected:** Stopping early to skip mesh generation. The intent was sound (the mesh is never consumed by this project) but the stop point was attached to the wrong stage, so it skipped the deliverable along with the mesh.

**Evidence:** Two failed runs producing no `.laz`. Corrected stage order confirmed against the ODM run log rather than from assumption.

**Cost if wrong:** One full ODM run wasted per occurrence, roughly one to three hours on a 232-image dataset.

**Note:** This entry exists as much as a warning about method as about ODM. The original wrong instruction was written into both `CLAUDE.md` and the `odm-run` skill as a confident "lesson learned," and was then followed twice. Written-down claims about tool behavior must be checked against tool output.
