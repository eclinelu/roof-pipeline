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
I write the analysis core myself so I can defend every stage in an interview.
For the analysis core (segmentation, geometry, measurement math, anything an
interviewer would probe) explain the approach and the why, write a heavily
commented REFERENCE version if helpful, but let ME write the real version and
then review mine. Do not generate-and-move-on for these parts.

Boilerplate and glue ARE fine to write for me file paths, plotting, argument
parsing, ODMDocker commands, environment setup, config files, visualization.

Default loop explain concept - I write it - I run it - we review and fix.
Small steps, beginner pace on code.

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
- Always stop ODM at `odm_filterpoints` (`--end-with odm_filterpoints`). The mesh
  is expensive and this pipeline never uses it.

## Environment
- Python 3.12 in a native Windows venv (`.venv`).
- Key libraries Open3D, laspy + lazrs, numpy, scipy, Pillow, OpenCV.
- `roofkit` is installed as an editable package via pyproject.toml, so
  `import roofkit` works from anywhere in the project.
- ODM runs via Docker. ODM workspace is at `Codmdatasets` (separate from this
  repo). Point cloud files live there; this repo holds only code.