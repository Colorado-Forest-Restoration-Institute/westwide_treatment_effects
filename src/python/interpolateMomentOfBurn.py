# === description ====
#
# Input: the raster written by polygonToRaster.py - "seconds to extinction"
# countdown values, zero in unburned ground and at the bounding box, rising
# toward the fire origin. Interpolates values between IR perimeters using a
# Euclidean distance transform (or, alternately, recursive binary dilation).
# The innermost perimeter has no earlier perimeter to interpolate its
# interior from, so the fire-origin point is assumed to be the deepest point
# inside it, and is given a countdown ORIGIN_LEAD_TIME earlier than the
# perimeter itself.
#
# Output: a "moment of burn" raster at the same resolution and extent as the
# input, plus a mask flagging the innermost perimeter's footprint (where
# values rest on that origin-point guess) so it can be dropped downstream.

import os

import arcpy
import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt

arcpy.env.overwriteOutput = True

# === workspace (.gdb) ===
# polygonToRaster.py writes here
GDB     = r"C:\Users\anson\Documents\westwide_treatment_effects\derived_data\daily_progression.gdb"
IN_RAS  = "Daily_Progression_countdown"    # output of polygonToRaster.py
OUT_RAS = "Daily_Progression_momentOfBurn"  # base name; METHOD is appended below

arcpy.env.workspace = GDB

# === interpolation method ===
# "edt": exact Euclidean distance transform (default). "dilation": approximate
# growth via alternating binary dilation, kept for comparison with "edt".
METHOD = "edt"
if METHOD not in ("edt", "dilation"):
    raise ValueError(f"METHOD must be 'edt' or 'dilation', got {METHOD!r}.")

# for METHOD == "dilation" only: how often a growth step uses 8-connectivity
# ("queen", which also reaches diagonal neighbors) instead of the default
# 4-connectivity ("rook"). Alternating rook/queen steps traces an octagon
# rather than a rook-only diamond or queen-only square; a fixed "every 3rd
# step" spacing has no relationship to a circle. Spacing queen steps
# DILATION_PERIOD/QUEEN_STEPS_PER_PERIOD =~ pi iterations apart on average
# (22/7, below) keeps the octagon's proportions closer to an actual circle.
DILATION_PERIOD = 22        # 22/7 is the classic rational approximation of pi
QUEEN_STEPS_PER_PERIOD = 7


def queen_step_schedule():
    """Yield True on a "queen" step, False otherwise, spacing the True's
    evenly (Bresenham-style) rather than bursting them within each period."""
    acc = 0
    while True:
        acc += QUEEN_STEPS_PER_PERIOD
        if acc >= DILATION_PERIOD:
            acc -= DILATION_PERIOD
            yield True
        else:
            yield False


# === fire-origin assumption ===
# seconds assumed between ignition and the first (innermost) perimeter.
ORIGIN_LEAD_TIME = 24 * 60 * 60


# === helper: normalized position between two distance grids ===
def get_normalized_position(insideness, outsideness):
    denominator = insideness + outsideness
    # Use np.where to apply condition element-wise avoids !div/0 problems: if
    # insideness and outsideness are nearly equal, the normalized position is
    # zero. otherwise, the normalized position is (insideness - outsideness) /
    # (insideness + outsideness)
    n_pos = np.where(
        np.isclose(insideness, outsideness),
        np.float64(0.0),
        (insideness - outsideness) / denominator,
    )
    # identify places where the isclose() condition applies
    equal_distance = np.where(np.isclose(insideness, outsideness), 1, 0)

    return n_pos, equal_distance


# === load and validate the input raster ===
raster = arcpy.Raster(IN_RAS)
desc = arcpy.Describe(raster)
spatial_ref = desc.spatialReference

# nestPerimeters.py builds a projected, per-fire Transverse Mercator CRS
# specifically so distances are trustworthy, and polygonToRaster.py carries
# that CRS through via arcpy.env.outputCoordinateSystem. Confirm both that it
# survived and that cells are square, since the EDT-based interpolation below
# treats one grid step as equal-distance in every direction - true only for
# square cells in a (locally) conformal, low-distortion projection.
if spatial_ref.type != "Projected":
    raise RuntimeError(
        f"{IN_RAS} has a {spatial_ref.type} CRS ({spatial_ref.name}); expected "
        "the projected, per-fire CRS nestPerimeters.py builds. Re-run "
        "polygonToRaster.py so outputCoordinateSystem is set from its input "
        "feature class."
    )
if not np.isclose(raster.meanCellWidth, raster.meanCellHeight):
    raise RuntimeError(
        f"{IN_RAS} has non-square cells ({raster.meanCellWidth} x "
        f"{raster.meanCellHeight}); the EDT-based interpolation below assumes "
        "isotropic cells."
    )
print(
    f"Spatial reference: {spatial_ref.name} (projected, square "
    f"{raster.meanCellWidth}m cells)."
)

# === enumerate flight-time steps ===
ir = arcpy.RasterToNumPyArray(raster, nodata_to_value=0).astype(np.int_)
flight_times = np.unique(ir)
print(f"n unique timestamps: {flight_times.shape[0]}")
print(f"timestamps: {flight_times}")

# === estimate a fire-origin point inside the innermost perimeter ===
# The innermost perimeter has no earlier perimeter to interpolate its interior
# from, so its interior would otherwise be left flat. Guess an ignition point
# instead: the pixel deepest inside the perimeter, i.e. the last one to survive
# if the perimeter were eroded inward repeatedly. Splicing that point into
# ir/flight_times as one more ring lets the loop below interpolate the interior
# exactly like every other ring - no special-casing needed.
#
# This is a guess, not a measurement: innermost_mask flags the footprint it
# applies to, in case it should be excluded from downstream analysis.
innermost_mask = ir == flight_times[-1]
depth = distance_transform_edt(innermost_mask)
origin_row, origin_col = np.unravel_index(np.argmax(depth), depth.shape)
origin_countdown = flight_times[-1] + ORIGIN_LEAD_TIME

