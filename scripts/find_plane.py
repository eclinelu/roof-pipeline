import numpy as np
import open3d as o3d
from roofkit.io import load_xyz

path = r"C:\odm\datasets\gable\clean_gable_lidar.laz"
points = load_xyz(path)

# Hand the plain numbers to Open3D's cloud container.
cloud = o3d.geometry.PointCloud()
cloud.points = o3d.utility.Vector3dVector(points)

# RANSAC: find the single flat surface with the most points lying on it.
plane_model, inlier_indices = cloud.segment_plane(
    distance_threshold=0.2,   # a point within 0.2 m of the plane counts as "on it"
    ransac_n=3,               # 3 points are the minimum to define a plane
    num_iterations=1000,      # how many random guesses RANSAC tries
)

a, b, c, d = plane_model
print("Plane normal (a, b, c):", round(a, 3), round(b, 3), round(c, 3))
print("Points on this plane:", len(inlier_indices), "of", len(points))

# Split the cloud into "on the plane" vs "everything else", color, and view.
on_plane = cloud.select_by_index(inlier_indices)
the_rest = cloud.select_by_index(inlier_indices, invert=True)
on_plane.paint_uniform_color([1.0, 0.0, 0.0])    # red = the plane RANSAC found
the_rest.paint_uniform_color([0.7, 0.7, 0.7])    # gray = everything else

o3d.visualization.draw_geometries([on_plane, the_rest])