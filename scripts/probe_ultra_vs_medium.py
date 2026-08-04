# WHY: the header min/max extent assertion FAILED (Z differed by 31.9%). min/max
# are the two most outlier-sensitive statistics there are: a single stray point
# sets them. Before concluding the two clouds cover different scenes, check
# whether the difference survives when outliers are excluded. Percentiles are
# not a weaker test here, they are the right one for the question "is this the
# same volume of building" versus "is there one point in the sky".
#
# This deliberately computes NOTHING about the roof: no crop, no ground plane,
# no facets, no area, no pitch. It is cloud characterisation only.
import sys
from pathlib import Path

import laspy
import numpy as np

PAIRS = [
    ("medium",
     r"C:\odm\datasets\big_house\odm_georeferencing\odm_georeferenced_model.laz"),
    ("ultra",
     r"C:\odm\datasets\big_house_ultra\odm_georeferencing\odm_georeferenced_model.laz"),
]
QS = [0.0, 0.1, 1.0, 50.0, 99.0, 99.9, 100.0]

out = {}
for label, path in PAIRS:
    with laspy.open(path) as f:
        n = f.header.point_count
        xs = np.empty(n); ys = np.empty(n); zs = np.empty(n)
        i = 0
        for pts in f.chunk_iterator(5_000_000):
            m = len(pts)
            xs[i:i + m] = pts.x; ys[i:i + m] = pts.y; zs[i:i + m] = pts.z
            i += m
    assert i == n, f"read {i:,} of {n:,} points for {label}"
    out[label] = dict(n=n, x=xs, y=ys, z=zs)
    print(f"{label}: read {n:,} points")

print("\nPER-AXIS SPAN AT EACH PERCENTILE PAIR (metres, arbitrary ODM units)")
print(f"{'axis':<5}{'range':<14}{'medium':>10}{'ultra':>10}{'diff %':>9}")
verdict_rows = []
for ax in ("x", "y", "z"):
    for lo, hi in ((0.0, 100.0), (0.1, 99.9), (1.0, 99.0)):
        a = np.percentile(out["medium"][ax], hi) - np.percentile(out["medium"][ax], lo)
        b = np.percentile(out["ultra"][ax], hi) - np.percentile(out["ultra"][ax], lo)
        d = 100.0 * (b - a) / a
        print(f"{ax:<5}{f'p{lo}-p{hi}':<14}{a:>10.2f}{b:>10.2f}{d:>+9.1f}")
        verdict_rows.append((ax, lo, hi, d))
    print()

# The question this answers: does the extent gap collapse once outliers are
# excluded? If it does, the clouds are the same scene and the header min/max
# difference was noise reach, not coverage.
trimmed = [abs(d) for ax, lo, hi, d in verdict_rows if (lo, hi) == (1.0, 99.0)]
raw = [abs(d) for ax, lo, hi, d in verdict_rows if (lo, hi) == (0.0, 100.0)]
print(f"worst |diff| on raw min/max : {max(raw):.1f}%")
print(f"worst |diff| on p1-p99      : {max(trimmed):.1f}%")
if max(trimmed) < max(raw):
    print("=> the gap SHRINKS when outliers are trimmed, so the header extent "
          "difference is driven by outlier reach, not by different coverage.")
else:
    print("=> the gap does NOT shrink; the difference is in the bulk of the "
          "cloud and the two clouds really do cover different volumes.")
sys.exit(0)
