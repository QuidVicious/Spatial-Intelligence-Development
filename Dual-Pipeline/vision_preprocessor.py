"""
Vision Preprocessor Engine: PyTorch/CUDA accelerated illumination normalization.
Extracts geometric albedo from photogrammetry captures using Edge-Preserving Guided
Illumination Decomposition. Completely preserves high-frequency structural edges,
fenestration, and masonry details while lifting baked-in cast shadows.
"""

import base64
import gc
import io
from typing import Optional

import torch
import torch.nn.functional as F
import torchvision.transforms.functional as TF
from PIL import Image


def get_device() -> torch.device:
    """Safely resolves to CUDA on the RTX 4070."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _box_filter(x: torch.Tensor, r: int) -> torch.Tensor:
    """Fast O(1) box filter with reflection padding to eliminate edge dark-banding."""
    k_size = 2 * r + 1
    x_padded = F.pad(x, (r, r, r, r), mode="reflect")
    return F.avg_pool2d(x_padded, kernel_size=k_size, stride=1)


def guided_filter(guide: torch.Tensor, src: torch.Tensor, r: int = 16, eps: float = 0.01) -> torch.Tensor:
    """
    Native PyTorch Guided Filter.
    Smooths flat regions while strictly preventing filter leakage across high-contrast edges.
    """
    mean_guide = _box_filter(guide, r)
    mean_src = _box_filter(src, r)
    
    corr_guide = _box_filter(guide * guide, r)
    corr_guide_src = _box_filter(guide * src, r)
    
    var_guide = corr_guide - mean_guide * mean_guide
    cov_guide_src = corr_guide_src - mean_guide * mean_src
    
    a = cov_guide_src / (var_guide + eps)
    b = mean_src - a * mean_guide
    
    mean_a = _box_filter(a, r)
    mean_b = _box_filter(b, r)
    
    return mean_a * guide + mean_b


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
        
    # 1. Push to GPU: Shape [1, 3, H, W], Range [0.0, 1.0]
    t = TF.to_tensor(img).unsqueeze(0).to(device)
    eps = 1e-4

    # 2. Extract ITU-R BT.709 Standard Perceptual Luminance
    luminance = 0.2126 * t[:, 0:1, :, :] + 0.7152 * t[:, 1:2, :, :] + 0.0722 * t[:, 2:3, :, :]
    
    # 3. Log-Domain Illumination / Detail Decomposition
    log_lum = torch.log(luminance + eps)
    
    # Base Illumination: Smooths low-frequency light fields without crossing architectural edges
    base_illum = guided_filter(log_lum, log_lum, r=16, eps=0.02)
    
    # High-Frequency Detail: Contains 100% of colonnades, fenestration, stone joints, and leaves
    detail_residual = log_lum - base_illum
    
    # 4. Selective Dynamic Range Compression & Shadow Lift on Base Layer Only
    base_linear = torch.exp(base_illum) - eps
    base_max = torch.amax(base_linear, dim=(2, 3), keepdim=True).clamp(min=1e-3)
    norm_base = torch.clamp(base_linear / base_max, 0.0, 1.0)
    
    # Smooth gamma lift on low frequencies (lifts deep shadow regions toward neutral ambient)
    lifted_norm_base = torch.pow(norm_base, 0.72)
    lifted_base_linear = lifted_norm_base * base_max
    lifted_base_log = torch.log(lifted_base_linear + eps)
    
    # 5. Recombine Lifted Base with Boosted High-Frequency Detail (1.10x Crispness Factor)
    reconstructed_log = lifted_base_log + 1.10 * detail_residual
    reconstructed_lum = torch.clamp(torch.exp(reconstructed_log) - eps, 0.0, 1.0)
    
    # 6. Stable Luminance Ratio Scaling (Eliminates Noise Amplification in Shadows)
    lum_ratio = (reconstructed_lum + 1e-3) / (luminance + 1e-3)
    lum_ratio = torch.clamp(lum_ratio, 0.2, 3.5)
    
    # Apply soft chrominance-preserving scaling
    albedo = t * torch.pow(lum_ratio, 0.85)
    albedo = torch.clamp(albedo, 0.0, 1.0)
    
    # 7. Lossless PNG Output Encoding (Zero DCT Block Blur)
    albedo_cpu = albedo.squeeze(0).cpu()
    result_pil = TF.to_pil_image(albedo_cpu)
    
    buffered = io.BytesIO()
    result_pil.save(buffered, format="PNG", optimize=False)
    delighted_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    # 8. Memory Cleanup
    del t, luminance, log_lum, base_illum, detail_residual
    del base_linear, norm_base, lifted_norm_base, lifted_base_linear, lifted_base_log
    del reconstructed_log, reconstructed_lum, lum_ratio, albedo, albedo_cpu
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()
        
    return f"data:image/png;base64,{delighted_b64}"