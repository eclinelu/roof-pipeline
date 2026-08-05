# roofkit/io.py -- the ONLY module that touches file formats. Everything else
# in the pipeline works on plain NumPy XYZ and knows nothing about laspy, LAZ,
# or ODM. Swap the reconstruction engine and only this file changes.
import laspy
import numpy as np

from .crop import crop_box

# How many points to decompress at a time in the streaming reader.
#
# THIS IS NOT A TUNING KNOB AND IT CANNOT CHANGE THE ANSWER. It trades peak
# memory against per-chunk overhead and nothing else: the survivors of a box
# test do not depend on how the points were grouped on the way in, and the
# colour divisor is deliberately computed globally (see load_xyz_rgb_cropped)
# rather than per chunk, which is the one way chunking COULD have changed the
# result. `test_io_chunked.py` asserts that invariance directly by running two
# different chunk sizes and requiring bit-identical output.
#
# 4M points is roughly 100-150 MB of decompressed point record plus a 96 MB
# float64 xyz view, which keeps the reader's own footprint well inside a
# spare gigabyte while still amortising laspy's per-chunk cost.
DEFAULT_CHUNK = 4_000_000


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


def load_xyz_rgb_cropped(path, min_corner, max_corner, chunk_size=DEFAULT_CHUNK):
    """load_xyz_rgb + crop_box, without ever holding the whole cloud.

    Returns (points, colors) for the points inside the box, identical in value
    and in ORDER to::

        points, colors = load_xyz_rgb(path)
        points, mask = crop_box(points, min_corner, max_corner)
        colors = colors[mask]

    WHY THIS EXISTS. The ultra reconstruction of big_house is 90.2M points.
    `laspy.read` decompresses all of it and then `las.xyz` and the colour stack
    each allocate another (N, 3) float64 array, which peaks near 8 GB against
    the 6.8 GB of free physical memory this machine actually had. The crop
    throws most of it away moments later, so the full cloud never needed to be
    resident at all. Cropping DURING the read is the fix, and file reading is
    exactly what this module is for.

    THE ONE PLACE CHUNKING COULD HAVE CHANGED THE ANSWER, and how it is closed.
    `load_xyz_rgb` chooses its colour divisor by looking at the maximum over
    the ENTIRE cloud: 65535 if anything exceeds 255, else 255. That is a global
    property. Deciding it per chunk would give an 8-bit divisor to a dark chunk
    and a 16-bit divisor to a bright one in the same file, scaling two parts of
    one cloud differently -- a silent, plausible-looking corruption that would
    land straight in the ExG colour filter downstream.

    So the raw integer colours of the SURVIVORS are accumulated unscaled, the
    running maximum is tracked over EVERY point read (survivor or not, because
    that is what the whole-cloud rule means), and the division happens once at
    the end. The scaling is therefore global by construction, not by luck.

    Order is preserved because laspy's chunk iterator yields points in file
    order and the per-chunk survivors are concatenated in the order the chunks
    arrived, so the result is the same subsequence the one-shot path produces.

    The box test itself is delegated to `crop_box`, not reimplemented. A second
    copy of a boundary comparison is a second place for `>=` to drift to `>`.
    """
    xs, cs = [], []
    raw_max = 0
    with laspy.open(str(path)) as reader:
        for chunk in reader.chunk_iterator(chunk_size):
            # `.xyz` is a LasData property and does not exist on a chunk's
            # point record, so the same array is built from the scale-aware
            # x/y/z views. These apply the header's scale and offset exactly as
            # LasData.xyz does; the equivalence test is what proves it.
            pts = np.column_stack([chunk.x, chunk.y, chunk.z])
            raw = np.column_stack([chunk.red, chunk.green, chunk.blue])
            # The maximum must be over every point in the file, matching the
            # whole-cloud rule in load_xyz_rgb, so it is taken BEFORE cropping.
            if raw.size:
                raw_max = max(raw_max, int(raw.max()))
            kept, mask = crop_box(pts, min_corner, max_corner)
            if kept.size:
                xs.append(kept)
                cs.append(raw[mask])

    if not xs:
        return (np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=float))

    points = np.concatenate(xs, axis=0)
    colors = np.concatenate(cs, axis=0)
    divisor = 65535.0 if raw_max > 255 else 255.0
    return points, colors / divisor