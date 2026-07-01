#### load packages
library(rlandfire)
library(sf)
library(terra)

#### defining region of interest
region <- c("-124.8", "31.3", "-102.0", "49.0")

#### Landfire biophysical setting data
lf_request<-landfireAPIv2(products="LF2020_BPS",aoi=region,email="ntomczyk@nmhu.edu",path="./data/raw/")
