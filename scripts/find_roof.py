import open3d as o3d
from roofkit.io import load_xyz
from roofkit.segment import find_roof_planes, clean_outliers
from roofkit.measure import facet_area, facet_boundary

path = r"C:\odm\datasets\gable\clean_gable_lidar.laz"
points = load_xyz(path)
points = clean_outliers(points)        # drop the floaters before segmenting

facets = find_roof_planes(points)
print("Found", len(facets), "roof facets:")

SQM_TO_SQFT = 10.7639
total_area = 0.0
palette = [[1, 0, 0], [0, 0.5, 1], [0, 1, 0], [1, 1, 0], [1, 0, 1], [0, 1, 1]]
geometries = []

for i, f in enumerate(facets):
    # measure this facet's area and add it to the running total
    area_m2 = facet_area(f["points"], f["normal"])
    total_area += area_m2
    print(f"  facet {i+1}: pitch {f['pitch']:.1f} deg, area {area_m2 * SQM_TO_SQFT:.0f} sq ft")

    # colored points for this facet
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(f["points"])
    pc.paint_uniform_color(palette[i % len(palette)])
    geometries.append(pc)

    # black outline of the measured area
    outline = facet_boundary(f["points"], f["normal"])
    pairs = [[j, (j + 1) % len(outline)] for j in range(len(outline))]
    lines = o3d.geometry.LineSet()
    lines.points = o3d.utility.Vector3dVector(outline)
    lines.lines = o3d.utility.Vector2iVector(pairs)
    lines.paint_uniform_color([0, 0, 0])
    geometries.append(lines)

print(f"TOTAL roof area: {total_area * SQM_TO_SQFT:.0f} sq ft")

print("Opening viewer. Each color is one roof facet, black is its measured outline. Close window to exit.")
o3d.visualization.draw_geometries(geometries)