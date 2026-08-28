# === description ====
# Input: ir heat perimeter polygon feature layer. Should include a
# flightDateTime attribute, and should have a "bounding box" feature with a
# flightDateTime attribute value +1d relative to the date of the last (largest)
# perimeter feature. All polygon features should be "corrected" to properly nest
# (earlier perimeters completely enclosed by later ones). Output: the feature
# layer with an added "timeString" attribute, representing seconds until fire
# extinction (==flightDateTime of bounding box feature). Calcs use long int
# format to preserve precision.
import arcpy

# === Set workspace (.gdb) ===
arcpy.env.workspace = r"C:\Users\anson\Documents\ArcGIS\Projects\FireSpread\FireSpread.gdb"
arcpy.env.overwriteOutput = True

# === add fields ===
# input should have bounding box with timestamp == last perimeter + 1 day
arcpy.management.CopyFeatures("IR_HeatPerimeters_Corrected", "irPerimsTimed")
# calculate time as seconds from unix epoch, store as long int
arcpy.management.ConvertTimeField("irPerimsTimed", "flightDateTime",
                                  output_time_field = "timeString",
                                  output_time_format = "unix_s",
                                  output_time_type="LONG")

## get max timestring value (== end of fire)
allTimeValues = [row for row in arcpy.da.SearchCursor("irPerimsTimed", ["timeString"])]
a, = max(allTimeValues)
## calculate new field
code_block = """
def getCountdown(tS):
    return -(tS - a)
"""
arcpy.management.CalculateField("irPerimsTimed", "countdown",
                                expression = "getCountdown(!timeString!)",
                                code_block = code_block,
                                field_type = "LONG")
