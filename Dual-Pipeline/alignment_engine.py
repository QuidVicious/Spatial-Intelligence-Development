"""
Alignment Engine (2026-10-17): has a rendered plate kept the capture's framing?

A keystone render is meant to keep the capture's composition exactly, but the image model sometimes
moves the frame: tilts, turns or zooms out. This module measures that move, so a drifted candidate
is flagged before it becomes a keystone, and an A/B pair is only compared when both arms held.

How it measures: the capture (photogrammetry) and the render (photographic) look nothing alike pixel
for pixel, but their strong edges line up: rooflines, facade edges, windows, kerbs. Both images are
reduced to an edge-direction field (direction only, so light and colour differences matter little),
and the render is scaled, rotated and shifted until its edges best match the capture's. A coarse search
at 320 px width is refined at 640 px. Tested on the Abercromby and Nelson runs of 2026-10-09 and
2026-10-16: the aligned keystone measured no shift, and warping each drifted render by the measured
amount put the target building back on the capture.

Numbers are in capture pixels and describe how to move the RENDER onto the CAPTURE:
  scale > 1   the render is zoomed out (its content is smaller) and must be enlarged
  dy < 0      the render's content sits lower than the capture's and must move up (as if the camera tilted up)
  dx < 0      the render's content sits to the right of the capture's and must move left
Requires numpy and Pillow; if either is missing, nothing is measured, never fatal.
"""

from pathlib import Path
from typing import Any, Dict, Optional

try:
    import numpy as np
    from PIL import Image, ImageFilter
    _AVAILABLE = True
except Exception:          # pragma: no cover
    _AVAILABLE = False

VERSION = 1
# "Aligned" tolerance, agreed with Don 2026-10-17: the 14:39 A arm measured 4% zoomed out and he judged it on frame.
MAX_SHIFT_FRACTION = 30 / 2560     # 30 px at 2560 wide
MAX_ZOOM = 0.05                    # 5%
MAX_ROTATION = 1.0                 # degrees
MIN_SCORE = 0.06                   # below this the edges barely match: the result is not trusted
MIN_REALIGN_COVERAGE = 0.96        # realign only when the warped render covers at least 96% of the frame


def _field(img: "Image.Image") -> "np.ndarray":
    a = np.asarray(img.filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32) / 255.0
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    z = gx + 1j * gy
    m = np.abs(z)
    f = np.where(m > 1e-4, (z * z) / np.maximum(m, 1e-6), 0)   # doubled angle: an edge matches whichever side is darker
    return f / (np.abs(f) + 0.02)


def _affine(s: float, rot: float, dx: float, dy: float, size) -> tuple:
    """PIL AFFINE coefficients (output -> input) for: scale s and rotate rot degrees about the centre, then shift."""
    w, h = size
    th = np.deg2rad(rot)
    c, sn = np.cos(th), np.sin(th)
    cx, cy = w / 2, h / 2
    a, b = c / s, sn / s
    x0, y0 = cx + dx, cy + dy                       # where the centre lands
    return (a, b, cx - a * x0 - b * y0, -b, a, cy + b * x0 - a * y0)


def _warp(img: "Image.Image", s: float, rot: float, dx: float, dy: float, size, resample=None) -> "Image.Image":
    return img.transform(size, Image.AFFINE, _affine(s, rot, dx, dy, size), resample or Image.BILINEAR)


def _corr(FC, FP, win, maxx: int, maxy: int):
    A = np.fft.fft2(FC * win)
    B = np.fft.fft2(FP * win)
    c = np.real(np.fft.ifft2(A * np.conj(B)))
    h, w = c.shape
    ys = np.r_[0:maxy + 1, h - maxy:h]
    xs = np.r_[0:maxx + 1, w - maxx:w]
    sub = c[np.ix_(ys, xs)]
    i = np.unravel_index(np.argmax(sub), sub.shape)
    dy, dx = int(ys[i[0]]), int(xs[i[1]])
    if dy > h // 2:
        dy -= h
    if dx > w // 2:
        dx -= w
    n = np.sqrt(np.sum(np.abs(FC * win) ** 2) * np.sum(np.abs(FP * win) ** 2)) + 1e-9
    return float(sub[i] / n), dx, dy


def _search(capture, plate, W, scales, rots, frac, centre=(0.0, 0.0)):
    full = capture.size
    size = (W, round(W * full[1] / full[0]))
    k = full[0] / W
    C = capture.convert("L").resize(size, Image.BILINEAR)
    P = plate.convert("L").resize(size, Image.BILINEAR)
    FC = _field(C)
    h, w = FC.shape
    win = np.outer(np.hanning(h) ** 0.3, np.hanning(w) ** 0.3)
    best = (-1.0, 1.0, 0.0, 0.0, 0.0)
    for s in scales:
        for r in rots:
            Pw = _warp(P, s, r, centre[0] / k, centre[1] / k, size)
            sc, dx, dy = _corr(FC, _field(Pw), win, int(w * frac), int(h * frac))
            if sc > best[0]:
                best = (sc, float(s), float(r), centre[0] + dx * k, centre[1] + dy * k)
    return best


