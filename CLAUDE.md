# Roof Measurement Pipeline

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

## CRITICAL pair, do not autopilot
Claude Code writes the analysis core; the gate is explanation, not authorship
(decision 2026-07-12, amended 2026-07-18). For the analysis core (segmentation,
geometry, measurement math, anything an interviewer would probe): explain the
approach and the why in plain language, in heavily commented code and clear
walkthroughs, so I can defend every stage in an interview. Then invite my
questions and MOVE ON. Never quiz me, never ask me to explain the why back,
and never refuse to proceed until I supply a reason. Understanding is my job;
a clear explanation is yours.

Boilerplate and glue ARE fine to write for me file paths, plotting, argument
parsing, ODMDocker commands, environment setup, config files, visualization.

Default loop: explain the concept, build it, run it, invite questions, move
on. Small steps, plain language on code, never a quiz.

## Where the project record lives
- `STATE.md` holds the current state (phase, blocker, last thing verified, next
  action). It is OVERWRITTEN in place and must be true right now.
- `decisions/` holds the decision log, ONE FILE PER ENTRY, named
  `YYYY-MM-DD-short-slug.md`. It is APPEND ONLY: past entries are evidence and
  are never edited. `decisions/README.md` is the index and carries the order
  (several entries share a date, so filename sort does not recover it).
- These were a single `DECISIONS.md` until 2026-07-26. The split copied every
  entry verbatim; `python scripts/verify_decisions_split.py` proves it by
  reassembling the original and diffing against the last committed version.
- Use the `decision-log` skill to add entries. Opposite update rules, so do not
  mix the two: state gets rewritten, entries never do.

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
- Always stop ODM at `odm_georeferencing` (`--end-with odm_georeferencing --skip-3dmodel`). That is the stage
  that writes the georeferenced `.laz` this pipeline reads; it runs AFTER meshing/texturing in ODM's fixed
  stage order, so `--skip-3dmodel` is required to actually skip the mesh, which this pipeline never uses.

## Environment
- Python 3.12 in a native Windows venv (`.venv`).
- Key libraries Open3D, laspy + lazrs, numpy, scipy, Pillow, OpenCV.
- `roofkit` is installed as an editable package via pyproject.toml, so
  `import roofkit` works from anywhere in the project.
- ODM runs via Docker. ODM workspace is at `Codmdatasets` (separate from this
  repo). Point cloud files live there; this repo holds only code.