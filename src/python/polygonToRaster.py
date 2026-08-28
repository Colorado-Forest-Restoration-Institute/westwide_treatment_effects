# === description ====

# TODO this doesn't seem to work, doing this directly in ArcGIS Pro for now.
# Inputs: 1) a polygon feature layer for ir perimeters, output from
# calculateTimeFields.py and 2) a template raster. Rasterizes the input polygon
# features. Output: rasterized ir perimeter layer suitable for use in
# target_selector.py.
import arcpy

# === Set workspace (.gdb) ===
arcpy.env.workspace = r"C:\Users\anson\Documents\ArcGIS\Projects\FireSpread\FireSpread.gdb"
arcpy.env.overwriteOutput = True

# === Read existing raster to determine cellsize ====
raster = arcpy.Raster("doveBaseMapMay2020Clip")
cell_size = raster.meanCellWidth

# === Rasterize timestamped feature class ===
arcpy.conversion.PolygonToRaster("irPerimsTimed", "countdown", "irCountDownRaster",
                                 cell_assignment = "CELL_CENTER",
                                 priority_field = "countdown",
                                 cellsize = cell_size)
# weirdly, this only worked with the desktop tool?
# this script is returning empty raster output with min/max values at long int min/max (-/+2147483647)