def _coverage(est: Dict[str, Any], size) -> float:
    """Share of the capture frame the warped render covers (the rest would be empty after a realign)."""
    w, h = 320, round(320 * size[1] / size[0])
    k = size[0] / w
    ones = Image.new("L", (w, h), 255)
    m = _warp(ones, est["scale"], est["rotation"], est["dx"] / k, est["dy"] / k, (w, h), Image.NEAREST)
    return float((np.asarray(m) > 127).mean())


def describe(est: Dict[str, Any]) -> str:
    """Plain words for the page: how the RENDER differs from the capture."""
    if est.get("verdict") == "uncertain":
        return "could not be measured reliably (the edges barely match)"
    bits = []
    dx, dy = est["dx"], est["dy"]
    tol = MAX_SHIFT_FRACTION * est["width"]
    if abs(dy) > tol:
        bits.append(f"content {abs(dy)} px {'lower' if dy < 0 else 'higher'}")
    if abs(dx) > tol:
        bits.append(f"content {abs(dx)} px {'to the right' if dx < 0 else 'to the left'}")
    z = est["scale"] - 1
    if abs(z) > 0.005:
        bits.append(f"{abs(z) * 100:.0f}% zoomed {'out' if z > 0 else 'in'}")
    if abs(est["rotation"]) >= 0.5:
        bits.append(f"rotated {abs(est['rotation']):.1f}°")
    return ", ".join(bits) if bits else "no measurable change"


def measure(capture_path: Path, plate_path: Path) -> Optional[Dict[str, Any]]:
    """Measure how the plate's framing differs from the capture's. None if numpy/Pillow are missing."""
    if not _AVAILABLE:
        return None
    capture = Image.open(capture_path)
    capture.load()
    plate = Image.open(plate_path).convert("RGB")
    sc, s, r, dx, dy = _search(capture, plate, 320, np.arange(0.84, 1.22, 0.03), np.arange(-4, 4.01, 1.0), 0.3)
    sc, s, r, dx, dy = _search(capture, plate, 640, np.arange(s - 0.03, s + 0.031, 0.01),
                               np.arange(r - 1, r + 1.01, 0.25), 0.03, (dx, dy))
    w = capture.size[0]
    est = {"version": VERSION, "score": round(sc, 3), "scale": round(s, 3), "rotation": round(r, 2),
           "dx": int(round(dx)), "dy": int(round(dy)), "width": w, "height": capture.size[1]}
    est["coverage"] = round(_coverage(est, capture.size), 3)
    if sc < MIN_SCORE:
        verdict = "uncertain"
    elif (max(abs(dx), abs(dy)) <= MAX_SHIFT_FRACTION * w and abs(s - 1) <= MAX_ZOOM and abs(r) <= MAX_ROTATION):
        verdict = "aligned"
    else:
        verdict = "drifted"
    est["verdict"] = verdict
    est["can_realign"] = verdict == "drifted" and est["coverage"] >= MIN_REALIGN_COVERAGE
    est["summary"] = describe(est)
    return est


def realign(capture_path: Path, plate_path: Path, est: Dict[str, Any], out_path: Path) -> Dict[str, Any]:
    """Warp the plate onto the capture's framing and save it at the plate's own size. The few edge pixels
    the warped render does not cover are filled from the nearest covered pixels (only allowed when the gap
    is small: est["can_realign"])."""
    capture = Image.open(capture_path)
    plate = Image.open(plate_path).convert("RGB")
    size = plate.size
    k = size[0] / capture.size[0]                      # measured in capture pixels; the plate may be larger
    out = _warp(plate, est["scale"], est["rotation"], est["dx"] * k, est["dy"] * k, size, Image.BICUBIC)
    mask = _warp(Image.new("L", size, 255), est["scale"], est["rotation"], est["dx"] * k, est["dy"] * k, size, Image.NEAREST)
    a = np.asarray(out).copy()
    m = np.asarray(mask) > 127
    # fill the uncovered border with a mirror image of the covered pixels next to it (less visible than
    # repeating one row or column); only rows and columns that are fully covered count as covered
    rows = np.where(m.all(axis=1))[0]
    cols = np.where(m.all(axis=0))[0]
    if rows.size and cols.size:
        top, bot = rows[0] + 1, rows[-1] - 1            # step one pixel inside the soft warped edge
        left, right = cols[0] + 1, cols[-1] - 1
        H, W = a.shape[:2]
        if top > 0:
            n = min(top, bot - top)
            a[top - n:top] = a[top:top + n][::-1]
            a[:top - n] = a[top - n]
        if bot < H - 1:
            n = min(H - 1 - bot, bot - top)
            a[bot + 1:bot + 1 + n] = a[bot + 1 - n:bot + 1][::-1]
            a[bot + 1 + n:] = a[bot + n]
        if left > 0:
            n = min(left, right - left)
            a[:, left - n:left] = a[:, left:left + n][:, ::-1]
            a[:, :left - n] = a[:, left - n:left - n + 1]
        if right < W - 1:
            n = min(W - 1 - right, right - left)
            a[:, right + 1:right + 1 + n] = a[:, right + 1 - n:right + 1][:, ::-1]
            a[:, right + 1 + n:] = a[:, right + n:right + n + 1]
    Image.fromarray(a).save(out_path, "PNG")
    return {"filled_fraction": round(1 - float(m.mean()), 3)}
