# scripts/find_crop_box.py
# Read coordinates off a cloud by shift-clicking points in a viewer.
# Dataset-agnostic: reads the cloud path (and any existing crop) from
# <dataset>\roofkit.json, same as isolate_roof.py.
#
#   python scripts/find_crop_box.py C:\odm\datasets\big_house
#
# Workflow: SHIFT+LEFT CLICK points in the window (each pick prints its XYZ
# to this terminal immediately), press Q to close, and the script reprints
# every picked point plus a paste-ready crop_min/crop_max snippet built
# from the picks' extremes.
import argparse
import json
import numpy as np
import open3d as o3d
from dataset_config import load_config
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box

MAX_VIEW_POINTS = 2_000_000  # keep the picking viewer responsive


def print_bbox(points, label):
    lo, hi = points.min(axis=0), points.max(axis=0)
    span = hi - lo
    print(f"\n{label} bounding box (cloud units):")
    for ax, name in enumerate("XYZ"):
        print(f"  {name}: {lo[ax]:12.2f} .. {hi[ax]:12.2f}   span {span[ax]:8.2f}")


def main():
    ap = argparse.ArgumentParser(
        description="Shift-click points in a cloud to read coordinates for "
                    "roofkit.json (crop corners, ground and eave heights).")
    ap.add_argument("dataset", help="dataset directory (holds roofkit.json)")
    args = ap.parse_args()
    cfg = load_config(args.dataset)

    points, colors = load_xyz_rgb(cfg["cloud_path"])
    print(f"raw cloud: {len(points):,} points")
    print_bbox(points, "raw")
    # Fixed origin for the relative printout: the RAW cloud's min corner,
    # so relative numbers mean the same thing on cropped and uncropped runs.
    origin = points.min(axis=0)

    if cfg["crop_min"] is not None and cfg["crop_max"] is not None:
        points, mask = crop_box(points, cfg["crop_min"], cfg["crop_max"])
        colors = colors[mask]
        print(f"\ncrop from roofkit.json applied: {len(points):,} points remain")
        print_bbox(points, "cropped")
    else:
        print("\ncrop_min/crop_max not set in roofkit.json: showing the raw cloud")

    # Subsample ONLY what the viewer displays. Every pick still lands on a
    # real point of the cloud, so its printed XYZ is exact; a denser view
    # would only add points between the ones you can already click.
    if len(points) > MAX_VIEW_POINTS:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(points), MAX_VIEW_POINTS, replace=False)
        points, colors = points[idx], colors[idx]
        print(f"\nviewer shows a random {MAX_VIEW_POINTS:,}-point subsample "
              f"for responsiveness")

    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    cloud.colors = o3d.utility.Vector3dVector(colors)

    print("\nviewer: SHIFT+LEFT CLICK prints a point's XYZ here. Q closes.")
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window(window_name="pick points: shift+click, then Q")
    vis.add_geometry(cloud)
    vis.run()
    vis.destroy_window()

    picked = vis.get_picked_points()          # indices into the shown cloud
    if not picked:
        print("no points picked")
        return
    pts = points[picked]
    # Open3D's own click log prints 2-significant-figure scientific notation,
    # useless at UTM magnitudes. These lines are the real numbers.
    print("\npicked points (in click order), absolute UTM and relative to the "
          "raw cloud's min corner:")
    for i, p in enumerate(pts):
        rel = p - origin
        print(f"  pick {i + 1}: X={p[0]:.2f}  Y={p[1]:.2f}  Z={p[2]:.2f}"
              f"   |   dx={rel[0]:8.2f}  dy={rel[1]:8.2f}  dz={rel[2]:8.2f}")

    lo = [float(round(v, 2)) for v in pts.min(axis=0)]
    hi = [float(round(v, 2)) for v in pts.max(axis=0)]
    print("\npaste-ready snippet from the picks' extremes (check each axis; "
          "pad z upward so the ridge is not clipped):")
    print(json.dumps({"crop_min": lo, "crop_max": hi}, indent=2))


if __name__ == "__main__":
    main()
