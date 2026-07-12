import open3d as o3d
import numpy as np
from roofkit.io import load_xyz_rgb


def show_points(points, colors=None):
    """Open a 3D window showing the given points.

    points : (N, 3) array of XYZ, in any units. Passed in from memory, so this
             works on intermediate results (cropped cloud, etc.) with no file.
    colors : optional (N, 3) array of 0-1 RGB. If None, points draw in a
             default uniform color. This lets you view clouds that have no
             color, like a cropped subset you don't care to color.
    """
    # Work on a COPY so the display-only shift below never changes the caller's
    # real coordinates. points - ... already creates a new array, but np.asarray
    # guards against surprises if a list was passed in.
    points = np.asarray(points)

    # Shift a copy next to the origin so Open3D draws it crisply. This is a
    # DISPLAY trick only. It does not leave this function; the caller's data and
    # any measurements are unaffected.
    draw_points = points - points.min(axis=0)

    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(draw_points)
    if colors is not None:
        cloud.colors = o3d.utility.Vector3dVector(colors)

    print("Opening viewer. Drag to rotate, scroll to zoom, close the window to exit.")
    o3d.visualization.draw_geometries([cloud])


# When this file is run directly (not imported), load a cloud from disk and show
# it. This keeps the old "view a file" behavior working. The `if __name__ ...`
# guard means this block runs ONLY on `python scripts/view_cloud.py`, and is
# skipped when another script does `from view_cloud import show_points`.
if __name__ == "__main__":
    path = r"C:\odm\datasets\tyco_house\odm_georeferencing\odm_georeferenced_model.laz"
    points, colors = load_xyz_rgb(path)
    show_points(points, colors)