print(
    f"Estimated fire origin at row {origin_row}, col {origin_col} "
    f"({depth[origin_row, origin_col]:.1f} cells inside the innermost "
    f"perimeter); assigned countdown {origin_countdown}."
)

ir[origin_row, origin_col] = origin_countdown
flight_times = np.unique(ir)

# === interpolate burn time between successive perimeters ===
output = ir
output_normalized_position = ir
for i in range(len(flight_times) - 1, -1, -1):
    print(flight_times[i])
    # max value is first parameter
    # create first origin raster
    origin = np.where(ir == flight_times[i], 1, 0)
    target = np.where(ir == flight_times[i - 1], 1, 0)
    destination = np.where(ir <= flight_times[i - 2], 1, 0)

    if flight_times[i - 1] == 0:
        output = np.where(output <= i, 0, output)
        print("Finished processing. Writing output.")
        break

    # === compute inward/outward distance grids ===
    if METHOD == "edt":
        gradient_outward = np.float64(distance_transform_edt(1 - origin))
        gradient_inward = np.float64(distance_transform_edt(1 - destination))

    else:
        seed = origin > 0  # binary seed (True where we start)

        # grow outward from the newer perimeter until it reaches `target`
        gradient_outward = np.zeros_like(seed, dtype=np.uint32)
        current_mask = seed.copy()
        iteration = 1
        max_iterations = 1000  # adjust as needed
        outward_steps = queen_step_schedule()

        while iteration <= max_iterations:
            if next(outward_steps):
                dilated = binary_dilation(
                    current_mask, structure=np.ones((3, 3)), mask=target
                )
            else:
                dilated = binary_dilation(current_mask, mask=target)
            new_ring = np.logical_and(dilated, ~current_mask)
            nr_2 = np.logical_and(new_ring, target)

            if not np.any(nr_2):
                outward_iter = iteration
                print("Iteration", iteration)
                print("complete.")
                break  # stop if no new pixels are added

            gradient_outward[new_ring] = iteration
            current_mask = np.logical_or(current_mask, new_ring)
            iteration += 1

        gradient_outward = np.where(target == 1, gradient_outward, 0)

        # now grow inward from the older perimeter, same rules
        seed2 = destination > 0

        gradient_inward = np.zeros_like(seed2, dtype=np.uint32)
        current_mask2 = seed2.copy()
        iteration2 = 1
        inward_steps = queen_step_schedule()

        while iteration2 <= max_iterations:
            if next(inward_steps):
                dilated2 = binary_dilation(
                    current_mask2, structure=np.ones((3, 3)), mask=target
                )
            else:
                dilated2 = binary_dilation(current_mask2, mask=target)
            new_ring2 = np.logical_and(dilated2, ~current_mask2)
            nr2_2 = np.logical_and(new_ring2, target)

            if not np.any(nr2_2):
                print("Iteration2", iteration2)
                print("complete.")
                break  # stop if no new pixels are added

            gradient_inward[new_ring2] = iteration2
            current_mask2 = np.logical_or(current_mask2, new_ring2)
            iteration2 += 1

        gradient_inward = np.where(target == 1, gradient_inward, 0)

    go = gradient_outward.astype(np.float64)
    gi = gradient_inward.astype(np.float64)
    normalized_position, equal_distance = get_normalized_position(go, gi)
    total_distance = go + gi
    t_diff = np.float64(flight_times[i] - flight_times[i - 1])
    scaled = ((normalized_position * -1) + 1) / 2
    scaled2 = scaled * t_diff + flight_times[i - 1]

    print(
        f"Updating for timestamp {flight_times[i - 1]}. "
        f"{i - 2} timestamps remaining."
    )
    output = np.where(ir == flight_times[i - 1], scaled2, output)
    output_total_distance = np.where(ir == flight_times[i - 1], scaled2, output)
    output_normalized_position = np.where(
        ir == flight_times[i - 1], normalized_position, output_normalized_position
    )

# === build output rasters ===
lower_left = arcpy.Point(raster.extent.XMin, raster.extent.YMin)
cell_size = raster.meanCellWidth

# innermost-perimeter mask (flags the origin-point guess's footprint)
innermost_area = arcpy.NumPyArrayToRaster(
    innermost_mask.astype(np.uint8), lower_left, cell_size, cell_size
)
arcpy.management.DefineProjection(innermost_area, spatial_ref)

# moment of burn
moment_of_burn = arcpy.NumPyArrayToRaster(output, lower_left, cell_size, cell_size)
arcpy.management.DefineProjection(moment_of_burn, spatial_ref)

# normalized position
n_position = arcpy.NumPyArrayToRaster(
    output_normalized_position, lower_left, cell_size, cell_size
)
arcpy.management.DefineProjection(n_position, spatial_ref)

# equal-distance mask
eq_dist = arcpy.NumPyArrayToRaster(equal_distance, lower_left, cell_size, cell_size)
arcpy.management.DefineProjection(eq_dist, spatial_ref)

# === save to GDB ===
# fold METHOD into the saved name so edt/dilation outputs never collide
out_base = f"{OUT_RAS}_{METHOD}"
if arcpy.Exists(out_base):
    arcpy.management.Delete(out_base)

moment_of_burn.save(out_base)
n_position.save(f"{out_base}_normalizedPosition")
eq_dist.save(f"{out_base}_eqDist")
innermost_area.save(f"{out_base}_innermostMask")

print(f"Saved output raster to: {os.path.join(arcpy.env.workspace, out_base)}")
