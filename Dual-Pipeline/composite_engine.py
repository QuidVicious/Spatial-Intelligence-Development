"""
Composite Engine: canopy-only prints.

A print from a keystone should change only the trees (and the light). The renderer
redraws the whole frame, so buildings, windows and weathering shimmy from print to
print. This module keeps every pixel of the approved keystone plate EXCEPT where the
vegetation changed, taking those regions from the new render.

The canopy mask is found by comparison, not by recognising trees:
  1. tone-match the render to the plate (so a small overall brightness shift is ignored)
  2. mark pixels that changed noticeably
  3. keep only changes that look like vegetation in either image (green, or saturated
     autumn yellow/orange); this excludes buff sandstone, grey stone and cyan glazing
  4. clean up (close gaps between leaves, drop specks), then feather the edge

Only valid when the render's light matches the plate's (the neutral Overcast keystone):
outside the canopy the plate's light is kept, so a sunny or rainy print would end up
half in the wrong weather. The caller decides when to apply it.
Requires numpy and Pillow; if either is missing, compositing is skipped, never fatal.
"""

import base64
import io
from typing import Optional, Tuple, Dict, Any

try:
    import numpy as np
    from PIL import Image, ImageFilter
    _AVAILABLE = True
except Exception:          # pragma: no cover
    _AVAILABLE = False

MAX_COVERAGE = 0.60        # if more than this much "changed", something global moved: don't composite
MAX_STRUCTURE_CHANGE = 0.30  # share of NON-vegetation pixels that changed. Real renders shimmy at about
                             # 0.18 (measured on two same-seed St Andrews prints); a 3 px camera shift
                             # reaches about 0.36. Above this, the frame itself moved: don't composite.


def _decode(data_url: str) -> "Image.Image":
    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    return Image.open(io.BytesIO(base64.b64decode(raw))).convert("RGB")


def _encode_png(img: "Image.Image") -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _vegetation(rgb: "np.ndarray") -> "np.ndarray":
    """Green foliage and turf, or saturated autumn yellow/orange/red. Excludes buff stone and cyan glass."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = (mx - mn) / np.maximum(mx, 1.0)
    # hue in degrees
    d = np.maximum(mx - mn, 1e-6)
    hue = np.where(mx == r, (60 * ((g - b) / d)) % 360,
          np.where(mx == g, 60 * ((b - r) / d) + 120, 60 * ((r - g) / d) + 240))
    green = (hue >= 65) & (hue <= 165) & (sat >= 0.12) & (mx >= 30)
    autumn = (hue >= 10) & (hue < 65) & (sat >= 0.38) & (mx >= 45)
    return green | autumn


def _morph(mask: "np.ndarray", op: str, size: int) -> "np.ndarray":
    im = Image.fromarray((mask * 255).astype(np.uint8))
    f = ImageFilter.MaxFilter(size) if op == "dilate" else ImageFilter.MinFilter(size)
    return np.asarray(im.filter(f)) > 127


def composite_canopy(
    plate_b64: str,
    render_b64: str,
    threshold: float = 18.0,
) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Returns (composite_png_data_url, mask_png_data_url, info).
    On any problem returns (None, None, info) with info["applied"] False and a reason.
    """
    if not _AVAILABLE:
        return None, None, {"applied": False, "reason": "numpy/Pillow not available"}
    try:
        plate_img = _decode(plate_b64)
        render_img = _decode(render_b64)
    except Exception as e:
        return None, None, {"applied": False, "reason": f"could not decode images: {e}"}

    if render_img.size != plate_img.size:
        render_img = render_img.resize(plate_img.size, Image.LANCZOS)

    P = np.asarray(plate_img).astype(np.float32)
    R = np.asarray(render_img).astype(np.float32)

    # 1. tone-match the render to the plate, per channel
    Rm = (R - R.mean(axis=(0, 1))) / (R.std(axis=(0, 1)) + 1e-6) * P.std(axis=(0, 1)) + P.mean(axis=(0, 1))

    # 2. noticeable change, smoothed so single-pixel texture differences don't count
    diff = np.abs(Rm - P).mean(axis=2)
    diff = np.asarray(Image.fromarray(np.clip(diff, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(np.float32)
    changed = diff > threshold

    # 3. only changes that are vegetation in either image
    veg = _vegetation(R) | _vegetation(P)
    structure_change = float((changed & ~veg).sum() / max((~veg).sum(), 1))
    mask = changed & veg

    # 4. close gaps between leaves, drop specks, grow slightly to cover leaf edges
    mask = _morph(_morph(mask, "dilate", 9), "erode", 9)     # closing
    mask = _morph(_morph(mask, "erode", 5), "dilate", 5)     # opening
    mask = _morph(mask, "dilate", 5)

    coverage = float(mask.mean())
    info: Dict[str, Any] = {"threshold": threshold, "mask_coverage": round(coverage, 4),
                            "structure_change": round(structure_change, 4)}
    if structure_change > MAX_STRUCTURE_CHANGE:
        info.update(applied=False, reason=f"{structure_change:.0%} of buildings and ground changed; the frame itself seems to have moved")
        return None, None, info
    if coverage > MAX_COVERAGE:
        info.update(applied=False, reason=f"{coverage:.0%} of the frame changed; too much to be canopy alone")
        return None, None, info

    alpha_img = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    A = (np.asarray(alpha_img).astype(np.float32) / 255.0)[..., None]
    out = A * R + (1.0 - A) * P
    out_img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

    info.update(applied=True, reason="render weather matches the keystone")
    return _encode_png(out_img), _encode_png(alpha_img.convert("L")), info
