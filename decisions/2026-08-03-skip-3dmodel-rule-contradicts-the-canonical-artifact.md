### 2026-08-03: OPEN DEFECT: `CLAUDE.md` requires `--skip-3dmodel` on every ODM run, and the canonical medium artifact was built without it. UNRESOLVED, and neither is changed here

**Defect:** `CLAUDE.md` states that ODM is always run with
`--end-with odm_georeferencing --skip-3dmodel`, and explains that
`odm_georeferencing` runs AFTER meshing and texturing in ODM's fixed stage
order, so `--skip-3dmodel` is required to actually skip the mesh the pipeline
never uses. The canonical medium cloud was built with `skip_3dmodel = False`.
Meshing and texturing ran. The ultra run of 2026-08-03 matched that setting
deliberately, to avoid introducing a second change alongside `pc_quality`.

First reported inside
`decisions/2026-08-03-ultra-is-conditional-on-the-memory-configuration.md` under
"Two things found on the way". This entry promotes it to a tracked open defect
so it is not carried only as a note inside an entry about something else.

**Which is wrong, the rule or the artifact: UNRESOLVED, and deliberately left
so.** The two candidate readings have different costs and the evidence here does
not choose between them.

- If the RULE is right, the canonical medium artifact was produced by a run that
  violated the project's own stated procedure. The cloud is not thereby wrong,
  because meshing is a downstream consumer of the point cloud and does not feed
  back into it, so the extra stages cost time and disk and not correctness.
- If the ARTIFACT is right, the rule is stricter than the project actually needs
  and has been quietly ignored, which makes it a rule that cannot be trusted to
  describe what the pipeline does.

**Why this matters, and it is not the wasted compute.** The consequence that
bites is this: **"follow `CLAUDE.md`" and "reproduce the canonical artifact" are
currently not the same instruction.** Anyone rebuilding the canonical medium
cloud from the written procedure would run a different configuration than the
one that produced it. That is a reproducibility defect in the record, not a
performance complaint, and it is the reason this is logged rather than shrugged
off. It also propagates: the ultra run had to choose between following the rule
and matching the baseline, chose the baseline, and so inherited the deviation.

**POWER CHECK, could this have come out the other way.** Yes, and it was
checked rather than assumed. The two runs' `log.json` option dictionaries were
diffed programmatically, 91 options per side, and `skip_3dmodel` was read from
that record rather than from anyone's recollection of how the run was invoked.
Had the canonical run carried `skip_3dmodel = True`, the diff would have shown
it and there would be no contradiction to log. The finding is therefore a
reading of the run record and is falsifiable against it.

**Cost if wrong:** low, and asymmetric in a useful direction. Nothing is changed
by this entry, so a later decision either way costs only the edit it chooses.
The expensive outcome is leaving it unrecorded, because the contradiction is
invisible until someone tries to reproduce the artifact from the documentation
and gets a different run.

**Not done here, on instruction:** `CLAUDE.md` is NOT edited, the canonical
artifact is NOT rebuilt, and no ODM run is launched. Resolving this requires
deciding which of the two is authoritative, which is Emmett's call.

**Attribution.** The discovery is from the ultra reconstruction session. The
framing of the consequence as a divergence between the written procedure and the
reproducible artifact is mine. The instruction to log without editing
`CLAUDE.md` is Emmett's.
