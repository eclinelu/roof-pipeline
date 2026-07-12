import numpy as np


def distance(point_a, point_b):
    """Straight-line distance between two 3D points, in meters."""
    a = np.array(point_a, dtype=float)
    b = np.array(point_b, dtype=float)
    return np.sqrt(np.sum((a - b) ** 2))