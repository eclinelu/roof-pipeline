import numpy as np
import open3d as o3d
from roofkit.measure import tilt_degrees
from scipy.spatial.transform import Rotation

def clean_outliers(points, nb_neighbors=20, std_ratio=2.0):
    """Remove sparse floating points (noise) that sit far from their neighbors.
    Returns the cleaned points as a NumPy array."""
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    cleaned, kept_indices = cloud.remove_statistical_outlier(
        nb_neighbors=nb_neighbors, std_ratio=std_ratio)
    return np.asarray(cleaned.points)

def fit_ground_plane(points, distance_threshold=0.2):
    """Find the ground: the single largest flat surface in the cloud.

    Uses one RANSAC pass to grab the biggest plane, which after cropping is the
    lawn. Returns:
      normal        : (3,) unit vector pointing UP out of the ground (true vertical)
      ground_points : the points that lie on the ground plane
      inlier_mask   : (N,) True/False, which input points are ground
    """
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)

    # RANSAC for the single biggest flat plane. Same call find_roof_planes uses,
    # but we run it ONCE and take whatever the largest plane is, no pitch filter,
    # because here we WANT the flat ground, not a roof.
    plane_model, inliers = cloud.segment_plane(
        distance_threshold=distance_threshold, ransac_n=3, num_iterations=1000)

    normal = np.asarray(plane_model[:3], dtype=float)   # (a, b, c)
    normal = normal / np.linalg.norm(normal)            # make it length 1 (a unit vector)

    # Sign fix: RANSAC may return the normal pointing down into the ground instead
    # of up. We want "up". In the cloud's own frame, the roof/house sits on the
    # HIGH side of the ground. We can't trust Z (it's tilted), so we orient the
    # normal to point toward the cloud's average point, which sits above the
    # ground (house + points are mostly above the lawn, not below it).
    cloud_center = points.mean(axis=0)
    ground_center = points[inliers].mean(axis=0)
    up_ish = cloud_center - ground_center      # rough "toward the bulk of the cloud"
    if normal @ up_ish < 0:                     # dot product negative = normal points away from the bulk
        normal = -normal                        # flip it to point up

    # Build a True/False mask of which points are ground (for later use).
    inlier_mask = np.zeros(len(points), dtype=bool)
    inlier_mask[inliers] = True

    ground_points = points[inlier_mask]
    return normal, ground_points, inlier_mask

def find_roof_planes(points, distance_threshold=0.2, min_points=300,
                     min_pitch=10, max_pitch=60, max_planes=8):
    """Peel flat planes off the cloud one at a time with RANSAC, keeping only
    the ones tilted like a roof. Returns a list of facets, each a dict holding
    that facet's points, its normal, and its pitch in degrees."""
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)

    facets = []
    for _ in range(max_planes):
        # Stop if too little is left to be a real surface.
        if len(cloud.points) < min_points:
            break

        # RANSAC: grab the biggest flat plane in what remains.
        plane_model, inliers = cloud.segment_plane(
            distance_threshold=distance_threshold, ransac_n=3, num_iterations=1000)

        # If even the biggest remaining plane is tiny, we're done finding surfaces.
        if len(inliers) < min_points:
            break

        normal = plane_model[:3]          # (a, b, c) from (a, b, c, d)
        pitch = tilt_degrees(normal)

        # Keep it only if it tilts like a roof (not flat ground, not a wall).
        if min_pitch <= pitch <= max_pitch:
            plane_points = np.asarray(cloud.select_by_index(inliers).points)
            facets.append({"points": plane_points, "normal": np.asarray(normal), "pitch": pitch})

        # Remove this plane's points (kept or not) so the next loop finds the next surface.
        cloud = cloud.select_by_index(inliers, invert=True)

    # Greedy peeling steals shared-edge points: at a ridge the two roof
    # planes lie within the RANSAC band of EACH OTHER, so whichever plane is
    # found first absorbs a strip of its neighbor's points, inflating its
    # area and tilting its fit (order-dependent, so also not reproducible).
    # One reassignment pass removes the order dependence: pool every point
    # that belongs to any facet, hand each point to its NEAREST plane, then
    # refit each plane to its final members. RANSAC proposes, the final
    # consensus refits.
    if len(facets) > 1:
        pool = np.vstack([f["points"] for f in facets])
        dists = np.column_stack([_point_plane_dist(pool, f) for f in facets])
        owner = dists.argmin(axis=1)          # index of the closest plane, per point
        for k, f in enumerate(facets):
            mine = pool[owner == k]
            if len(mine) < 3:                 # a plane needs 3 points; keep RANSAC's answer
                continue
            # Refit: the plane normal is the direction the point set spreads
            # LEAST along. SVD of the centered points gives the three spread
            # directions sorted largest to smallest; row 2 is the smallest,
            # i.e. the normal. (Same eigen-idea as the planarity filter.)
            centered = mine - mine.mean(axis=0)
            _, _, vt = np.linalg.svd(centered, full_matrices=False)
            f["points"] = mine
            f["normal"] = vt[2]
            f["pitch"] = tilt_degrees(vt[2])

    return facets


def _point_plane_dist(points, facet):
    """Perpendicular distance from each point to a facet's plane (the plane
    through the facet's centroid with the facet's normal)."""
    n = np.asarray(facet["normal"], float)
    n = n / np.linalg.norm(n)
    return np.abs((points - facet["points"].mean(axis=0)) @ n)

def level_cloud(points, up_normal):
    """Rotate the whole cloud so `up_normal` points along +Z (true vertical).

    points    : (N, 3) array to rotate.
    up_normal : (3,) the ground's 'up' direction, from fit_ground_plane.

    Returns the rotated points, same shape. After this, the ground is horizontal
    and the Z axis is真 vertical, so tilt_degrees and friends work correctly.
    """
    up_normal = np.asarray(up_normal, dtype=float)
    up_normal = up_normal / np.linalg.norm(up_normal)   # ensure length 1

    target = np.array([0.0, 0.0, 1.0])                  # where we want 'up' to point: +Z

    # Axis to rotate around = cross product of current-up and target-up.
    # This vector is perpendicular to both; it's the hinge we pivot on.
    axis = np.cross(up_normal, target)
    axis_length = np.linalg.norm(axis)

    # Degenerate case: if up_normal already ~equals target, the cross product is
    # ~zero and there's no meaningful axis. That just means "already level" --
    # return the points unchanged rather than dividing by zero.
    if axis_length < 1e-8:
        return points.copy()

    axis = axis / axis_length                           # make the axis a unit vector

    # Angle between current-up and target = arccos of their dot product.
    # Both are unit vectors, so the dot product IS the cosine of the angle.
    angle = np.arccos(np.clip(up_normal @ target, -1.0, 1.0))

    # Build the rotation from axis + angle. SciPy wants a "rotation vector":
    # the axis scaled by the angle (in radians). Then apply it to every point.
    rotation = Rotation.from_rotvec(axis * angle)
    return rotation.apply(points)