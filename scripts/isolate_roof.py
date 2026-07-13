# Stage-by-stage roof isolation for ANY dataset, with a viewer after each
# stage. Run:
#   python scripts/isolate_roof.py C:\odm\datasets\big_house --stage 0
# Stages: 0 raw, 1 crop, 2 height cutoff, 3 color filter, 4 planarity.
import argparse
import numpy as np
import open3d as o3d
from dataset_config import load_config
from roofkit.io import load_xyz_rgb
from roofkit.crop import crop_box
from roofkit.isolate import height_cutoff, color_filter, planarity_filter
from roofkit.stats import median_nn_spacing
from roofkit.segment import clean_outliers


def show(points, colors=None, title=""):
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    if colors is not None:
        cloud.colors = o3d.utility.Vector3dVector(colors)
    print(f"[{title}] {len(points):,} points")
    o3d.visualization.draw_geometries([cloud], window_name=title)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="dataset directory (holds roofkit.json)")
    ap.add_argument("--stage", type=int, default=0,
                    help="0 raw, 1 crop, 2 height, 3 color, 4 planarity")
    ap.add_argument("--save", action="store_true",
                    help="after stage 4, write roof points to <dataset>/roof.npy")
    args = ap.parse_args()
    cfg = load_config(args.dataset)

    points, colors = load_xyz_rgb(cfg["cloud_path"])
    if args.stage == 0:
        show(points, colors, "0 raw")
        return

    if cfg["crop_min"] is None or cfg["crop_max"] is None:
        raise SystemExit("Set crop_min/crop_max in roofkit.json from the "
                         "stage-0 view first.")
    points, mask = crop_box(points, cfg["crop_min"], cfg["crop_max"])
    colors = colors[mask]
    if args.stage == 1:
        show(points, colors, "1 crop")
        return

    if cfg["z_min"] is None:
        raise SystemExit("Set z_min in roofkit.json from the stage-1 view first.")
    points, mask = height_cutoff(points, cfg["z_min"])
    colors = colors[mask]
    if args.stage == 2:
        show(points, colors, "2 height cutoff")
        return

    points, mask = color_filter(points, colors, exg_max=cfg["exg_max"])
    colors = colors[mask]
    if args.stage == 3:
        show(points, colors, "3 color filter")
        return

    s = median_nn_spacing(points)
    print(f"median nn spacing: {s:.4f} cloud units")
    points, mask = planarity_filter(points, radius=cfg["radius_mult"] * s,
                                    score_max=cfg["score_max"])
    points = clean_outliers(points)
    show(points, None, "4 planarity filter + outlier cleanup")
    if args.save:
        np.save(cfg["roof_path"], points)
        print(f"saved {len(points):,} roof points to {cfg['roof_path']}")


if __name__ == "__main__":
    main()
