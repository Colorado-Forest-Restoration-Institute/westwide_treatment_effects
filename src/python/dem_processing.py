# === description ===
# Input: 1m DEM tiles from 3DEP. Output: mosaicked DEM. 

import arcpy
from arcpy import env
from arcpy.sa import *

# === Workspace ===
arcpy.env.workspace = r"C:\Users\anson\Documents\ArcGIS\Projects\az_map\raw_imagery\dem_1m_tiles"
arcpy.env.overwriteOutput = True

# === Create Mosaic TIF
arcpy.management.MosaicToNewRaster(
    input_rasters="USGS_1M_12_x37y406_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x37y407_AZ_CentralCoconino_B22.tif;USGS_1M_12_x37y407_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x37y408_AZ_CentralCoconino_B22.tif;USGS_1M_12_x37y409_AZ_CentralCoconino_B22.tif;USGS_1M_12_x38y406_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x38y407_AZ_CentralCoconino_B22.tif;USGS_1M_12_x38y407_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x38y408_AZ_CentralCoconino_B22.tif;USGS_1M_12_x38y408_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x38y409_AZ_CentralCoconino_B22.tif;USGS_1M_12_x38y409_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x39y406_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x39y407_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x39y408_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x39y409_AZ_CentralCoconino_B22.tif;USGS_1M_12_x39y409_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x40y406_AZ_CentralCoconino_B22.tif;USGS_1M_12_x40y406_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x40y407_AZ_CentralCoconino_B22.tif;USGS_1M_12_x40y407_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x40y408_AZ_CentralCoconino_B22.tif;USGS_1M_12_x40y408_AZ_NorthKaibabNF_2019_B19.tif;USGS_1M_12_x40y409_AZ_CentralCoconino_B22.tif;USGS_1M_12_x40y409_AZ_NorthKaibabNF_2019_B19.tif",
    output_location=r"C:\Users\anson\Documents\ArcGIS\Projects\az_map\raw_imagery\dem_1m_tiles",
    number_of_bands=1,
    raster_dataset_name_with_extension="dem_1m_mosaic.tif",
    pixel_type="32_BIT_SIGNED",
    mosaic_method="MAXIMUM")


