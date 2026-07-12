# scripts/find_crop_leveled.py
# Real pipeline order: load -> level the full cloud -> crop the house.
# The crop box must be re-tuned here because leveling moved every point, so the
# old tilted-cloud box numbers no longer apply.
#
# FIRST RUN: leave MIN_CORNER/MAX_CORNER as None to see the whole leveled cloud
# and print its bounding box. Read off numbers, then fill in the box and re-run,
# tightening each pass until only the main house remains.

import numpy as np
from roofkit.io import load_xyz_rgb
from roofkit.segment import fit_ground_plane, level_cloud
from roofkit.crop import crop_box
from view_cloud import show_points

CLOUD_PATH = r"C:\odm\datasets\tyco_house\odm_georeferencing\odm_georeferenced_model.laz"

# Set to None on the first run to skip cropping and just inspect the leveled box.
MIN_CORNER = (-0.8, -2.1, -3.0)   # e.g. (x_min, y_min, z_min)
MAX_CORNER = (1.0, 0, 1.0)   # e.g. (x_max, y_max, z_max)

# --- load and level (this is the real pipeline front-end) ---
points, colors = load_xyz_rgb(CLOUD_PATH)
up_normal, _, _ = fit_ground_plane(points)
leveled = level_cloud(points, up_normal)

# --- report the leveled cloud's bounding box, so you can choose a box ---
lo = leveled.min(axis=0)
hi = leveled.max(axis=0)
span = hi - lo
print("leveled bounding box:")
print(f"  X: {lo[0]:7.2f} .. {hi[0]:7.2f}   span {span[0]:6.2f}")
print(f"  Y: {lo[1]:7.2f} .. {hi[1]:7.2f}   span {span[1]:6.2f}")
print(f"  Z: {lo[2]:7.2f} .. {hi[2]:7.2f}   span {span[2]:6.2f}   <- height now (Z is true up)")

# --- crop only if a box is set; otherwise show the whole leveled cloud ---
if MIN_CORNER is None or MAX_CORNER is None:
    print("\nNo box set: showing full leveled cloud. Read the box numbers above.")
    show_points(leveled, colors)
else:
    cropped, mask = crop_box(leveled, MIN_CORNER, MAX_CORNER)
    print(f"\ncropped: {len(cropped):,} points")
    show_points(cropped, colors[mask])