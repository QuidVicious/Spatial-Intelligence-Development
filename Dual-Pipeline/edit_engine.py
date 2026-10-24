"""
Edit pass (2026-10-22/23): change one small area of a finished keystone at a time.

A polygon (2026-10-23) does the same for a band at an angle, and turns a long band level before the model sees it.
The area is cropped with a margin of context, sent to the image model twice (clean, and with a red rectangle marking
where the change goes) with the director's instruction, and only the area itself is pasted back, with soft edges.
Everything outside the area stays pixel for pixel as it was, whatever the model returns. Gemini 3.1 Flash Image
takes no mask, so the crop and the paste-back are what keep the edit local.
"""

import base64
import io
import os
import time
from typing import Dict, Any, List, Optional, Tuple

import requests
from fastapi import HTTPException

try:
    import numpy as np  # noqa: F401  (Pillow does the work; numpy kept for parity with the other engines)
    from PIL import Image, ImageDraw, ImageFilter
    _AVAILABLE = True
except Exception:          # pragma: no cover
    _AVAILABLE = False

# Aspect ratios the image model accepts; the crop is grown to the nearest one so nothing is squashed.
_RATIOS = {"1:1": 1.0, "5:4": 1.25, "4:5": 0.8, "4:3": 4 / 3, "3:4": 0.75, "3:2": 1.5, "2:3": 2 / 3,
           "16:9": 16 / 9, "9:16": 9 / 16, "21:9": 21 / 9}

EDIT_PROMPT = """You are retouching one small area of a finished architectural photograph.
IMAGE 1 is that area with some of its surroundings. IMAGE 2 is the same picture with a red rectangle marking exactly where the change goes.
Return IMAGE 1 with only this change made inside the red rectangle: {instruction}
The change fills the whole rectangle, edge to edge, unless the instruction says otherwise; do not shrink it or add a new border inside the rectangle. Everything outside the rectangle stays exactly as it is. Match the photograph's light, perspective, colour, grain, stone and weathering, so the change cannot be seen as an edit. The red rectangle is only a marker: your result must contain no red lines or marks of any kind. Add no text."""

# 2026-10-23: a polygon follows a band that runs at an angle (a cornice or balustrade in perspective). The rectangle's
# "fill the whole rectangle" rule made the model stamp a level balustrade across the box; this prompt asks it to follow
# the architecture instead.
POLY_PROMPT = """You are retouching one small area of a finished architectural photograph.
IMAGE 1 is that area with some of its surroundings. IMAGE 2 is the same picture with a red outline marking exactly where the change goes.
Return IMAGE 1 with only this change made inside the red outline: {instruction}
The change follows the lines and perspective of the architecture it sits on (the band of stone, the courses, the cornice), not the edges of the picture: the same slope, the same height on the wall and the same convergence as its surroundings. Fill the outlined area along its length. Everything outside the outline stays exactly as it is. Match the photograph's light, colour, grain, stone and weathering, so the change cannot be seen as an edit. The red outline is only a marker: your result must contain no red lines or marks of any kind. Add no text."""

LEVEL_LINE = ("The picture has been turned so that the outlined band runs level; keep the change level with it and in "
              "line with the courses of stone above and below.")

SAMPLE_LINE = ("IMAGE 3 is a sample from the same photograph showing how it should look: match its proportions, "
               "number and layout of panes, colour, materials and detail exactly, at the size and perspective of the "
               "rectangle in IMAGE 2.")


