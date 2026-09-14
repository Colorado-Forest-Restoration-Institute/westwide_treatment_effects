# === description ==== 
#
# Input: the feature class written by nestPerimeters.py (fully nested IR heat
# perimeters plus a single bounding-box feature dated one day past the last
# perimeter). Perimeters carry only a daily-resolution start_date; we assume
# each was captured at 00:00 on that day.
#
# Output: a copy of that feature class with two added fields: capture_dt - the
#   assumed capture timestamp (start_date at 00:00, possibly bumped +1 day, see
#                below) countdown  - whole seconds from capture_dt until fire
#   extinction, where extinction is the bounding box's timestamp (last perimeter
#                +1d). This is the "time remaining" field consumed by
#                polygonToRaster.py / target_selector.py.
#
# Same-day perimeters: start_date has only daily resolution, so a calendar day
# can hold two or more IR flights. When a day has exactly two perimeters and the
# following calendar day has none, we assume the first was flown near 00:00 and
# the second near 23:59, and bump the second to +1 day so the progression keeps
# a sane daily cadence.
#
# In any case where we can't do that split - the following day is already
# occupied (including by the bounding box), or three-plus perimeters share one
# start_date, so the early/late-flight assumption doesn't apply - we leave the
# whole group at 00:00 on that date with a shared countdown, and print a warning
# that includes how much the tied perimeters' areas differ. A same-day
# assumption is fine if the areas are close (little fire growth between them);
# if they differ a lot, treating them as simultaneous is probably wrong and the
# input needs manual review.

import os
from datetime import timedelta

import arcpy

arcpy.env.overwriteOutput = True

# === workspace (.gdb) ===
# nestPerimeters.py writes here
GDB     = r"C:\Users\anson\Documents\westwide_treatment_effects\derived_data\daily_progression.gdb"
IN_FC   = "Daily_Progression_boxed"   # output of nestPerimeters.py
OUT_FC  = "Daily_Progression_timed"   # this script's output

src = os.path.join(GDB, IN_FC)
out = os.path.join(GDB, OUT_FC)

# === copy, then add the time fields ===
arcpy.management.CopyFeatures(src, out)
arcpy.management.AddField(out, "capture_dt", "DATE")
arcpy.management.AddField(out, "countdown", "LONG")

# === read features in progression order === 
# collect (capture_datetime, area, oid); skip rows with null geometry or null
# start_date 
rows = []
null_geom = []
null_date = []
with arcpy.da.SearchCursor(out, ["OID@", "SHAPE@", "start_date"]) as cur:
    for oid, shp, sdate in cur:
        if shp is None:
            null_geom.append(oid)
            continue
        if sdate is None:
            null_date.append(oid)
            continue
        # assume a 00:00 capture time on the recorded day
        midnight = sdate.replace(hour=0, minute=0, second=0, microsecond=0)
        rows.append((midnight, shp.area, oid))

for oid in null_geom:
    print(f"Skipping OID {oid}: null geometry.")
for oid in null_date:
    print(f"Skipping OID {oid}: null start_date.")

if len(rows) < 2:
    raise RuntimeError(
        f"{IN_FC} needs at least one perimeter plus the bounding box; got {len(rows)}."
    )

# (start_date, area, oid) ascending: the same key nestPerimeters.py sorted on to
# build its running union, so this reproduces its progression order exactly;
# oid only breaks the (rare) tie of equal date AND equal area.
rows.sort(key=lambda r: (r[0], r[1], r[2]))

# the box's start_date is last perimeter +1d (nestPerimeters.py), so it's always
# the last row here regardless of area
extinction, _, box_oid = rows[-1]
perims = rows[:-1]  # everything earlier, already in progression order

# sanity: box should post-date every perimeter (nestPerimeters guarantees this)
if extinction <= perims[-1][0]:
    raise RuntimeError(
        f"Bounding box timestamp {extinction:%Y-%m-%d} does not post-date the "
        f"last perimeter {perims[-1][0]:%Y-%m-%d}; check nestPerimeters.py output."
    )

# === resolve same-day ties ===
# every day that already holds a perimeter, plus extinction day, is "occupied"
occupied = {cap for cap, _, _ in perims}
occupied.add(extinction)

def area_growth_pct(group):
    """% growth from the smallest to the largest area in a tied-date group.
    Group entries are (capture_dt, area, oid); the (date, area, oid) sort makes
    group[0] the smallest and group[-1] the largest for a given date."""
    lo, hi = group[0][1], group[-1][1]
    return float("inf") if lo <= 0 else (hi - lo) / lo * 100


capture = {}   # oid -> resolved capture datetime
bumped = 0
i = 0
while i < len(perims):
    # perims is date-sorted, so a tied group is contiguous
    j = i
    while j + 1 < len(perims) and perims[j + 1][0] == perims[i][0]:
        j += 1
    group = perims[i:j + 1]
    day = perims[i][0]
    next_day = day + timedelta(days=1)
    # if group only contains 1 perimeter: good! continue.
    if len(group) == 1:
        capture[perims[i][2]] = day
        i = j + 1
        continue
    
    # if group contains two perimeters and next day is empty, bump perimeter 2
    # to the next day. 
    if len(group) == 2 and next_day not in occupied:
        # first flight stays at 00:00 of `day`; second flight moves to next day
        occupied.add(next_day)
        (_, _, first_oid), (_, _, second_oid) = group
        capture[first_oid] = day
        capture[second_oid] = next_day
        bumped += 1
        i = j + 1
        continue

    # If the group isn't resolved by now, we have an issue: either 3+ perimeters
    # share `day` (the early/late-flight assumption doesn't extend that far),
    # or exactly 2 do but `next_day` is already taken. Leave them all at 00:00
    # on `day` and warn, since a same-day assumption is only safe if they're
    # close in size.
    oids = [oid for _, _, oid in group]
    growth = area_growth_pct(group)
    why = (
        "more than two perimeters share this date"
        if len(group) > 2
        else f"{next_day:%Y-%m-%d} is already occupied, so it can't be split"
    )
    print(
        f"WARNING: {len(group)} perimeters share start_date {day:%Y-%m-%d} "
        f"(OIDs {oids}) and {why}. Areas span {group[0][1]:.0f} -> "
        f"{group[-1][1]:.0f} m^2 ({growth:.1f}% growth) but are all being "
        f"treated as captured at 00:00 on {day:%Y-%m-%d} with an identical "
        f"countdown - review these manually, especially if the growth is large."
    )
    for _, _, oid in group:
        capture[oid] = day
    i = j + 1

# === write capture_dt and countdown ===
with arcpy.da.UpdateCursor(out, ["OID@", "capture_dt", "countdown"]) as cur:
    for row in cur:
        oid = row[0]
        if oid == box_oid:
            row[1] = extinction
            row[2] = 0
        elif oid in capture:
            cap = capture[oid]
            row[1] = cap
            row[2] = int((extinction - cap).total_seconds())
        else:
            # null_geom / null_date rows: leave the new fields null
            continue
        cur.updateRow(row)

print(
    f"Timed {len(perims)} perimeters "
    f"({perims[0][0]:%Y-%m-%d} .. {perims[-1][0]:%Y-%m-%d}); "
    f"extinction {extinction:%Y-%m-%d}; bumped {bumped} same-day pair(s) +1 day."
)
print(f"Wrote {out}")
