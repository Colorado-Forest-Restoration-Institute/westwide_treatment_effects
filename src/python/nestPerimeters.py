# === description ====
#
# Input: raw file geodatabase including ir heat perimeter polygon feature layer.
# Should be for a single fire. 
# Output: a new feature layer, reprojected into a Transverse Mercator centered
# on the fire, with fully nested perimeters (every perimeter completely encloses
# all earlier-dated perimeters), plus a bounding box feature with a start_date
# attribute value +1d relative to the date of the last (largest) perimeter
# feature.

import os
from datetime import timedelta

import arcpy

arcpy.env.overwriteOutput = True
# === Set workspaces (.gdb) ===
# raw data 
SRC_GDB = r"C:\Users\anson\Documents\westwide_treatment_effects\raw_data\Daily_Progression_08-24-2026_15-14-04\Daily_Progression_08-24-2026_15-14-04.gdb"
# output data
OUT_GDB = r"C:\Users\anson\Documents\westwide_treatment_effects\derived_data\daily_progression.gdb"

# === constants ===
SRC_FC  = "Daily_Progression" # Name of the input feature class
OUT_FC  = "Daily_Progression_boxed" # Name of the output feature class
# size of the padding around the largest perimeter for defining the bounding box
PAD_M   = 1000.0 # Padding in meters
# tidy variables for the input and output feature classes
src = os.path.join(SRC_GDB, SRC_FC)
out = os.path.join(OUT_GDB, OUT_FC)

# create output .gdb if it doesn't already exist
if not arcpy.Exists(OUT_GDB):
    arcpy.management.CreateFileGDB(os.path.dirname(OUT_GDB), os.path.basename(OUT_GDB))

# === pick a local projection for this fire ===
# Downstream we need true distances/areas (fireline speed) and preserved
# bearings (fireline direction). No single western-US CRS gives both, so each
# fire gets its own Transverse Mercator with the central meridian and latitude
# of origin set to the centroid of its perimeters. TM is conformal (bearings
# hold), and with scale factor 1 at the fire center the scale error across a
# single fire (tens of km) stays under ~1e-5, so area error is well under 0.01%.
# The datum matches the source (WGS84), so the reprojection needs no datum
# shift.

# get the centroid of the source feature class in WGS84
src_desc = arcpy.Describe(src)
e = src_desc.extent
cx, cy = (e.XMin + e.XMax) / 2, (e.YMin + e.YMax) / 2
centroid_ll = (
    arcpy.PointGeometry(arcpy.Point(cx, cy), src_desc.spatialReference)
    .projectAs(arcpy.SpatialReference(4326))
    .firstPoint
)
lon0, lat0 = round(centroid_ll.X, 6), round(centroid_ll.Y, 6)

# create new projected CRS: Transverse Mercator centered on the fire centroid
sr = arcpy.SpatialReference()
sr.loadFromString(
    'PROJCS["Fire_Local_TM",'
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],'
    'PARAMETER["False_Easting",500000.0],'
    'PARAMETER["False_Northing",0.0],'
    f'PARAMETER["Central_Meridian",{lon0}],'
    'PARAMETER["Scale_Factor",1.0],'
    f'PARAMETER["Latitude_Of_Origin",{lat0}],'
    'UNIT["Meter",1.0]]'
)
print(f"Local projection: Transverse Mercator centered on ({lon0}, {lat0}), WGS84.")

# reproject the source into that CRS; never touch raw_data
arcpy.management.Project(src, out, sr)
# union chokes on self-intersecting rings, which can occur in fire perimeters. 
# RepairGeometry() fixes those, and is idempotent.
arcpy.management.RepairGeometry(out)  

if sr.type != "Projected":
    raise RuntimeError(f"Expected a projected CRS, got {sr.name} ({sr.type}).")
pad = PAD_M / sr.metersPerUnit


# === force perimeters to nest ===

