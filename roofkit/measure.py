import numpy as np
from scipy.spatial import ConvexHull, Delaunay

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


def azimuth_degrees(normal):
    """Compass bearing of a facet's downhill direction: the horizontal
    component of its normal, as degrees clockwise from north. In a UTM
    frame x is easting and y is northing, so bearing = atan2(east, north).
    The normal is oriented upward first, because RANSAC's sign is a coin
    flip and both signs describe the same facet."""
    n = np.asarray(normal, float)
    if n[2] < 0:
        n = -n
    return float(np.degrees(np.arctan2(n[0], n[1])) % 360.0)


def vertical_from_pair(facet_a, facet_b):
    """True up recovered from a symmetric gable: the bisector of the two
    opposing facet normals. Valid exactly when the two real-world pitches
    are equal, which is the same symmetry assumption the gate itself uses.
    Feed the result to level_cloud if the gate rejects georeferenced Z."""
    up = _up_normal(facet_a) + _up_normal(facet_b)
    return up / np.linalg.norm(up)


# --- Ridge instrument (decision 2026-07-13: the reversal) ---
# A real ridge is LEVEL. The line where two roof planes meet can be
# measured directly from the points sitting on it, so its inclination IS
# the cloud's tilt along that direction, with no symmetry assumption
# anywhere. Two roughly orthogonal ridges fully determine which way is up.
# This replaces the symmetry residual as the vertical reference; the
# residual survives only as an asymmetry report.


def _plane_fit(points):
    """Least-squares plane of a point set: (unit normal oriented up,
    centroid). Same SVD idea as segment.fit_plane_svd; duplicated here
    because measure must not import segment (segment imports measure)."""
    centroid = points.mean(axis=0)
    _, _, vt = np.linalg.svd(points - centroid, full_matrices=False)
    n = vt[2]
    return (-n if n[2] < 0 else n), centroid


def ridge_line(points_a, points_b, contact_dist, min_contact=20):
    """Measure the line where two facets meet, from the points ON it.

    Fit a plane to each facet, intersect the planes for a first guess at
    the line, then collect each facet's CONTACT points: those within
    contact_dist of that line (contact_dist is a LENGTH, scale-dependent:
    callers derive it from median_nn_spacing). The line's direction is
    then re-measured as the principal direction of the contact points
    themselves, so the final reading comes from real geometry at the
    ridge, not from extrapolating two plane fits toward each other.

    Returns None when the planes are near-parallel (no defined line) or
    when fewer than min_contact points from either facet touch the line
    (the facets do not actually meet). Otherwise a dict:
      inclination_deg : signed slope of the line, + means it rises toward
                        azimuth_deg. A real ridge is level, so a nonzero
                        reading is cloud tilt along this direction.
      azimuth_deg     : compass bearing of the line, folded into [0, 180)
                        because a line has no forward end.
      frac_a, frac_b  : where the contact sits in each facet's own height
                        range, 0 bottom to 1 top. Near 1 on BOTH sides is
                        a true ridge pair; near 0 is a valley; mid-range
                        means the facets merely brush somewhere (the pair
                        0,2 failure mode) and prove nothing.
      n_a, n_b        : contact point counts, the instrument sample size.
    """
    points_a = np.asarray(points_a, float)
    points_b = np.asarray(points_b, float)
    na, ca = _plane_fit(points_a)
    nb, cb = _plane_fit(points_b)
    d = np.cross(na, nb)
    if np.linalg.norm(d) < 0.05:  # within ~3 degrees of parallel
        return None
    d = d / np.linalg.norm(d)
    # A point on the intersection line: solve the 3x3 system that puts it
    # on both planes and (to pin it along the line) closest to the
    # centroids' midpoint measured along d.
    mid = (ca + cb) / 2.0
    p0 = np.linalg.solve(np.vstack([na, nb, d]),
                         [na @ ca, nb @ cb, d @ mid])

    contacts, fracs = [], []
    for pts in (points_a, points_b):
        rel = pts - p0
        along = rel @ d
        radial = np.linalg.norm(rel - np.outer(along, d), axis=1)
        touch = pts[radial <= contact_dist]
        if len(touch) < min_contact:
            return None
        # Robust height range (1st..99th percentile) so a few stragglers
        # cannot stretch the denominator of the contact-height fraction.
        lo, hi = np.percentile(pts[:, 2], [1.0, 99.0])
        frac = (np.median(touch[:, 2]) - lo) / max(hi - lo, 1e-12)
        fracs.append(float(np.clip(frac, 0.0, 1.0)))
        contacts.append(touch)

    contact = np.vstack(contacts)
    _, _, vt = np.linalg.svd(contact - contact.mean(axis=0),
                             full_matrices=False)
    v = vt[0]  # the direction the contact strip is longest along
    az = float(np.degrees(np.arctan2(v[0], v[1])) % 360.0)
    if az >= 180.0:  # fold to [0, 180); flip v so inclination stays signed
        az -= 180.0
        v = -v
    incl = float(np.degrees(np.arctan2(v[2], np.hypot(v[0], v[1]))))
    return {"inclination_deg": incl, "azimuth_deg": az,
            "frac_a": fracs[0], "frac_b": fracs[1],
            "n_a": len(contacts[0]), "n_b": len(contacts[1])}


