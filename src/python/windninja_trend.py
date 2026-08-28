# === description ==== 
# builds interpolations of windninja data. not needed for the analysis.

import os, uuid
import arcpy
from arcpy.sa import *
import time

# === Workspace for final outputs ===
arcpy.env.workspace = r"C:\Users\anson\Documents\ArcGIS\Projects\FireSpread\FireSpread.gdb"
arcpy.env.overwriteOutput = True

# === Fresh scratch GDB for temps ===
scratch_root = r"C:\Temp"
os.makedirs(scratch_root, exist_ok=True)
scratch_gdb = os.path.join(scratch_root, f"scratch_{uuid.uuid4().hex[:8]}.gdb")
arcpy.management.CreateFileGDB(scratch_root, os.path.basename(scratch_gdb))
arcpy.env.scratchWorkspace = scratch_gdb

# === Template raster settings ===
template = arcpy.Raster("momentOfBurnEDT_s2a")
cell_size = template.meanCellWidth
tmpl_sr = arcpy.Describe(template).spatialReference
arcpy.env.snapRaster = template
arcpy.env.cellSize = cell_size
arcpy.env.extent = template.extent

# === Input shapefiles ===
raw_data_dir = r"C:\Users\anson\Documents\ArcGIS\Projects\az_map\WindNinja\full_run"

def parse_datetime_from_name(fname):
    parts = fname.split("_")
    d, t = None, None
    for p in parts:
        if len(p) == 10 and p[2] == "-" and p[5] == "-":
            d = p
        elif len(p) == 4 and p.isdigit():
            t = p
    return d, t

arcpy.CheckOutExtension("Spatial")

for file in os.listdir(raw_data_dir):
    if not file.lower().endswith(".shp"):
        continue

    shp = os.path.join(raw_data_dir, file)
    date_part, time_part = parse_datetime_from_name(file)
    if not (date_part and time_part):
        print(f"Skipping {file}: no date/time found")
        continue

    # Remove "-" from date for GDB-safe naming
    date_part_clean = date_part.replace("-", "")
    out_base = f"wind_{date_part_clean}_{time_part}"
    print(f"Processing {file} → {out_base}")

    # === Ensure same projection as template ===
    in_sr = arcpy.Describe(shp).spatialReference
    if not in_sr or in_sr.factoryCode != tmpl_sr.factoryCode:
        proj_shp = os.path.join(scratch_gdb, f"pts_{uuid.uuid4().hex[:6]}")
        arcpy.management.Project(shp, proj_shp, tmpl_sr)
        shp_for_idw = proj_shp
    else:
        shp_for_idw = shp

    # === Unique scratch names for IDW outputs ===
    spd_temp = os.path.join(scratch_gdb, f"spd_{uuid.uuid4().hex[:6]}")
    dir_temp = os.path.join(scratch_gdb, f"dir_{uuid.uuid4().hex[:6]}")

    # === Run IDW interpolations ===
    Idw(shp_for_idw, "speed", cell_size, 2).save(spd_temp)
    Idw(shp_for_idw, "dir", cell_size, 2).save(dir_temp)

    # === Composite into final two-band raster ===
    final_out = os.path.join(arcpy.env.workspace, out_base)
    arcpy.management.CompositeBands([spd_temp, dir_temp], final_out)

    # Clean up intermediates
    arcpy.management.Delete(spd_temp)
    arcpy.management.Delete(dir_temp)
    if shp_for_idw != shp:
        arcpy.management.Delete(shp_for_idw)
    time.sleep(0.2)

print("Done.")
