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
  4. clean up (close gaps between leaves, drop specks)
  5. keep only patches anchored by real canopy (dense AND textured vegetation), which drops mossy
     stone and mown lawn, then feather the edge

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

WORK_WIDTH = 1600          # the mask is computed at this width, whatever the output size, so every
                           # threshold below stays calibrated (tuned on St Andrews prints at 1600 px)
DENSITY_WINDOW = 7         # box radius (px, working size) for the vegetation-density check
MIN_VEG_DENSITY = 0.55     # canopy cores measure ~0.8-1.0; speckled or mossy stone ~0.3
MIN_NEW_FOLIAGE_DENSITY = 0.40  # share of a neighbourhood that is new foliage before it counts
MIN_TEXTURE = 9.0          # local luminance std (working size): canopy ~15, mown lawn ~5
MAX_LIGHT_DIFFERENCE = 0.12 # buildings+ground brightness, render vs plate. June-noon Overcast renders
                           # measured within ~2% of the January-noon St Andrews plate; evening or
                           # darker light would leave a seam around every canopy, so skip beyond this.
MAX_COVERAGE = 0.60        # if more than this much "changed", something global moved: don't composite
MAX_STRUCTURE_CHANGE = 0.25  # share of NON-vegetation pixels that changed, at working size. Raw renders
                             # shimmy at ~0.11 (two same-seed St Andrews prints); a ~3 px camera shift
                             # at full size reaches ~0.35. Above this, the frame itself moved.


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


def _local_std(gray: "np.ndarray", radius: int = 4) -> "np.ndarray":
    img = Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8))
    m = np.asarray(img.filter(ImageFilter.BoxBlur(radius))).astype(np.float32)
    sq = Image.fromarray(np.clip(gray * gray / 255.0, 0, 255).astype(np.uint8))
    m2 = np.asarray(sq.filter(ImageFilter.BoxBlur(radius))).astype(np.float32) * 255.0
    return np.sqrt(np.maximum(m2 - m * m, 0.0))


