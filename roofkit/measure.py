import numpy as np
from scipy.spatial import ConvexHull

def tilt_degrees(normal):
    """Angle of a surface from horizontal, given its normal (a, b, c).
    0 = flat (ground), 90 = vertical (wall). For a roof face, this tilt is the pitch."""
    a, b, c = normal
    length = np.sqrt(a*a + b*b + c*c)          # length of the normal arrow
    vertical_component = abs(c) / length        # how much it points straight up, 0 to 1
    angle_rad = np.arccos(vertical_component)    # angle of the normal away from vertical
    return np.degrees(angle_rad)                 # same as the surface's tilt from flat

def _facet_in_plane(points, normal, max_share=0.02):
    """Flatten a facet onto its own plane, then drop boundary 'spikes':
    any single point that by itself owns more than max_share of the hull's
    area is a stray sitting past the real roof edge, not a true corner.
    Returns the kept 2D coords and the matching kept 3D points."""
    n = np.asarray(normal, dtype=float)
    n = n / np.linalg.norm(n)
    u = np.cross(n, [0, 0, 1.0]); u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    centered = points - points.mean(axis=0)
    uv = np.column_stack([centered @ u, centered @ v])
    pts3d = points.copy()

    while len(uv) >= 4:
        hull = ConvexHull(uv)
        base = hull.volume
        worst_drop, worst = 0.0, None
        for vtx in hull.vertices:                 # only hull corners can be spikes
            keep = np.ones(len(uv), bool); keep[vtx] = False
            drop = base - ConvexHull(uv[keep]).volume
            if drop > worst_drop:
                worst_drop, worst = drop, vtx
        if worst_drop > max_share * base:          # this corner owns too much area
            uv = np.delete(uv, worst, axis=0)
            pts3d = np.delete(pts3d, worst, axis=0)  # delete from both in lockstep
        else:
            break                                  # no spike left, done
    return uv, pts3d


def facet_area(points, normal):
    """True surface area of a roof facet, in square meters."""
    uv, _ = _facet_in_plane(points, normal)
    return ConvexHull(uv).volume


def facet_boundary(points, normal):
    """The facet's outline in 3D, in loop order, after spike removal."""
    uv, pts3d = _facet_in_plane(points, normal)
    return pts3d[ConvexHull(uv).vertices]