# === description ====
# calculates dNBR, RdNBR from S2A images following Fassnacht et al. 2021
# https://doi.org/10.1016/j.jag.2020.102262

import arcpy
from arcpy.sa import *

# === Set workspace (.gdb) ===
arcpy.env.workspace = r"C:\Users\anson\Documents\ArcGIS\Projects\az_map\imagery.gdb"
arcpy.env.overwriteOutput = True

# === calc immediately postfire indices ===
# dNBR
# Set local variables
in_raster1 = "NBR_20m_20200522" # nbr, May 22, 2020
in_raster2 = "NBR_20m_20200706" # nbr, June 6, 2020

# apply raster calcs
immediate_dnbr = RasterCalculator([in_raster1, in_raster2], ["x", "y"], "x - y")
# WARNING below order of operations does not seem correct!!
immediate_rdnbr = RasterCalculator([immediate_dnbr, in_raster2], ["x", "y"],
                                   "x / (abs(y))^0.5")

# === calc 1-yr postfire indices ===
in_raster2 = "NBR_20m_20210512" # nbr, May 12, 2021

# apply raster calcs
dnbr = RasterCalculator([in_raster1, in_raster2], ["x", "y"], "x - y")

rdnbr = RasterCalculator([dnbr, in_raster2], ["x", "y"],
                                   "x / (abs(y))^0.5")

# === write out ===
arcpy.management.CompositeBands([immediate_dnbr, immediate_rdnbr, dnbr, rdnbr], "s2a_burn_severity")
# be sure to rename bands as necessary in ArcGIS Pro