def _crop_region(W: int, H: int, box: Tuple[int, int, int, int], margin: float, base: Optional[float] = None) -> Tuple[Tuple[int, int, int, int], str]:
    x, y, w, h = box
    pad = int(round(margin * (base if base is not None else max(w, h))))
    cx, cy = x + w / 2.0, y + h / 2.0
    cw, ch = w + 2 * pad, h + 2 * pad
    target = min(_RATIOS.items(), key=lambda kv: abs(kv[1] - cw / ch))
    key, r = target
    if cw / ch < r:
        cw = ch * r
    else:
        ch = cw / r
    # 2026-10-24: a box taller (or wider) than about 45% of the image grows a crop bigger than the image; cutting it at
    # the image's edges changed its shape while the model was still asked for the old ratio, so the answer came back
    # squeezed (a full-height box round a street lamp: facades at the wrong scale, smeared stone). After cutting, the crop
    # is trimmed to an accepted ratio again, always keeping the whole box inside it.
    if cw > W or ch > H:
        cw, ch = min(cw, W), min(ch, H)
        for key, r in sorted(_RATIOS.items(), key=lambda kv: abs(kv[1] - cw / ch)):
            tw, th = (ch * r, ch) if cw / ch > r else (cw, cw / r)
            if tw >= w and th >= h:
                cw, ch = tw, th
                break
        else:
            key = min(_RATIOS.items(), key=lambda kv: abs(kv[1] - cw / ch))[0]   # no accepted ratio holds the box: closest
    x0 = int(round(min(max(cx - cw / 2, 0), W - cw)))
    y0 = int(round(min(max(cy - ch / 2, 0), H - ch)))
    return (x0, y0, x0 + int(round(cw)), y0 + int(round(ch))), key


def _align_shift(orig, edited, box_rel, max_shift: int = 24):
    """Translation (dx, dy) that best lines the model's crop up with the original, measured by phase correlation on
    the margin around the box (the box itself is masked out, since it is meant to differ). (0, 0) if unsure."""
    try:
        a = np.asarray(orig.convert("L"), dtype=np.float32)
        b = np.asarray(edited.convert("L"), dtype=np.float32)
        bx, by, bw, bh = box_rel
        m = np.ones_like(a)
        m[max(0, by):by + bh, max(0, bx):bx + bw] = 0
        if m.mean() < 0.15:
            return 0, 0
        a = (a - a[m > 0].mean()) * m
        b = (b - b[m > 0].mean()) * m
        win = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1])).astype(np.float32)
        fa, fb = np.fft.fft2(a * win), np.fft.fft2(b * win)
        r = fa * np.conj(fb)
        r /= np.abs(r) + 1e-6
        c = np.abs(np.fft.ifft2(r))
        py, px = np.unravel_index(np.argmax(c), c.shape)
        if py > a.shape[0] // 2:
            py -= a.shape[0]
        if px > a.shape[1] // 2:
            px -= a.shape[1]
        if abs(px) > max_shift or abs(py) > max_shift or c.max() < 3 * c.mean():
            return 0, 0
        return int(px), int(py)
    except Exception:
        return 0, 0


