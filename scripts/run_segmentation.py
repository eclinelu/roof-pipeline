# scripts/run_segmentation.py
# Full chain so far: load -> level -> crop -> find roof planes.
# Prints each facet's pitch and shows the facets in distinct colors so you can
# confirm by eye that RANSAC grabbed the real roof faces.

import numpy as np
from roofkit.io import load_xyz_rgb
from roofkit.segment import fit_ground_plane, level_cloud, find_roof_planes
from roofkit.crop import crop_box
from view_cloud import show_points

CLOUD_PATH = r"C:\odm\datasets\tyco_house\odm_georeferencing\odm_georeferenced_model.laz"

# Your tuned crop box on the LEVELED cloud (the one that gave the clean house).
MIN_CORNER = (-0.8, -2.1, -3.0)
MAX_CORNER = ( 1.0,  0.0,  1.0)

# --- load, level, crop ---
points, colors = load_xyz_rgb(CLOUD_PATH)
up_normal, _, _ = fit_ground_plane(points)
leveled = level_cloud(points, up_normal)
house, mask = crop_box(leveled, MIN_CORNER, MAX_CORNER)
print(f"house crop: {len(house):,} points")

# --- find roof planes ---
facets = find_roof_planes(house, distance_threshold=0.02)
print(f"\nfound {len(facets)} roof facet(s):")
for i, f in enumerate(facets):
    print(f"  facet {i}: pitch {f['pitch']:.1f} deg, {len(f['points']):,} points")

# --- visualize: show ONLY the facet points, each facet its own color ---
# No gray base, no overlapping points, so draw-order can't hide anything.
palette = [
    [1, 0, 0], [0, 0.4, 1], [0, 0.8, 0], [1, 0.6, 0],
    [0.7, 0, 1], [1, 1, 0], [0, 1, 1], [1, 0, 0.6],
]

facet_pts = []
facet_cols = []
for i, f in enumerate(facets):
    color = palette[i % len(palette)]
    facet_pts.append(f["points"])
    facet_cols.append(np.tile(color, (len(f["points"]), 1)))

vis_points = np.vstack(facet_pts)
vis_colors = np.vstack(facet_cols)

print("\nShowing ONLY the facets, each a distinct color:")
print("  facet 0 = red, facet 1 = blue, facet 2 = green, facet 3 = orange, ...")
show_points(vis_points, vis_colors)