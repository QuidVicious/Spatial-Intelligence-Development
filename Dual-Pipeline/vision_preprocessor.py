"""
Vision Preprocessor Engine: PyTorch/CUDA accelerated illumination normalization.
Extracts geometric albedo from photogrammetry captures by lifting baked-in cast shadows
and equalizing directional luminance for a lighting-neutral canvas.
"""

import base64
import io
from typing import Optional
import gc 

import torch
import torchvision.transforms.functional as TF
from PIL import Image


def get_device() -> torch.device:
    """Safely resolves to CUDA on the RTX 4070."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def delight_image(base64_str: Optional[str]) -> Optional[str]:
    if not base64_str:
        return None
        
    device = get_device()
    
    try:
        raw_b64 = base64_str.split(",")[-1] if "," in base64_str else base64_str
        img_data = base64.b64decode(raw_b64)
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
    except Exception as e:
        print(f"[Vision Preprocessor] Error decoding image: {e}")
        return base64_str
        
    # 1. Push to GPU (Shape: [1, 3, H, W], Range: [0.0, 1.0])
    t = TF.to_tensor(img).unsqueeze(0).to(device)
    
    # 2. Extract Luminance Channel
    luminance = (0.299 * t[:, 0:1, :, :] + 0.587 * t[:, 1:2, :, :] + 0.114 * t[:, 2:3, :, :])
    
    # 3. Multi-Scale Ambient Illumination Estimation
    scales = [63, 127, 255]
    illumination = torch.zeros_like(luminance)
    for kernel_size in scales:
        sigma = kernel_size / 3.0
        illumination += TF.gaussian_blur(luminance, kernel_size=[kernel_size, kernel_size], sigma=[sigma, sigma])
    illumination = illumination / len(scales)
    
    # 4. Shadow Detection & Chromaticity-Preserving Shadow Lift
    # Measure ratio of actual luminance to surrounding ambient illumination
    lum_ratio = luminance / (illumination + 1e-4)
    
    # Smooth shadow mask: 1.0 for deep cast shadows, 0.0 for ambient/unshadowed terrain
    shadow_mask = torch.clamp((0.85 - lum_ratio) / 0.55, 0.0, 1.0)
    
    # Extract pure color chromaticity (normalized RGB ratios)
    chroma = t / (luminance + 1e-4)
    
    # Dynamically lift shadow luminance toward the surrounding ambient level
    lifted_lum = luminance + (illumination - luminance) * shadow_mask * 0.90
    
    # Compress extreme dynamic range smoothly
    lifted_lum = torch.pow(lifted_lum, 0.88)
    
    # 5. Recombine boosted luminance with chromaticity
    albedo = chroma * lifted_lum
    albedo = torch.clamp(albedo, 0.0, 1.0)
    
    # Global brightness balancing
    target_mean = 0.48
    current_mean = albedo.mean()
    if current_mean > 1e-3:
        albedo = albedo * (target_mean / current_mean)
    albedo = torch.clamp(albedo, 0.0, 1.0)
    
    # 6. Encode output to Base64 JPEG
    albedo_cpu = albedo.squeeze(0).cpu()
    result_pil = TF.to_pil_image(albedo_cpu)
    
    buffered = io.BytesIO()
    result_pil.save(buffered, format="JPEG", quality=92)
    delighted_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    # 7. Explicit CUDA Memory Cleanup
    del t
    del luminance
    del illumination
    del albedo
    del albedo_cpu
    del chroma
    del lifted_lum
    del shadow_mask
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()
        
    return f"data:image/jpeg;base64,{delighted_b64}"