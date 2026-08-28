# a brief demo of fireline speed using pocket fire data
# load packages ----------------------------------------------------------------
library(tidyverse)
library(curl)
library(rlandfire)
library(sf)
library(terra)

# data -------------------------------------------------------------------------
# pocket fire
pf_perims <- st_read(
  "raw_data/Daily_Progression_08-24-2026_15-14-04/Daily_Progression_08-24-2026_15-14-04.gdb"
)
