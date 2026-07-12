from roofkit.io import load_xyz

path = r"C:\odm\datasets\tyco_house\odm_georeferencing\odm_georeferenced_model.laz"
points = load_xyz(path)

print("Number of points:", len(points))

smallest = points.min(axis=0)
largest = points.max(axis=0)
print("Smallest corner (x, y, z):", smallest)
print("Largest corner (x, y, z):", largest)
print("Size in native units (x, y, z):", largest - smallest)   # NOT meters: no-GPS ODM = arbitrary scale