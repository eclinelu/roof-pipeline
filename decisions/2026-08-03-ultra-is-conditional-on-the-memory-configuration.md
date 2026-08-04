### 2026-08-03: `--pc-quality ultra` COMPLETED, and the default is conditional on the WSL2 memory configuration, which is now part of the reconstruction environment

`decisions/2026-07-30-ultra-becomes-the-odm-default.md` made ultra the ODM
default. It is not edited, and it is not wrong. This entry adds the condition
that entry could not state, because at the time it was written **ultra had never
completed on this machine**. It has now completed once. What made the difference
is not the ODM flag.

## What happened

big_house was reconstructed at `--pc-quality ultra` on a clean dataset
(`C:\odm\datasets\big_house_ultra`, everything but `images/` deleted first, 233
images verified byte-identical before and after). It succeeded.

| | value |
|---|---|
| ODM version | 3.6.0 |
| result | `log.json` `success: true`, all 9 stages finished |
| wall clock | **172 min** (2026-08-03 23:02:54 to 2026-08-04 01:54:57 UTC) |
| peak container RAM | **22.390 GiB of the 23.470 GiB cap, 95.4 %** |
| peak swap in use | **~12.6 GiB** of 32 GiB, concurrent with that RAM peak |
| cloud | `big_house_ultra/odm_georeferencing/odm_georeferenced_model.laz`, 302.8 MB |
| points | **90,151,819**, against 21,325,293 for the medium canonical cloud |
| density | **4.23x** the medium cloud, on the same scene |

The two previous ultra attempts both died at **9.01 % of depth-map fusion**, OOM
killed. This attempt passed that point and finished fusion.

## Why the default is conditional, and on WHAT exactly

The naive reading of the 2026-07-30 entry is "use `--pc-quality ultra`". That
instruction is not sufficient, and following it on a differently configured
machine reproduces the two failures rather than this success.

At the fusion peak the run held **22.4 GiB resident AND 12.6 GiB of swap at the
same time**, a working set of roughly **35 GiB**. The configuration in place for
the two failed attempts offered 15.35 GiB RAM and 4 GiB swap: **19.4 GiB total**,
which is not close. So:

**`swap=32GB` is doing decisive work here, not `memory=24GB` alone.** RAM peaked
at 95.4 % of its cap. A 24 GiB cap with the old 4 GiB swap would have had roughly
28 GiB against a ~35 GiB working set and would very likely have died too. It is
tempting to record "we raised memory to 24 GB and it worked"; that is the wrong
lesson and would not transfer.

The file, verbatim, at `C:\Users\eclin\.wslconfig`:

```ini
[wsl2]
memory=24GB
swap=32GB
```

**This is part of the reconstruction environment, in the same sense that the ODM
version is.** It is not an incidental machine setting and it is not tuning. It
belongs beside "ODM 3.6.0" and "Docker" in any description of how a cloud in this
project was produced. A cloud produced at ultra without it is not reproducible
and, on the evidence of two attempts, does not exist.

The file lives outside the repo because WSL2 requires it at that path. That is a
real weakness in the record and it is stated rather than hidden: the repo cannot
prove what the config was at reconstruction time. Runtime memory is therefore
now reported by the monitor and quoted in entries like this one, so the numbers
survive even though the file does not.

## What is NOT claimed

- **No accuracy claim.** big_house is the development site
  (`decisions/2026-07-29-development-vs-validation-sites.md`). 4.23x the points
  is a density fact, not a measurement improvement.
- **No defect is closed.** M1b, M2, M3, M4, M5, M6, M7 are untouched. Per the
  density-dependent rule, a defect that vanishes on this cloud is
  DENSITY-DEPENDENT, not fixed.
- **No pitch correction.** The 1.83 deg bias remains accepted-untested.
- **The analysis pass has not been run** on this cloud. Reconstruction only.
- **One success is not a reliability claim.** Ultra completed once, with RAM at
  95.4 % of cap. That is a narrow margin, not headroom.

## Two things found on the way, recorded because they cost real time

1. **The canonical medium cloud was built with `skip_3dmodel = False`**, so
   meshing and texturing ran, despite `CLAUDE.md` instructing that
   `--skip-3dmodel` is always required. This run matched the baseline rather
   than introduce a second change, so it also meshed and textured. `CLAUDE.md`
   and the actual canonical run disagree, and the log is the record.
2. **The canonical medium cloud came from a RESUMED run.** Its `rerun_from` lists
   `odm_filterpoints` through `odm_postprocess`. This ultra run was clean. The
   comparison above is therefore clean-run against resumed-run.

Both are reported, not fixed.

## How "one change only" was made checkable

Rather than assert that only `pc_quality` changed, the two runs' `log.json`
option dicts were diffed programmatically: 91 options on each side, exactly one
difference, `pc_quality: medium -> ultra`.

A first version of that check compared the ultra CONSOLE dump against the medium
`log.json` and reported a spurious second difference,
`undistorted_image_max_size`. That key is absent from BOTH `log.json` files; it
is a value ODM computes and prints, not an option. The lesson is small and
general: **compare like sources, or the diff measures the sources rather than the
runs.**

## The extent assertion that fired, and why it was not simply relaxed

The cloud comparison asserted that the two clouds cover the same scene, on the
grounds that a density ratio between different scenes means nothing. It FAILED:
header Z extent 36.78 (medium) against 25.05 (ultra), a 31.9 % difference.

min and max are the two most outlier-sensitive statistics available; one stray
point sets them. So the question was put to the data instead of the threshold:

| axis | p0-p100 | p0.1-p99.9 | p1-p99 |
|---|---|---|---|
| X | +19.7 % | +2.4 % | **+0.6 %** |
| Y | +9.3 % | +0.7 % | **+0.3 %** |
| Z | **-31.9 %** | +2.6 % | **+0.0 %** |

The worst disagreement collapses from **31.9 % to 0.6 %** once outliers are
trimmed, and the p1-p99 Z span is **8.25 in both clouds**. The clouds cover the
same volume; the header gap is outlier REACH, and the medium cloud reaches
further vertically. The density comparison stands.

This is recorded because the alternative was available and wrong: widen the
threshold until the assertion passes. The threshold was left alone and the
underlying question was answered with a measurement.
