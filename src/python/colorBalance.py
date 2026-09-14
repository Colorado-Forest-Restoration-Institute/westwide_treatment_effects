# === description ====
# EXPERIMENTAL
# Color balances raster mosaics.
import arcpy

# === Set workspace (.gdb) ===
arcpy.env.workspace = r"C:\Users\anson\Documents\ArcGIS\Projects\FireSpread\FireSpread.gdb"
arcpy.env.overwriteOutput = True

# === Color balance superDove mosaic ====
# must add rasters to mosaic with "Calculate Statistics" and "Build Raster Pyramids" selected, or this will fail!
arcpy.management.ColorBalanceMosaicDataset("superDoveMay2020", "DODGING", "THIRD_ORDER",
                                           stretch_type = "MINIMUM_MAXIMUM")