def tilt_from_ridges(ridges):
    """The cloud's tilt vector from ridge readings [(azimuth_deg,
    inclination_deg), ...]. A level real-world line reading slope s at
    bearing az constrains the tilt components: s = t_east*sin(az) +
    t_north*cos(az). Two ridges at distinct bearings solve this exactly;
    more are least squares. Returns (tilt_deg, uphill_azimuth_deg): level
    lines read UPHILL by tilt_deg toward that bearing. Small-angle linear
    in degrees, exact to ~1e-4 degrees at the 1-2 degree tilts this
    measures."""
    az = np.radians([r[0] for r in ridges])
    s = np.asarray([r[1] for r in ridges], float)
    coeffs = np.column_stack([np.sin(az), np.cos(az)])
    (t_east, t_north), *_ = np.linalg.lstsq(coeffs, s, rcond=None)
    return (float(np.hypot(t_east, t_north)),
            float(np.degrees(np.arctan2(t_east, t_north)) % 360.0))


def up_from_tilt(tilt_deg, uphill_az_deg):
    """True up in CLOUD coordinates for a measured tilt: level lines read
    uphill by tilt_deg toward uphill_az_deg, so true up leans away from
    that bearing. Feed the result to level_cloud. The null check required
    by the 2026-07-13 reversal: after leveling, re-measured ridge
    inclinations must read ~0."""
    t = np.tan(np.radians(tilt_deg))
    az = np.radians(uphill_az_deg)
    up = np.array([-t * np.sin(az), -t * np.cos(az), 1.0])
    return up / np.linalg.norm(up)


# --- Stage 7a: polygon area per facet (decision 2026-07-12) ---
# Area is measured IN THE FACET'S OWN PLANE (slope area, what shingles
# cover), not the ground footprint. The alpha shape is a shrink-wrapped
# outline: keep Delaunay triangles whose circumradius is at most alpha,
# sum their areas. Gaps narrower than ~2*alpha get bridged (point noise,
# small occlusions); gaps wider stay open (chimney and dormer holes).
# This REPLACES the earlier convex-hull facet_area: a hull is a rubber
# band that cannot follow concave outlines and silently fills holes.


def project_to_plane(points, normal):
    """2D coordinates of points in the facet's own plane. Build an
    orthonormal basis (u, v) perpendicular to the normal and express each
    centered point in it. Distances within the plane are preserved, so
    areas and lengths measured in 2D are the true slope quantities."""
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    helper = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(n, helper)
    u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    centered = points - points.mean(axis=0)
    return np.column_stack([centered @ u, centered @ v])


def alpha_shape_area(pts2d, alpha):
    """Area of the alpha shape of 2D points: the sum of Delaunay triangles
    with circumradius at most alpha. Alpha is a LENGTH and therefore
    scale-dependent: callers derive it from median_nn_spacing."""
    tri = Delaunay(pts2d).simplices
    a, b, c = pts2d[tri[:, 0]], pts2d[tri[:, 1]], pts2d[tri[:, 2]]
    ab, ac, bc = b - a, c - a, c - b
    cross = ab[:, 0] * ac[:, 1] - ab[:, 1] * ac[:, 0]
    tri_area = np.abs(cross) / 2.0
    la = np.linalg.norm(bc, axis=1)
    lb = np.linalg.norm(ac, axis=1)
    lc = np.linalg.norm(ab, axis=1)
    # Circumradius R = (product of side lengths) / (4 * area); degenerate
    # slivers (area ~ 0) get R = inf so they are never kept.
    with np.errstate(divide="ignore", invalid="ignore"):
        circum_r = np.where(tri_area > 1e-15, la * lb * lc / (4.0 * tri_area),
                            np.inf)
    return float(tri_area[circum_r <= alpha].sum())


def facet_area(points, normal, alpha):
    """Slope area of one facet: project into its plane, alpha-shape, sum."""
    return alpha_shape_area(project_to_plane(points, normal), alpha)