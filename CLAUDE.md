# Roof Measurement Pipeline

> **PRECEDENCE. If this file and `decisions/` disagree, `decisions/` WINS and
> this file is stale.** The decision log is append-only and dated; this file is
> overwritten and can silently carry a rule the log has already reversed. That
> is not hypothetical: on 2026-07-28 this file was found still instructing a
> stop at `odm_filterpoints`, which the log had recorded as producing no point
> cloud on two separate runs, and still naming `DECISIONS.md` as the live
> record two days after it was split. When you find a disagreement, fix this
> file in the same pass and say which layer you changed.

## What this project is
A Python pipeline that turns drone imagery of a property into a 3D point cloud,
then extracts real-world roof measurements from it. Primary deliverable total
roof area and per-facet roof pitch, validated against a roof of known dimensions
with the error quantified and reported honestly.

Reconstruction (photosvideo - point cloud) uses OpenDroneMap (ODM). Do NOT try
to build or reimplement reconstructionstructure-from-motion; that is out of scope.
The value of this project is the ANALYSIS half point cloud in, measurements out.

## Who I am, and how to work with me
- I am a mechanical engineering student, strong on hardware, drones, GPS, geometry,
  and GIS, but NEW to software. Explain all programmingsoftware concepts in plain
  language and define jargon on first use. Assume strong aptitude on the engineering
  and geometry; do not assume coding fluency.
- Explain the WHY behind recommendations, not just the steps. Present decisions as
  frameworks with tradeoffs, not bare answers. Use tables for comparisons.
- Be direct and concise. Never sycophantic. Flag problems directly.
- Never use em dashes, in any response, in any context.

I do not type the analysis code anymore; Claude Code does. But I do not
accept code I cannot explain.

Before any analysis code in roofkit/ is committed:
1. Explain the approach and why, not just what the code does.
2. Justify every parameter and threshold, including why it is or is not
   scale-dependent.

Glue code (paths, plotting, argparse, viewers) needs no gate.

## Architecture the seam
- `roofkitio.py` is the ONLY module that touches file formats. It reads a cloud
  and returns plain NumPy XYZ (and optionally colors). Everything else works on
  plain numbers and knows nothing about file formats, ODM, or laspy. To swap ODM
  for another engine later, only io.py changes.
- Do NOT pre-abstract Open3D. Use it directly inside the analysis. Premature
  abstraction is the wrong call until a real second use exists.
- Reusable analysis logic lives in `roofkit` (io, crop, scale, segment, measure).
  Throwaway explorationtuning scripts live in `scripts`. Capture prep lives in
  `prep`. Do not mix these.

## Key technical principles (learned the hard way)
- Scale comes from ONE tape-measured real-world distance, not from GPS. Meter-grade
  GPS is not accurate enough for a single building. Measure the LONGEST clean edge.
- Area scales as the square of the scale multiplier, so a 2% scale error is a 4%
  area error. Pitch is scale-independent (it is a ratio).
- No-GPS ODM clouds are in ARBITRARY units and ARBITRARY orientation (tilted).
  Never assume the cloud is in meters or level. Fit the ground plane to recover
  true vertical, then measure pitch relative to that.
- RANSAC distance thresholds are SCALE-DEPENDENT, not universal constants. A value
  tuned on one cloud will not transfer to a cloud at a different scale.
- Segment only AFTER isolating ground and walls must be removed before roof
  segmentation, or RANSAC grabs the wallsground instead of the roof.
- Always stop ODM at `odm_georeferencing`
  (`--end-with odm_georeferencing --skip-3dmodel`). That is the stage that writes
  the georeferenced `.laz` this pipeline reads.
  **Do NOT stop at `odm_filterpoints`.** It was tried twice and produced NO point
  cloud both times, because the `.laz` is written by the later stage, not that
  one. `odm_georeferencing` runs AFTER meshing and texturing in ODM's fixed stage
  order, so `--skip-3dmodel` is required to actually skip the mesh, which this
  pipeline never uses.

## Environment
- Python 3.12 in a native Windows venv (`.venv`).
- Key libraries Open3D, laspy + lazrs, numpy, scipy, Pillow, OpenCV.
- `roofkit` is installed as an editable package via pyproject.toml, so
  `import roofkit` works from anywhere in the project.
- ODM runs via Docker. ODM workspace is at `Codmdatasets` (separate from this
  repo). Point cloud files live there; this repo holds only code.

## Decision logging

The record lives in TWO places with OPPOSITE update rules. Do not mix them.

- `STATE.md` is the current state (phase, blocker, last thing verified, next
  action). It is OVERWRITTEN in place and must be true right now.
- `decisions/` is the decision log, ONE FILE PER ENTRY, named
  `YYYY-MM-DD-short-slug.md`, APPEND ONLY, never edited. `decisions/README.md`
  is the index and carries the order, because several entries share a date.

These were a single `DECISIONS.md` until **2026-07-26**. That file is no longer
the live record; it exists only as the pre-split baseline that
`python scripts/verify_decisions_split.py` reassembles and diffs to prove no
entry was altered by the split. Read `STATE.md` and `decisions/README.md` at the
start of a session. When a decision is made, or at the end of any session, use
the decision-log skill.

Standing rule on commits. At the end of every task, commit and push. Do not leave work uncommitted for me to do.

- Any pre-registration entry is committed AND PUSHED before the run it predicts. A pre-registration that exists only locally is worth nothing, since a local commit can be rewritten. Verify with git branch -r --contains <hash> and report the result.
- Any frozen artifact is committed before any comparison to ground truth.
- Everything else: commit at the end of the task, one message naming what was done.
- Report the hash and confirm the push succeeded. If you cannot push, say so loudly rather than leaving it silent.