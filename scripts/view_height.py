import numpy as np
import open3d as o3d
from roofkit.io import load_xyz

# Point this at wherever you saved the gable file.
path = r"C:\odm\datasets\gable\clean_gable_lidar.laz"
points = load_xyz(path)

# This cloud has no color, so we invent one: color each point by its height.
z = points[:, 2]                          # the height of every point (third column)
t = (z - z.min()) / (z.max() - z.min())   # rescale heights to run from 0 to 1

colors = np.zeros((len(points), 3))       # one RGB row per point, all black to start
colors[:, 0] = t                          # red channel rises with height
colors[:, 2] = 1 - t                      # blue channel rises toward the ground

cloud = o3d.geometry.PointCloud()
cloud.points = o3d.utility.Vector3dVector(points)
cloud.colors = o3d.utility.Vector3dVector(colors)

print("Opening viewer. Low points blue, high points red. Close window to exit.")
o3d.visualization.draw_geometries([cloud])