def _keep_patches_with(mask: "np.ndarray", seeds: "np.ndarray") -> "np.ndarray":
    """Connected patches of `mask` that contain at least one seed pixel."""
    try:
        from scipy import ndimage
        labels, n = ndimage.label(mask)
        keep = np.unique(labels[seeds & mask])
        keep = keep[keep > 0]
        return np.isin(labels, keep)
    except Exception:
        # No scipy: flood the seeds through the mask by repeated constrained dilation.
        out = seeds & mask
        for _ in range(400):
            grown = _morph(out, "dilate", 9) & mask
            if grown.sum() == out.sum():
                break
            out = grown
        return out


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
    full_size = plate_img.size

    # Work on copies at a fixed width, so fine speckle (weathering, moss) can't merge into patches
    # and every threshold keeps the calibration it was tuned at.
    if plate_img.width > WORK_WIDTH:
        work = (WORK_WIDTH, round(plate_img.height * WORK_WIDTH / plate_img.width))
        P = np.asarray(plate_img.resize(work, Image.LANCZOS)).astype(np.float32)
        R = np.asarray(render_img.resize(work, Image.LANCZOS)).astype(np.float32)
    else:
        P = np.asarray(plate_img).astype(np.float32)
        R = np.asarray(render_img).astype(np.float32)

    # 1. tone-match the render to the plate, per channel
    Rm = (R - R.mean(axis=(0, 1))) / (R.std(axis=(0, 1)) + 1e-6) * P.std(axis=(0, 1)) + P.mean(axis=(0, 1))

    # 2. noticeable change, smoothed so single-pixel texture differences don't count
    diff = np.abs(Rm - P).mean(axis=2)
    diff = np.asarray(Image.fromarray(np.clip(diff, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(np.float32)
    changed = diff > threshold

    # 3. only changes that are vegetation in either image
    veg_r, veg_p = _vegetation(R), _vegetation(P)
    veg = veg_r | veg_p
    # New leaves over bare branches are mostly a change of COLOUR (brown-grey to green) at similar
    # brightness, which the channel-average difference above barely registers (median ~19 against a
    # threshold of 18 on June St Andrews renders, so half were missed). A pixel that is vegetation in
    # the render but not in the plate is, by definition, new foliage: count it as changed too.
    # Only where it is dense: a canopy grows over an area, while weathered stone and lawn flip in and
    # out of the colour test in scattered specks (the column torus did exactly that).
    new_foliage = veg_r & ~veg_p
    nf_density = np.asarray(Image.fromarray((new_foliage * 255).astype(np.uint8)).filter(
        ImageFilter.BoxBlur(DENSITY_WINDOW))).astype(np.float32) / 255.0
    changed = changed | (new_foliage & (nf_density >= MIN_NEW_FOLIAGE_DENSITY))
    structure_change = float((changed & ~veg).sum() / max((~veg).sum(), 1))
    stone = ~veg
    light_ratio = float(R.mean(axis=2)[stone].mean() / max(P.mean(axis=2)[stone].mean(), 1e-6)) if stone.any() else 1.0
    mask = changed & veg

    # 4. close gaps between leaves, drop specks, grow slightly to cover leaf edges
    mask = _morph(_morph(mask, "dilate", 9), "erode", 9)     # closing
    mask = _morph(_morph(mask, "erode", 5), "dilate", 5)     # opening
    mask = _morph(mask, "dilate", 5)

    # 5. keep only patches that contain real canopy. A canopy is solidly vegetation over an area;
    # weathered or mossy stone is only speckled with it (the Melville column's torus: about a third
    # of its olive-tinted pixels pass the colour test, and step 4 merged them into a band).
    # Any patch without a dense-vegetation core is dropped whole; canopies keep their full outline.
    # Cores must also be textured: mown lawn is dense green too, but smooth, and its mowing stripes
    # change on every render. Lawn is not seasonal in an Overcast series, so it stays from the plate.
    density = np.asarray(Image.fromarray((veg * 255).astype(np.uint8)).filter(
        ImageFilter.BoxBlur(DENSITY_WINDOW))).astype(np.float32) / 255.0
    texture = _local_std(R.mean(axis=2))
    cores = mask & changed & veg & (density >= MIN_VEG_DENSITY) & (texture >= MIN_TEXTURE)
    mask = _keep_patches_with(mask, cores)

    coverage = float(mask.mean())
    info: Dict[str, Any] = {"threshold": threshold, "mask_coverage": round(coverage, 4),
                            "structure_change": round(structure_change, 4), "light_ratio": round(light_ratio, 3)}
    if abs(light_ratio - 1.0) > MAX_LIGHT_DIFFERENCE:
        info.update(applied=False, reason=f"light level differs from the keystone by {abs(light_ratio - 1.0):.0%}; "
                                          "the canopy would not match its surroundings")
        return None, None, info
    if structure_change > MAX_STRUCTURE_CHANGE:
        info.update(applied=False, reason=f"{structure_change:.0%} of buildings and ground changed; the frame itself seems to have moved")
        return None, None, info
    if coverage > MAX_COVERAGE:
        info.update(applied=False, reason=f"{coverage:.0%} of the frame changed; too much to be canopy alone")
        return None, None, info

    alpha_img = Image.fromarray((mask * 255).astype(np.uint8))
    if alpha_img.size != full_size:
        alpha_img = alpha_img.resize(full_size, Image.BILINEAR)
    alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(max(1.0, 3.0 * full_size[0] / WORK_WIDTH)))
    A = (np.asarray(alpha_img).astype(np.float32) / 255.0)[..., None]
    Pf = np.asarray(plate_img).astype(np.float32)
    Rf = np.asarray(render_img).astype(np.float32)
    out = A * Rf + (1.0 - A) * Pf
    out_img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

    info.update(applied=True, reason="render weather matches the keystone")
    return _encode_png(out_img), _encode_png(alpha_img.convert("L")), info