def _call_model(parts: list, ratio: str, model_name: str, api_key: str):
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "temperature": 0.0,
                             "imageConfig": {"aspectRatio": ratio, "imageSize": "2K"}},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"The edit call failed: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"The edit call failed: {resp.text[:400]}")
    out = ((resp.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    data = next((p.get("inlineData") or p.get("inline_data") for p in out if (p.get("inlineData") or p.get("inline_data"))), None)
    if not data or "data" not in data:
        said = " ".join(p.get("text", "") for p in out if "text" in p).strip()
        raise HTTPException(status_code=502, detail="The model returned no image" + (f": {said[:300]}" if said else "."))
    return Image.open(io.BytesIO(base64.b64decode(data["data"]))).convert("RGB")


def _band_angle(pts) -> Tuple[float, float]:
    """Direction of a polygon's long axis in degrees (image coordinates, y down) and how elongated it is (long / short
    extent along the principal axes). Used to turn a sloping band level before the model sees it."""
    a = np.asarray(pts, dtype=np.float64)
    c = a - a.mean(axis=0)
    if len(a) < 3:
        return 0.0, 1.0
    vals, vecs = np.linalg.eigh(np.cov(c.T))
    v = vecs[:, int(np.argmax(vals))]
    ang = float(np.degrees(np.arctan2(v[1], v[0])))
    if ang > 90:
        ang -= 180
    if ang < -90:
        ang += 180
    proj_l = c @ v
    proj_s = c @ np.array([-v[1], v[0]])
    elong = float((proj_l.max() - proj_l.min()) / max(1e-6, proj_s.max() - proj_s.min()))
    return ang, elong


def _poly_mask(size, pts, feather: int):
    """Soft mask that is 255 well inside the polygon, falls to 0 at its edge and is 0 everywhere outside it."""
    hard = Image.new("L", size, 0)
    ImageDraw.Draw(hard).polygon([tuple(p) for p in pts], fill=255)
    if feather <= 2:
        return hard, hard
    soft = hard.filter(ImageFilter.GaussianBlur(feather / 2))
    soft = soft.point(lambda v: max(0, min(255, (v - 128) * 2)))
    return Image.composite(soft, hard, hard), hard


def _outline_ring(size, pts, gap: int, lw: int):
    """A ring just OUTSIDE the polygon, for the red marker (so a copied line never reaches the pasted area)."""
    hard = Image.new("L", size, 0)
    ImageDraw.Draw(hard).polygon([tuple(p) for p in pts], fill=255)
    inner = hard.filter(ImageFilter.MaxFilter(2 * gap + 1))
    outer = inner.filter(ImageFilter.MaxFilter(2 * lw + 1))
    return Image.eval(Image.composite(Image.new("L", size, 0), outer, inner), lambda v: v)


def apply_poly_edit(base_path: str, out_path: str, poly_frac: List[List[float]], instruction: str, margin: float = 0.6,
                    model_name: str = "gemini-3.1-flash-image", api_key: Optional[str] = None,
                    sample_frac: Optional[List[float]] = None, edge: str = "soft", straighten: bool = True) -> Dict[str, Any]:
    """Edit inside a polygon. A long band at an angle is turned level first (the model draws level architecture far
    better), edited, and turned back; only pixels inside the polygon can change."""
    if not _AVAILABLE:
        raise HTTPException(status_code=500, detail="The edit pass needs Pillow and numpy on the server.")
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")
    img = Image.open(base_path).convert("RGB")
    W, H = img.size
    pts = [(min(max(float(p[0]), 0.0), 1.0) * W, min(max(float(p[1]), 0.0), 1.0) * H) for p in poly_frac]
    if len(pts) < 3:
        raise HTTPException(status_code=400, detail="A polygon needs at least three corners.")
    ang, elong = _band_angle(pts)
    turn = bool(straighten) and elong >= 2.0 and 2.0 <= abs(ang) <= 40.0
    cx, cy = float(np.mean([p[0] for p in pts])), float(np.mean([p[1] for p in pts]))
    if turn:
        # PIL turns counter-clockwise for positive degrees; a band rising to the right (negative angle, y down) turns by ang.
        rot = img.rotate(ang, resample=Image.BICUBIC, center=(cx, cy), fillcolor=(0, 0, 0))
        t = np.radians(ang)
        ct, st = np.cos(t), np.sin(t)
        # Image.rotate(a) maps a source point p to R(-a) about the centre, in y-down coordinates.
        rpts = [(cx + (px - cx) * ct + (py - cy) * st, cy - (px - cx) * st + (py - cy) * ct) for px, py in pts]
    else:
        rot, rpts = img, pts
    xs, ys = [p[0] for p in rpts], [p[1] for p in rpts]
    x, y = int(np.floor(min(xs))), int(np.floor(min(ys)))
    w, h = int(np.ceil(max(xs))) - x, int(np.ceil(max(ys))) - y
    x, y = max(0, x), max(0, y)
    w, h = min(w, W - x), min(h, H - y)
    if w < 8 or h < 8:
        raise HTTPException(status_code=400, detail="The area is too small to edit: draw a larger shape.")
    # A long thin band would pull in most of the picture if the context were a share of its length; use its thickness,
    # or a quarter of its length if that is more.
    (x0, y0, x1, y1), ratio = _crop_region(W, H, (x, y, w, h), max(0.15, min(margin, 2.0)), max(min(w, h), 0.25 * max(w, h)))
    crop = rot.crop((x0, y0, x1, y1))
    cpts = [(px - x0, py - y0) for px, py in rpts]
    lw = max(3, (x1 - x0) // 200)
    ring = _outline_ring(crop.size, cpts, lw + 2, lw)
    marked = Image.composite(Image.new("RGB", crop.size, (255, 0, 0)), crop, ring)

    parts = [
        {"inlineData": {"mimeType": "image/png", "data": _b64png(crop)}},
        {"inlineData": {"mimeType": "image/png", "data": _b64png(marked)}},
    ]
    prompt = POLY_PROMPT.format(instruction=instruction.strip())
    if turn:
        prompt += "\n" + LEVEL_LINE
    sample_px = None
    if sample_frac:
        sx, sy, sw, sh = [float(v) for v in sample_frac]
        sx0, sy0 = int(max(0.0, sx) * W), int(max(0.0, sy) * H)
        sx1, sy1 = int(min(1.0, sx + sw) * W), int(min(1.0, sy + sh) * H)
        if sx1 - sx0 >= 8 and sy1 - sy0 >= 8:
            sample = img.crop((sx0, sy0, sx1, sy1))
            if turn:
                sample = sample.rotate(ang, resample=Image.BICUBIC, expand=True, fillcolor=(0, 0, 0))
            parts.append({"inlineData": {"mimeType": "image/png", "data": _b64png(sample)}})
            prompt += "\n" + SAMPLE_LINE.replace("rectangle in IMAGE 2", "outlined area in IMAGE 2")
            sample_px = [sx0, sy0, sx1 - sx0, sy1 - sy0]
    parts.append({"text": prompt})
    t0 = time.perf_counter()
    edited = _call_model(parts, ratio, model_name, api_key).resize(crop.size, Image.LANCZOS)
    dx, dy = _align_shift(crop, edited, (x - x0, y - y0, w, h))
    if dx or dy:
        shifted = crop.copy()
        shifted.paste(edited, (dx, dy))
        edited = shifted

    feather = {"sharp": 2, "wide": max(6, int(0.12 * min(w, h)))}.get(edge, max(4, int(0.05 * min(w, h))))
    mask, _ = _poly_mask(crop.size, cpts, feather)
    if turn:
        # Put the edited crop and its mask into the turned frame, turn both back, and blend in the original frame.
        canvas = rot.copy()
        canvas.paste(edited, (x0, y0))
        mfull = Image.new("L", (W, H), 0)
        mfull.paste(mask, (x0, y0))
        back = canvas.rotate(-ang, resample=Image.BICUBIC, center=(cx, cy), fillcolor=(0, 0, 0))
        mback = mfull.rotate(-ang, resample=Image.BICUBIC, center=(cx, cy), fillcolor=0)
        hard = Image.new("L", (W, H), 0)
        ImageDraw.Draw(hard).polygon([tuple(p) for p in pts], fill=255)
        mback = Image.composite(mback, hard, hard)   # nothing outside the polygon, as drawn, can change
        out = Image.composite(back, img, mback)
    else:
        patch = Image.composite(edited, crop, mask)
        out = img.copy()
        out.paste(patch, (x0, y0))
    out.save(out_path, format="PNG")
    bx0, by0 = int(min(p[0] for p in pts)), int(min(p[1] for p in pts))
    return {"crop": [x0, y0, x1, y1], "box_px": [bx0, by0, int(max(p[0] for p in pts)) - bx0, int(max(p[1] for p in pts)) - by0],
            "poly_px": [[round(p[0]), round(p[1])] for p in pts], "sample_px": sample_px, "aspect": ratio, "feather_px": feather,
            "edge": edge, "straightened_deg": round(ang, 1) if turn else 0.0, "elongation": round(elong, 1),
            "latency_ms": round((time.perf_counter() - t0) * 1000), "model": model_name, "aligned_shift": [dx, dy]}


def _b64png(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def apply_edit(base_path: str, out_path: str, box_frac: List[float], instruction: str, margin: float = 0.6,
               model_name: str = "gemini-3.1-flash-image", api_key: Optional[str] = None,
               sample_frac: Optional[List[float]] = None, edge: str = "soft") -> Dict[str, Any]:
    if not _AVAILABLE:
        raise HTTPException(status_code=500, detail="The edit pass needs Pillow and numpy on the server.")
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")
    img = Image.open(base_path).convert("RGB")
    W, H = img.size
    fx, fy, fw, fh = [float(v) for v in box_frac]
    x, y = int(round(max(0.0, fx) * W)), int(round(max(0.0, fy) * H))
    w, h = int(round(min(fw, 1.0 - max(0.0, fx)) * W)), int(round(min(fh, 1.0 - max(0.0, fy)) * H))
    if w < 8 or h < 8:
        raise HTTPException(status_code=400, detail="The area is too small to edit: draw a larger box.")
    (x0, y0, x1, y1), ratio = _crop_region(W, H, (x, y, w, h), max(0.15, min(margin, 2.0)))
    crop = img.crop((x0, y0, x1, y1))
    marked = crop.copy()
    bx, by = x - x0, y - y0
    # 2026-10-23: the marker is drawn just OUTSIDE the box, so if the model copies the red line into its result (it did),
    # the line falls outside the pasted area and never reaches the plate.
    lw = max(3, (x1 - x0) // 200)
    gap = lw + 2
    ImageDraw.Draw(marked).rectangle([max(0, bx - gap), max(0, by - gap), min(x1 - x0 - 1, bx + w + gap), min(y1 - y0 - 1, by + h + gap)],
                                     outline=(255, 0, 0), width=lw)

    parts = [
        {"inlineData": {"mimeType": "image/png", "data": _b64png(crop)}},
        {"inlineData": {"mimeType": "image/png", "data": _b64png(marked)}},
    ]
    prompt = EDIT_PROMPT.format(instruction=instruction.strip())
    sample_px = None
    if sample_frac:
        sx, sy, sw, sh = [float(v) for v in sample_frac]
        sx0, sy0 = int(max(0.0, sx) * W), int(max(0.0, sy) * H)
        sx1, sy1 = int(min(1.0, sx + sw) * W), int(min(1.0, sy + sh) * H)
        if sx1 - sx0 >= 8 and sy1 - sy0 >= 8:
            parts.append({"inlineData": {"mimeType": "image/png", "data": _b64png(img.crop((sx0, sy0, sx1, sy1)))}})
            prompt += "\n" + SAMPLE_LINE
            sample_px = [sx0, sy0, sx1 - sx0, sy1 - sy0]
    parts.append({"text": prompt})
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "temperature": 0.0,
                             "imageConfig": {"aspectRatio": ratio, "imageSize": "2K"}},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    t0 = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"The edit call failed: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"The edit call failed: {resp.text[:400]}")
    parts = ((resp.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    data = next((p.get("inlineData") or p.get("inline_data") for p in parts if (p.get("inlineData") or p.get("inline_data"))), None)
    if not data or "data" not in data:
        said = " ".join(p.get("text", "") for p in parts if "text" in p).strip()
        raise HTTPException(status_code=502, detail="The model returned no image" + (f": {said[:300]}" if said else "."))
    edited = Image.open(io.BytesIO(base64.b64decode(data["data"]))).convert("RGB").resize(crop.size, Image.LANCZOS)
    # 2026-10-23: the model redraws the whole crop slightly out of register; line it up with the original on the margin
    # before blending, so courses of stone meet instead of ghosting across the soft edge.
    dx, dy = _align_shift(crop, edited, (bx, by, w, h))
    if dx or dy:
        shifted = crop.copy()
        shifted.paste(edited, (dx, dy))
        edited = shifted

    # Paste back only the area. 2026-10-23: the box is a hard limit; the soft edge sits INSIDE it, so nothing outside the
    # box changes (a soft edge reaching outward blurred the neighbouring building). Edge: sharp, soft or very soft.
    feather = {"sharp": 2, "wide": max(6, int(0.12 * min(w, h)))}.get(edge, max(4, int(0.05 * min(w, h))))
    mask = Image.new("L", crop.size, 0)
    inset = feather
    ImageDraw.Draw(mask).rectangle([bx + inset, by + inset, bx + w - inset, by + h - inset], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather / 2))
    clip = Image.new("L", crop.size, 0)
    ImageDraw.Draw(clip).rectangle([bx, by, bx + w - 1, by + h - 1], fill=255)
    mask = Image.composite(mask, clip, clip)   # anything outside the box is forced back to the original
    patch = Image.composite(edited, crop, mask)
    out = img.copy()
    out.paste(patch, (x0, y0))
    out.save(out_path, format="PNG")
    return {"crop": [x0, y0, x1, y1], "box_px": [x, y, w, h], "sample_px": sample_px, "aspect": ratio, "feather_px": feather, "edge": edge,
            "latency_ms": round((time.perf_counter() - t0) * 1000), "model": model_name, "aligned_shift": [dx, dy]}
