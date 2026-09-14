# === description ====
# prepares raw S2A data for downstream analysis. 

import os
import arcpy
from collections import defaultdict

# === Workspace ===
arcpy.env.workspace = r"C:\Users\anson\Documents\ArcGIS\Projects\az_map\imagery.gdb"
arcpy.env.overwriteOutput = True

# === Raw data location ===
raw_data_dir = r"C:\Users\anson\Documents\ArcGIS\Projects\az_map\raw_imagery\sentinel"

# === Band definitions ===
r10m_bands = ["B02", "B03", "B04", "B08"]  # Blue, Green, Red, NIR
r20m_bands = ["B8A", "B12"]                # Narrow NIR, SWIR2

roi_layer = "ROI_Rectangle"

# === Find inner SAFE directories grouped by date ===
# Use defaultdict to group tile directories per acquisition date
tiles_by_date = defaultdict(list)

for outer in os.listdir(raw_data_dir):
    if outer.endswith(".SAFE"):
        outer_path = os.path.join(raw_data_dir, outer)
        for inner in os.listdir(outer_path):
            if inner.endswith(".SAFE"):
                # Extract date from inner SAFE name: S2A_MSIL2A_YYYYMMDDTHHMMSS...
                date_str = inner.split("_")[2][:8]  # YYYYMMDD
                inner_path = os.path.join(outer_path, inner)
                if os.path.exists(os.path.join(inner_path, "GRANULE")):
                    tiles_by_date[date_str].append(inner_path)

if not tiles_by_date:
    raise RuntimeError("No valid Sentinel-2 SAFE directories found.")

# === Functions ===
def find_jp2s(tile_dirs, res, bands):
    """Find JP2 files for given resolution and band list."""
    matches = []
    for tile in tile_dirs:
        for root, dirs, files in os.walk(tile):
            if res in root:
                for band in bands:
                    suffix = f"{band}_{res}.jp2"
                    for f in files:
                        if f.endswith(suffix):
                            matches.append(os.path.join(root, f))
    return matches

def clip_and_name(jp2_list, res, date_str):
    """Clip rasters to ROI, preserving band code and date."""
    clipped = []
    for jp2_path in jp2_list:
        parts = os.path.basename(jp2_path).split("_")
        band_code = [p for p in parts if p.startswith("B")][0]
        out_path = os.path.join(arcpy.env.workspace, f"{band_code}_{res}_{date_str}_clip")
        arcpy.management.Clip(jp2_path, "#", out_path, roi_layer,
                              "#", "ClippingGeometry", "MAINTAIN_EXTENT")
        clipped.append(out_path)
    return clipped

def find_band(clipped_list, code):
    """Find a clipped raster matching a band code."""
    for r in clipped_list:
        if f"_{code}_" in os.path.basename(r) or os.path.basename(r).startswith(f"{code}_"):
            return r
    raise RuntimeError(f"Band {code} not found in clipped rasters.")

# === Process each date ===
for date_str, tile_dirs in tiles_by_date.items():
    print(f"Processing date {date_str}...")

    # Find files for this date
    r10m_files = find_jp2s(tile_dirs, "10m", r10m_bands)
    r20m_files = find_jp2s(tile_dirs, "20m", r20m_bands)

    if not r10m_files or not r20m_files:
        raise RuntimeError(f"Missing JP2 files for date {date_str}")

    # Clip
    clipped_r10m = clip_and_name(r10m_files, "10m", date_str)
    clipped_r20m = clip_and_name(r20m_files, "20m", date_str)

    # NDVI
    b08_clip = find_band(clipped_r10m, "B08")
    b04_clip = find_band(clipped_r10m, "B04")
    ndvi_out = os.path.join(arcpy.env.workspace, f"NDVI_10m_{date_str}")
    ndvi_raster = (arcpy.Raster(b08_clip) - arcpy.Raster(b04_clip)) / \
                  (arcpy.Raster(b08_clip) + arcpy.Raster(b04_clip))
    ndvi_raster.save(ndvi_out)

    # NBR
    b8a_clip = find_band(clipped_r20m, "B8A")
    b12_clip = find_band(clipped_r20m, "B12")
    nbr_out = os.path.join(arcpy.env.workspace, f"NBR_20m_{date_str}")
    nbr_raster = (arcpy.Raster(b8a_clip) - arcpy.Raster(b12_clip)) / \
                 (arcpy.Raster(b8a_clip) + arcpy.Raster(b12_clip))
    nbr_raster.save(nbr_out)

    # Composite RGB + NDVI
    b04_clip = find_band(clipped_r10m, "B04")
    b03_clip = find_band(clipped_r10m, "B03")
    b02_clip = find_band(clipped_r10m, "B02")
    rgb_ndvi_out = os.path.join(arcpy.env.workspace, f"RGB_NDVI_10m_{date_str}")
    arcpy.management.CompositeBands([b04_clip, b03_clip, b02_clip, ndvi_out], rgb_ndvi_out)

    print(f"Date {date_str} complete: {rgb_ndvi_out}, {nbr_out}")

print("All processing complete.")
