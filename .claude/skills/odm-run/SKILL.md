---
name: odm-run
description: Run OpenDroneMap (ODM) via Docker to reconstruct a georeferenced point cloud from a folder of drone images. Use this skill whenever the user mentions ODM, OpenDroneMap, photogrammetry reconstruction, regenerating a .laz or point cloud, processing a drone dataset, or working with anything under C:\odm\datasets. Also use it when a cloud file is missing and needs to be rebuilt from images, or when the user is deciding on ODM quality flags or runtime tradeoffs. Consult this before running any docker command involving opendronemap.
---

# Running ODM

Reconstruction is a solved problem handled by an existing tool. This project does NOT reimplement structure-from-motion. ODM's only job here is: images in, georeferenced point cloud out. Everything downstream (segmentation, measurement) is the project's own code and is engine-agnostic.

## The prime directive: images are irreplaceable, clouds are not

Point clouds, meshes, orthophotos, and every other ODM output are DERIVED artifacts. Delete one and you lose compute time, not data. You re-run ODM and get it back.

The source images are the only irreplaceable asset in the project. They cost a flight to obtain. A lost cloud costs an hour; a lost flight costs a flight.

Practical consequences:
- Never run a recursive delete on a directory containing `images/` without enumerating it first.
- Before any destructive operation on `C:\odm\datasets`, confirm the images are backed up somewhere else.
- If asked to "clean up" ODM outputs, clean the derived directories, never `images/`.

## Pre-flight checks

Run these before starting. They cost seconds and can save an hour of wasted compute:

1. Is Docker running? `docker ps` should return without error.
2. Does the project folder exist with an `images/` subfolder? ODM requires exactly this layout: `C:\odm\datasets\<project_name>\images\*.jpg`
3. How many images? `(ls C:\odm\datasets\<project_name>\images).Count` This sets the runtime expectation.
4. Is there enough disk space? ODM intermediates are large; budget several GB.

## The command

```powershell
docker run -ti --rm -v C:/odm/datasets:/datasets opendronemap/odm --project-path /datasets <project_name> --end-with odm_georeferencing --skip-3dmodel --pc-quality high --feature-quality high
```

| Flag | Why it is there |
|---|---|
| `-ti` | Attaches to the terminal so progress is visible. Closing the window kills the run. |
| `--rm` | Deletes the container on exit so dead containers do not accumulate. |
| `-v C:/odm/datasets:/datasets` | Mounts the Windows data folder into the container. Use FORWARD slashes even on Windows; backslashes fail. |
| `--project-path /datasets` | Where ODM looks for projects, as seen from INSIDE the container. Not a Windows path. |
| `<project_name>` | Folder name only, not a full path. ODM expects `/datasets/<project_name>/images/` to exist. |
| `--end-with odm_georeferencing` | ALWAYS use this. See below. |
| `--skip-3dmodel` | ALWAYS use this too. See below. |
| `--pc-quality high` | Controls point cloud density. The flag that matters most for this project. |

## Stop at odm_georeferencing, and skip the 3D model

This project never uses the mesh, the texture, or the orthophoto. It consumes the georeferenced point cloud and nothing else. That file, `odm_georeferencing/odm_georeferenced_model.laz`, is written by the `odm_georeferencing` stage, which runs AFTER `odm_meshing` and `mvs_texturing` in ODM's fixed pipeline order:

```
odm_filterpoints -> odm_meshing -> mvs_texturing -> odm_georeferencing -> odm_dem -> odm_orthophoto -> odm_report -> odm_postprocess
```

This means two things:

1. `--end-with odm_filterpoints` is WRONG. Stopping there happens before georeferencing ever runs, so `odm_georeferenced_model.laz` would never be written. `--end-with odm_georeferencing` is the correct stop point: it's the earliest stage after which the file this project actually reads exists.
2. Because meshing and texturing sit *before* georeferencing, `--end-with` alone cannot skip them. `--skip-3dmodel` is what tells ODM not to build the mesh/texture branch at all. Without it, ODM still burns the time building a mesh nobody reads before it gets to georeferencing. On a real run (tyco_house, 77 images), `odm_meshing` alone took 27.5 minutes, more than opensfm and openmvs combined.

