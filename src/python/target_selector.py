# === description ====
# takes rasterized ir perimeters as input. Raster should have zero value in
# unburned regions and max value at fire origin/ignition point. Raster can be in
# any time unit but "seconds to extinction" is recommended. Interpolates values
# between IR perimeters using recursive binary dilation or euclidean distance
# transform. Outputs a "moment of burn" raster of the same resolution as the
# input.

import arcpy
import numpy as np
import os
from scipy.ndimage import distance_transform_edt
from scipy.ndimage import binary_dilation

# === Set workspace (.gdb) ===
arcpy.env.workspace = r"C:\Users\anson\Documents\ArcGIS\Projects\FireSpread\FireSpread.gdb"
arcpy.env.overwriteOutput = True

# === definitions ===
def get_normalized_position(insideness, outsideness):
    denominator = insideness + outsideness
    # Use np.where to apply condition element-wise avoids !div/0 problems: if
    # insideness and outsideness are nearly equal, the normalized position is
    # zero. otherwise, the normalized position is (insideness - outsideness) /
    # (insideness + outsideness)
    n_pos = np.where(
        np.isclose(insideness, outsideness),
        np.float64(0.0),
        (insideness - outsideness) / denominator
    )
    # identify places where the isclose() condition applies
    equal_distance = np.where(
        np.isclose(insideness, outsideness),
        1,
        0
    )

    return n_pos, equal_distance

# === Input and output raster names (within the .gdb) ===
input_raster_name = "irPerimsTimed_PolygonToRaster_s2a"
output_raster_name = "momentOfBurnEDT_s2a"

# === Load raster and metadata ===
raster = arcpy.Raster(input_raster_name)
desc = arcpy.Describe(raster)
spatial_ref = desc.spatialReference
print(("Spatial reference name: {0}:".format(desc.spatialReference.name)))

# === Convert to NumPy array ===
ir = arcpy.RasterToNumPyArray(raster, nodata_to_value=0).astype(np.int_)
# === Clean up ir by changing 0 to new value and NoData to 0 ===
# just check nodata value here
print("input nodata value:\n", ir[0:9, 0:9])
# not needed if input is already clean
# === Get unique values of array (== IR flight times)
flight_times = np.unique(ir)
print("n unique timestamps:\n", flight_times.shape) # 17 elements, index 0 to 16. Includes 0
print("timestamps:\n", flight_times)

# init array to hold results
output = ir
output_normalized_position = ir
for i in range(len(flight_times) - 1, -1, -1):
    print(flight_times[i])
    # max value is first parameter
    # create first origin raster
    origin = np.where(ir == flight_times[i], 1, 0)
    target = np.where(ir == flight_times[i-1], 1, 0)
    destination = np.where(ir <= flight_times[i-2], 1, 0)

    if flight_times[i-1] == 0:
        output = np.where(output <= i, 0, output)
        print("Finished processing. Writing output.")
        break

    # === calculate the distance ===
    edt = True
    if edt:
        gradient_outward = np.float64(distance_transform_edt(1 - origin))
        gradient_inward = np.float64(distance_transform_edt(1 - destination))

    else:
        seed = (origin > 0)  # binary seed (True where we start)

        # === Initialize output array with zeros ===
        gradient_outward = np.zeros_like(seed, dtype=np.uint32)
        current_mask = seed.copy()
        iteration = 1
        max_iterations = 1000  # adjust as needed

        # === Iterative dilation and labeling ===
        while iteration <= max_iterations:
            if iteration % 3 == 0:
                dilated = binary_dilation(current_mask, structure=np.ones((3, 3)), mask=target) # queen connectivity
            else:
                dilated = binary_dilation(current_mask, mask=target) # default structure: rook connectivity
            new_ring = np.logical_and(dilated, ~current_mask)
            nr_2 = np.logical_and(new_ring, target)

            if not np.any(nr_2):
                outward_iter = iteration
                print("Iteration", iteration)
                print("complete.")
                break  # stop if no new pixels are added

            gradient_outward[new_ring] = iteration
            current_mask = np.logical_or(current_mask, new_ring)
            iteration += 1

        gradient_outward = np.where(target == 1, gradient_outward, 0)

        # now inward
        seed2 = (destination > 0)

        gradient_inward = np.zeros_like(seed2, dtype=np.uint32)
        current_mask2 = seed2.copy()
        iteration2 = 1

        while iteration2 <= max_iterations:
            if iteration2 % 3 == 0:
                dilated2 = binary_dilation(current_mask2, structure=np.ones((3, 3)), mask=target)
            else:
                dilated2 = binary_dilation(current_mask2, mask=target)  # default structure
            new_ring2 = np.logical_and(dilated2, ~current_mask2)
            nr2_2 = np.logical_and(new_ring2, target)

            if not np.any(nr2_2):
                print("Iteration2", iteration2)
                print("complete.")
                break  # stop if no new pixels are added

            gradient_inward[new_ring2] = iteration2
            current_mask2 = np.logical_or(current_mask2, new_ring2)
            iteration2 += 1

        gradient_inward = np.where(target == 1, gradient_inward, 0)

    go = gradient_outward.astype(np.float64)
    gi = gradient_inward.astype(np.float64)
    normalized_position, equal_distance = get_normalized_position(go, gi)
    # grab edge case (smallest target region, containing no "inner" polygon for normalization of position)
    # TODO this does not seem to be fixing the problem, still seeing some 1512780.000000 values.
    # fixing in ArcGIS for now.
    normalized_position = np.where(normalized_position > 1000, 0, normalized_position)
    total_distance = go + gi
    t_diff = np.float64(flight_times[i] - flight_times[i-1])
    scaled = ((normalized_position * -1) + 1) / 2
    scaled2 = scaled * t_diff + flight_times[i-1]

    print(f"Updating for timestamp {flight_times[i-1]}. {i-2} timestamps remaining.")
    output = np.where(ir == flight_times[i-1], scaled2, output)
    output_total_distance = np.where(ir == flight_times[i-1], scaled2, output)
    output_normalized_position = np.where(ir == flight_times[i-1], normalized_position, output_normalized_position)

# # === Convert back to raster ===
lower_left = arcpy.Point(raster.extent.XMin, raster.extent.YMin)
cell_size = raster.meanCellWidth

# moment of burn output
testout = arcpy.NumPyArrayToRaster(output, lower_left, cell_size, cell_size)
arcpy.DefineProjection_management(testout, spatial_ref)

# normalized position output
n_position = arcpy.NumPyArrayToRaster(output_normalized_position, lower_left, cell_size, cell_size)
arcpy.DefineProjection_management(n_position, spatial_ref)

# eq_dist output
eq_dist = arcpy.NumPyArrayToRaster(equal_distance, lower_left, cell_size, cell_size)
arcpy.DefineProjection_management(eq_dist, spatial_ref)
# === Save to GDB ===
if arcpy.Exists(output_raster_name):
    arcpy.Delete_management(output_raster_name)

testout.save(output_raster_name)
n_position.save(f"{output_raster_name}_normalizedPosition")
eq_dist.save(f"{output_raster_name}_eqDist")

print(f"Saved output raster to: {os.path.join(arcpy.env.workspace, output_raster_name)}")
