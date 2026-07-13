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


# --- Z-verification gate (decision 2026-07-12) ---
# Georeferenced Z comes from meter-grade GPS and is an ASSUMPTION as a
# gravity reference. Before any pitch is reported, measure the residual
# tilt using the building's own symmetry: opposing gable facets must read
# equal pitch, so half their difference IS the Z tilt.


def _up_normal(facet):
    """Facet normal as a unit vector oriented upward (z >= 0). RANSAC's
    normal sign is arbitrary, so orient before comparing directions."""
    n = np.asarray(facet["normal"], float)
    n = n / np.linalg.norm(n)
    return -n if n[2] < 0 else n


def opposing_pairs(facets, direction_tol_deg=15.0, pitch_tol_deg=10.0):
    """Indices (i, j) of facets that face each other like two sides of a
    gable: horizontal components of their normals point in opposite
    directions (within direction_tol_deg) and their pitches are similar
    (within pitch_tol_deg). Both tolerances are angles: scale-independent."""
    pairs = []
    for i in range(len(facets)):
        for j in range(i + 1, len(facets)):
            hi, hj = _up_normal(facets[i]).copy(), _up_normal(facets[j]).copy()
            hi[2] = 0.0
            hj[2] = 0.0
            li, lj = np.linalg.norm(hi), np.linalg.norm(hj)
            if li < 1e-9 or lj < 1e-9:
                continue  # a flat facet faces no direction
            angle = np.degrees(np.arccos(np.clip(hi @ hj / (li * lj), -1, 1)))
            if (angle >= 180.0 - direction_tol_deg and
                    abs(facets[i]["pitch"] - facets[j]["pitch"]) <= pitch_tol_deg):
                pairs.append((i, j))
    return pairs


def z_tilt_residual(facets, direction_tol_deg=15.0, pitch_tol_deg=10.0):
    """(residual_degrees, pairs). Residual = the WORST half-difference of
    pitch across all opposing pairs: conservative on purpose, because the
    gate exists to catch error, not to average it away. Returns (None, [])
    when no pair exists: the gate has no instrument, and that fact must
    reach the report rather than pass silently."""
    pairs = opposing_pairs(facets, direction_tol_deg, pitch_tol_deg)
    if not pairs:
        return None, []
    residuals = [abs(facets[i]["pitch"] - facets[j]["pitch"]) / 2.0
                 for i, j in pairs]
    return max(residuals), pairs


def vertical_from_pair(facet_a, facet_b):
    """True up recovered from a symmetric gable: the bisector of the two
    opposing facet normals. Valid exactly when the two real-world pitches
    are equal, which is the same symmetry assumption the gate itself uses.
    Feed the result to level_cloud if the gate rejects georeferenced Z."""
    up = _up_normal(facet_a) + _up_normal(facet_b)
    return up / np.linalg.norm(up)