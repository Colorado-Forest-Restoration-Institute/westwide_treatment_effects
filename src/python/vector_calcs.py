# === description ====
# EXPERIMENTAL
# Takes a "moment of burn" raster (or "DEM", output from target_selector.py) and
# returns the gradient or "flow direction", representing the probable direction
# and magnitude (speed) of the firefront. not needed for the analysis. 
import arcpy
import numpy as np
from arcpy.sa import *
import math

# === Set workspace (.gdb) ===
arcpy.env.workspace = r"C:\Users\anson\Documents\ArcGIS\Projects\FireSpread\FireSpread.gdb"
arcpy.env.overwriteOutput = True

def compute_flow_vectors(dem_path):
    dem_raster = arcpy.Raster(dem_path)
    # Get spatial reference from input raster
    spatial_ref = dem_raster.spatialReference

    dem = arcpy.RasterToNumPyArray(dem_raster, nodata_to_value=np.nan).astype(np.float64)
    cellsize = np.float64(dem_raster.meanCellWidth)
    print('cellsize:', cellsize) # in meters, if projection is WGS_1984_Web_Mercator_Auxiliary_Sphere
    attribs = arcpy.Describe(dem_path)
    print('attribs:', attribs)
    print(("Spatial reference name: {0}:".format(attribs.spatialReference.name)))
    lower_left = arcpy.Point(dem_raster.extent.XMin, dem_raster.extent.YMin)

    rows, cols = dem.shape
    direction = np.full((rows, cols), np.nan, dtype=np.float64)  # init direction array
    magnitude = np.full((rows, cols), np.nan, dtype=np.float64)  # init magnitude array

    directions = [
        (-1, 0),  # N
        (-1, 1),  # NE
        (0, 1),  # E
        (1, 1),  # SE
        (1, 0),  # S
        (1, -1),  # SW
        (0, -1),  # W
        (-1, -1)  # NW
    ]

    # Print DEM stats for debugging
    print(f"DEM stats - Min: {np.nanmin(dem)}, Max: {np.nanmax(dem)}, Mean: {np.nanmean(dem)}")
    print(f"Non-NaN values in DEM: {np.sum(~np.isnan(dem))} out of {dem.size}")

    valid_cell_count = 0
    invalid_mag_count = 0
    total_cells = (rows - 2) * (cols - 2)  # Excluding edges
    # todo everything in 64 bit float
    # precompute where possible
    sqrt2 = np.float64(math.sqrt(2))
    norm_factor = np.float64(np.sqrt(2) - 1)

    OCTANT_MAP = {
        'NNE': ((-1, 0), (-1, -1)),  # -1 = up one row, -1 = left one col. edge (y, x) first
        'ENE': ((0, -1), (-1, -1)),
        'ESE': ((0, -1), (1, -1)),
        'SSE': ((1, 0), (1, -1)),
        'SSW': ((1, 0), (1, 1)),
        'WSW': ((0, 1), (1, 1)),
        'WNW': ((0, 1), (-1, 1)),
        'NNW': ((-1, 0), (-1, 1)),
    }

    for y in range(1, rows - 1):
        # y is a row number
        for x in range(1, cols - 1):
            # x is a col number
            center = np.float64(dem[y, x])
            # center is a time measurement for a specific cell and np.array
            if np.isnan(center):
                continue

            sum_u, sum_v = np.float64(0.0), np.float64(0.0)
            has_valid_neighbors = False

            for dy, dx in directions:
                # dy is a scalar "adjustment" to center cell location
                # dx is a scalar "adjustment" to center cell location
                # you have one dy and one dx FOR EACH element of directions
                ny, nx = y + dy, x + dx
                # same as ny = y + dy and nx = x + dx
                neighbor = np.float64(dem[ny, nx])
                if np.isnan(neighbor):
                    continue
                has_valid_neighbors = True
                # Calculate slope and direction
                dz = (neighbor - center)
                distance = 1 if dx == 0 or dy == 0 else sqrt2 # distance in cellwidths
                slope = dz / distance

                # For flow direction, we use downslope direction (opposite of upslope)
                # If slope is negative (uphill), this will point uphill
                angle = np.float64(math.atan2(dx, -dy))  # compass-based: 0° = north, +clockwise
                # weight = abs(slope) # not needed, use slope directly?
                # For downslope flow, use positive weight
                # For upslope flow, use negative weight
                # direction_factor = 1 if slope > 0 else -1
                sum_u += slope * np.float64(math.sin(angle))  # "upness" #direction_factor * weight
                sum_v += slope * np.float64(math.cos(angle))  # "overness" #direction_factor * weight

            if has_valid_neighbors:
                dir = math.degrees(np.float64(np.arctan2(sum_u, sum_v)))
                mag = 1 / np.sqrt((sum_u / 4) ** 2 + (sum_v / 4) ** 2)

                direction[y, x] = dir
                magnitude[y, x] = mag * cellsize # scale magnitude to make unit "[projection unit]/sec"
    gradient = np.array([magnitude, direction])


    print(
        f"Valid flow directions calculated: {valid_cell_count} out of {total_cells} cells ({valid_cell_count / total_cells * 100:.2f}%)")
    print(
        f"Invalid flow directions calculated: {invalid_mag_count} out of {total_cells} cells ({invalid_mag_count / total_cells * 100:.2f}%)")
    return gradient, cellsize, lower_left, spatial_ref


def save_rasters(gradient, cellsize, lower_left, output_base, spatial_ref):
    # Compute direction angle in radians (optional)

    gradient_ras = arcpy.NumPyArrayToRaster(gradient, lower_left, cellsize, cellsize, value_to_nodata=np.nan)

    # Define projection for each output raster
    arcpy.DefineProjection_management(gradient_ras, spatial_ref)

    gradient_ras.save(f"{output_base}_gradient")

def main(dem, output_base="flowdir"):

    gradient, cellsize, lower_left, spatial_ref = compute_flow_vectors(dem)

    # grad = compute_flow_direction_gradient(u, v, cellsize)
    # Print statistics for debugging
    # print(f"Gradient array stats - Min: {np.nanmin(dirmag)}, Max: {np.nanmax(dirmag)}, Mean: {np.nanmean(dirmag)}")
    # print(f"Non-NaN values - U: {np.sum(~np.isnan(dirmag))}, V: {np.sum(~np.isnan(dirmag))}, Grad: {np.sum(~np.isnan(dirmag))}")
    print("saving rasters")
    save_rasters(gradient,
                 cellsize, lower_left, output_base, spatial_ref)


main('momentOfBurnEDT', 'test_13')
