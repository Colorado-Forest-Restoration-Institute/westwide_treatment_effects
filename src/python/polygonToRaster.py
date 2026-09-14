# === description ====
#
# Input: the feature class written by calculateTimeFields.py (nested IR
# perimeters plus a bounding-box feature, from nestPerimeters.py). Every feature
# carries a "countdown" field - whole seconds from that feature's capture time
# until fire extinction, 0 on the bounding box.
#
# Output: a single-band raster covering the full extent of the bounding box
# feature, where each cell takes the "countdown" value of the smallest
# (earliest) perimeter that contains it, and 0 outside every perimeter (unburned
# ground within the box, and the box itself). This is the "seconds to
# extinction" raster consumed by target_selector.py.

import os

import arcpy

arcpy.env.overwriteOutput = True

# === workspace (.gdb) ===
# calculateTimeFields.py writes here
GDB     = r"C:\Users\anson\Documents\westwide_treatment_effects\derived_data\daily_progression.gdb"
IN_FC   = "Daily_Progression_timed"       # output of calculateTimeFields.py
OUT_RAS = "Daily_Progression_countdown"   # this script's output

# output cell size, in the input feature class's projected units (meters -
# nestPerimeters.py projects into a per-fire Transverse Mercator).
CELL_SIZE = 10.0

src = os.path.join(GDB, IN_FC)
out = os.path.join(GDB, OUT_RAS)

# === set the processing environment explicitly ===
# arcpy.env settings persist across scripts/sessions in the current workspace.
# To avoid issues, set every relevant environment from the input itself instead
# of inheriting anything.
desc = arcpy.Describe(src)
arcpy.env.workspace = GDB
arcpy.env.extent = desc.extent                     # = bounding box extent
arcpy.env.outputCoordinateSystem = desc.spatialReference
arcpy.env.cellSize = CELL_SIZE
arcpy.env.snapRaster = None
arcpy.env.mask = None

# === rasterize ===
arcpy.conversion.PolygonToRaster(
    src,
    "countdown",
    out,
    cell_assignment="CELL_CENTER",
    priority_field="countdown",
    cellsize=CELL_SIZE,
)

result = arcpy.Raster(out)
print(
    f"Wrote {out}: {result.width}x{result.height} cells at {CELL_SIZE}m, "
    f"values {result.minimum}..{result.maximum}."
)
if result.minimum is None or result.maximum is None:
    raise RuntimeError(
        f"{out} came out empty (no valid cell values) - check that {IN_FC} "
        "has non-null 'countdown' values and overlaps the set extent."
    )