Skipping the mesh/texture branch has no effect on the point cloud itself. Georeferencing converts `odm_filterpoints/point_cloud.ply` directly to `.laz`; meshing and texturing are a separate, parallel branch that consumes the same filtered cloud as input but never feeds back into it. Same points, same density, same coordinates, just without the wasted detour.

### If PoissonRecon still runs even with `--skip-3dmodel` in the command

This has happened before (`big_house` run): the mesh ran despite intending to skip it. The cause was not a flaw in the flag or in ODM's stage order, it was that the flag was never actually passed to that particular `docker run` invocation. Do not re-theorize the stage order again, verify the flag landed:

1. Open `<project>/log.json`.
2. Check `options.skip_3dmodel`. If it reads `false`, the flag was not applied on that run, full stop; check the exact command that was typed/run.
3. `options.rerun` and `options.rerun_all` are also worth checking: a `--rerun-from` invocation reuses cached stage outputs and can mask which flags were actually in effect for that specific run.

`log.json` is ground truth for what a run actually did. It records the fully-resolved `options` dict and the real stage sequence with timestamps, use it to check a hypothesis before touching commands or docs again.

## Where the output lands

`C:\odm\datasets\<project_name>\odm_georeferencing\odm_georeferenced_model.laz`

This is the file `roofkit/io.py` reads. Verify it exists and is non-trivial in size before declaring the run successful.

## Quality flags: the tradeoff

`--pc-quality` is the lever worth pulling. It controls point cloud density directly, and density determines whether RANSAC has enough points on a roof facet to fit a plane cleanly. A sparse roof is the single most common cause of downstream segmentation failure in this project.

| Setting | Effect | When |
|---|---|---|
| `--pc-quality high` | Good density, reasonable runtime | Default. Start here. |
| `--pc-quality ultra` | Denser cloud, roughly double the runtime | Only if `high` produced a roof too sparse to segment. Escalate, do not start here. |

`--feature-quality` affects matching, not final density. `high` is sufficient; `ultra` roughly doubles runtime for marginal gain on this use case.

## Runtime expectations

Rough, and CPU/RAM dependent. Use these to tell "still working" from "hung":

| Images | Expect |
|---|---|
| ~30 | 15 to 30 minutes |
| ~100 | 45 to 90 minutes |
| ~230 | 1 to 3 hours |

If it appears stuck, check whether it is in the dense reconstruction stage. That stage is genuinely slow and prints little.

## Capture style determines whether the cloud is usable

This is the most important diagnostic in this skill. If a reconstruction succeeds but the downstream roof analysis fails, the cause is usually the capture, not the code.

| Capture style | Result |
|---|---|
| Nadir grid (camera straight down, parallel passes, 70-80% overlap) | Dense roof, sparse walls. Ideal for roof measurement. |
| Orbit only (camera angled at the house, circling) | Dense walls, sparse roof. RANSAC will find walls instead of roof facets. |
| Grid plus oblique orbit | Best. Standard mapping practice. |
| Cinematography b-roll (fast single orbit, no deliberate overlap, low resolution) | Not suitable for measurement. Walls dominate the cloud entirely. |

If the user reports that plane segmentation is grabbing walls, ask how the data was captured before touching the segmentation code.

## Video input

If the source is video rather than stills, frames must be extracted first. Use `prep/extract_frames.py`, which scores sharpness (variance-of-Laplacian) and spaces kept frames for roughly 70-80% overlap. ODM takes stills only.

## Scale and georeferencing

Without GPS in the image EXIF, the resulting cloud has correct SHAPE and PROPORTIONS but arbitrary units and arbitrary orientation. It is off by a single scale multiplier, and it is not level.

Consequences that bite downstream:
- Level the cloud (fit the ground plane, rotate so +Z is up) before measuring any pitch.
- Distance-based thresholds are scale-dependent and do NOT transfer between clouds. A threshold tuned on one cloud will be wrong on the next.
- Normal-direction thresholds ARE scale-independent and do transfer.
- One known real-world distance in the scene locks scale. Prefer the longest clean measurable edge; tape error dilutes over length.
