import laspy
import numpy as np

def load_xyz(path):
    """Read a point cloud file and return its points as plain numbers."""
    las = laspy.read(path)
    return las.xyz

def load_xyz_rgb(path):
    """Read a point cloud and return BOTH its points and its colors.
    Points are meters, shape (N, 3). Colors are 0-1 RGB, shape (N, 3)."""
    las = laspy.read(path)
    points = las.xyz
    colors = np.column_stack([las.red, las.green, las.blue])
    divisor = 65535.0 if colors.max() > 255 else 255.0
    colors = colors / divisor
    return points, colors