# Physical burned area only grows, so the correct fix is to grow later
# perimeters to swallow every earlier one, never to shrink an earlier one.
# Replace each perimeter with the running union of it and all perimeters before
# it. This needs a total order over features, not one feature per day.
# start_date has only daily resolution, so ties are possible (two IR flights on
# one calendar day); we break ties by area ascending, since the smaller
# perimeter is almost certainly the earlier observation. union() is commutative,
# so within a tied group only the frame assigned to the first member depends on
# that choice.
rows = []          # the usable perimeters: (start_date, area, oid, shape)
attrs = {}         # oid -> (poly_incid, poly_irwin)
null_geom = []     # OIDs skipped for having no geometry
null_date = []     # OIDs skipped for having no start_date

# check that inputs have usable shapes and start_date attributes, and collect 
# them into a sortable list
with arcpy.da.SearchCursor(
    out, ["OID@", "SHAPE@", "start_date", "poly_incid", "poly_irwin"]
) as cur:
    for oid, shp, sdate, incid, irwin in cur:
        # check if shape is present
        if shp is None:
            null_geom.append(oid)
            continue
        # check in start_date is present
        if sdate is None:
            null_date.append(oid)
            continue
        # if shape and start date are present, add to the list of usable features
        rows.append((sdate, shp.area, oid, shp))
        attrs[oid] = (incid, irwin)

# print rows that fail geometry and start date checks
for oid in null_geom:
    print(f"Skipping OID {oid}: null geometry.")
for oid in null_date:
    print(f"Skipping OID {oid}: null start_date (cannot place it in the progression).")

# catch if no features are usable after the above checks
if not rows:
    raise RuntimeError(f"{SRC_FC} has no usable features.")

# sort rows by (start_date, area) ascending, so that the first row is the 
# earliest and smallest perimeter, and the last row is the latest and largest 
# perimeter. This ensures that when we perform the running union, each perimeter 
# will completely enclose all earlier perimeters.
rows.sort(key=lambda r: (r[0], r[1]))

# running union, writing the corrected geometry back keyed by OID
corrected = {}
running = None
for sdate, _area, oid, shp in rows:
    running = shp if running is None else running.union(shp)
    corrected[oid] = running

# assign the corrected geometry back to the feature class, and track the 
# largest growth
max_growth = 0.0
with arcpy.da.UpdateCursor(out, ["OID@", "SHAPE@", "start_date"]) as cur:
    for oid, shp, sdate in cur:
        # don't do anything to features that were skipped for having null 
        # geometry or null start_date
        if oid not in corrected:
            continue
        # compute the area growth of the corrected geometry relative to the 
        # original geometry. If shp was None, then set old_area==0.0 
        # (this should never happen, since we skipped null geometries above, 
        # but just in case).
        old_area = shp.area if shp is not None else 0.0
        new_geom = corrected[oid]
        cur.updateRow([oid, new_geom, sdate])
        if old_area > 0:
            growth = (new_geom.area - old_area) / old_area * 100
            max_growth = max(max_growth, growth)

print(
    f"Nested {len(rows)} perimeters "
    f"({rows[0][0]:%Y-%m-%d} .. {rows[-1][0]:%Y-%m-%d}); "
    f"largest single correction added {max_growth:.2f}% area."
)

# the last row in sorted order is now, by construction, the largest perimeter
# and contains every other; its extent is the extent of the whole progression.
# use this to define a bounding box feature with start_date == last perimeter +
# 1 day, and with the same poly_incid and poly_irwin attributes as the last
# perimeter.
last_date, _, last_oid, _ = rows[-1]
full_extent = corrected[last_oid].extent
anchor_date = last_date
incid, irwin = attrs[last_oid]

# --- padded rectangle, no intermediate feature classes ---
xmin, ymin = full_extent.XMin, full_extent.YMin
xmax, ymax = full_extent.XMax, full_extent.YMax
corners = [
    (xmin - pad, ymin - pad),
    (xmin - pad, ymax + pad),
    (xmax + pad, ymax + pad),
    (xmax + pad, ymin - pad),
    (xmin - pad, ymin - pad),
]
box = arcpy.Polygon(arcpy.Array([arcpy.Point(x, y) for x, y in corners]), sr)

# --- insert with attributes set at insert time ---
with arcpy.da.InsertCursor(out, ["SHAPE@", "start_date", "poly_incid", "poly_irwin"]) as ins:
    new_oid = ins.insertRow([box, anchor_date + timedelta(days=1), incid, irwin])

print(f"Inserted bounding box as OID {new_oid} in {out}")
