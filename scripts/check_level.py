# scripts/check_level.py -- fit ground, level the cloud, then re-fit ground and
# confirm the normal is now ~(0,0,1). Also view the leveled cloud.

import numpy as np
from roofkit.io import load_xyz_rgb
from roofkit.segment import fit_ground_plane, level_cloud
from view_cloud import show_points

CLOUD_PATH = r"C:\odm\datasets\tyco_house\odm_georeferencing\odm_georeferenced_model.laz"

points, colors = load_xyz_rgb(CLOUD_PATH)

# 1. find the ground's up-direction on the original (tilted) cloud
normal_before, _, _ = fit_ground_plane(points)
print(f"up-normal BEFORE leveling: {normal_before}")

# 2. rotate the whole cloud so that up-direction points along +Z
leveled = level_cloud(points, normal_before)

# 3. re-fit the ground on the leveled cloud; its normal should now be ~(0,0,1)
normal_after, _, _ = fit_ground_plane(leveled)
print(f"up-normal AFTER leveling:  {normal_after}")
print(f"(success looks like ~[0, 0, 1] or ~[0, 0, -1])")

show_points(leveled, colors)