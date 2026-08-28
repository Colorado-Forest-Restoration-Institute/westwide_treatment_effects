# === description ====
# EXPERIMENTAL script based on conversations with ChatGPT. May not work. Input:
# rasterized IR polygons, as used in target_selector.py. The script takes a
# partially known fire arrival-time raster and fills in missing values by
# solving a smoothed inverse Eikonal problem using PyTorch optimization, then
# outputs the completed raster to ArcGIS.
import arcpy
import numpy as np
import torch
import torch.nn.functional as F
import matplotlib.pyplot as plt

# --- Load observed arrival time raster ---
arcpy.env.workspace = r"C:\Users\anson\Documents\ArcGIS\Projects\FireSpread\FireSpread.gdb"
obs_arrival_time = arcpy.RasterToNumPyArray("irPerimsTimed_PolygonToLine_PolylineToRaster", nodata_to_value=-1)

# --- Convert to PyTorch ---
obs_arrival_time = torch.tensor(obs_arrival_time, dtype=torch.float32)
boundary_mask = obs_arrival_time >= 0  # Known burn times
boundary_times_tensor = obs_arrival_time.clone()
boundary_times_tensor[~boundary_mask] = 0  # Just to ensure no NaNs

H, W = obs_arrival_time.shape
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# --- Transfer to GPU ---
boundary_mask = boundary_mask.to(device)
boundary_times_tensor = boundary_times_tensor.to(device)

boundary_coords = torch.nonzero(boundary_mask, as_tuple=False)

# --- Initialize T with mean of known times ---
mean_time = boundary_times_tensor[boundary_mask].mean()
T_init = torch.full((H, W), mean_time.item(), device=device)
T_init[boundary_coords[:, 0], boundary_coords[:, 1]] = boundary_times_tensor[boundary_mask]

T = T_init.unsqueeze(0).unsqueeze(0).clone().detach().requires_grad_(True)

# --- Laplacian for smoothing ---
def compute_laplacian(tensor):
    kernel = torch.tensor([[0, 1, 0],
                           [1, -4, 1],
                           [0, 1, 0]], dtype=torch.float32, device=device).view(1, 1, 3, 3)
    return F.conv2d(tensor, kernel, padding=1)

# --- Optimization ---
steps = 20000
lr = 0.1
smooth_weight = 1e2
optimizer = torch.optim.Adam([T], lr=lr)

for step in range(steps):
    optimizer.zero_grad()

    pred_times = T[0, 0, boundary_coords[:, 0], boundary_coords[:, 1]]
    loss_data = F.mse_loss(pred_times, boundary_times_tensor[boundary_mask])

    loss_smooth = compute_laplacian(T).pow(2).mean()
    loss = loss_data + smooth_weight * loss_smooth

    loss.backward()
    optimizer.step()

    if step % 10 == 0 or step < 20:
        print(f"Step {step}: Loss = {loss.item():.2e} (Data: {loss_data.item():.2e}, Smooth: {loss_smooth.item():.4f})")

# --- Save or plot result ---
T_np = T.detach().cpu().numpy()[0, 0]

plt.imshow(T_np, cmap='inferno')
plt.title("Estimated Fire Arrival Times")
plt.colorbar()
plt.show()

# Optional: Save as .npy for future processing
# np.save("estimated_fire_times.npy", T_np)

raster = arcpy.Raster("irPerimsTimed_PolygonToLine_PolylineToRaster")
desc = arcpy.Describe(raster)
spatial_ref = desc.spatialReference

lower_left = arcpy.Point(raster.extent.XMin, raster.extent.YMin)
cell_size = raster.meanCellWidth

testout = arcpy.NumPyArrayToRaster(T_np, lower_left, cell_size, cell_size)
arcpy.DefineProjection_management(testout, spatial_ref)
testout.save("inverse_Eikonal")
