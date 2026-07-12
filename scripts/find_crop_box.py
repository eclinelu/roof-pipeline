# scripts/find_crop_box.py
# Throwaway exploration: find the bounding box that isolates the MAIN house and
# excludes the second outbuilding. Edit MIN_CORNER / MAX_CORNER each pass and
# re-run. Now prints the cropped cloud's own bounding box so you can reason about
# which axis to tighten instead of guessing.

import numpy as np
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box
from view_cloud import show_points

CLOUD_PATH = r"C:\odm\datasets\tyco_house\odm_georeferencing\odm_georeferenced_model.laz"

MIN_CORNER = (-0.5, 0.1, -3.0)   # (x_min, y_min, z_min)
MAX_CORNER = ( 0.8,  0.8,  1.5)   # (x_max, y_max, z_max)

points, colors = load_xyz_rgb(CLOUD_PATH)
print(f"before crop: {len(points):,} points")

cropped, mask = crop_box(points, MIN_CORNER, MAX_CORNER)
cropped_colors = colors[mask]
print(f"after crop:  {len(cropped):,} points")

# --- the new part: report the cropped cloud's OWN bounding box ---
# This is the extent of only the points that survived. Compare these numbers to
# what you SEE in the viewer to learn which axis points toward the outbuilding.
lo = cropped.min(axis=0)   # smallest x, y, z among surviving points
hi = cropped.max(axis=0)   # largest  x, y, z
span = hi - lo             # size along each axis

print("\ncropped bounding box (native units):")
print(f"  X: {lo[0]:7.2f} .. {hi[0]:7.2f}   span {span[0]:6.2f}")
print(f"  Y: {lo[1]:7.2f} .. {hi[1]:7.2f}   span {span[1]:6.2f}")
print(f"  Z: {lo[2]:7.2f} .. {hi[2]:7.2f}   span {span[2]:6.2f}")

show_points(cropped, cropped_colors)