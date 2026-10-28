"""Photo of a textured surface -> seamless height field (+ suggested base colour).

Steps (tuned on real photos, verified in Visualize):
  1. grayscale -> linear light; divide out the lighting gradient (large Gaussian)
  2. equalise local contrast so dark and bright areas bump equally
  3. square crop with a margin, cross-faded over the opposite edges -> tiles seamlessly
     without smearing detail (Poisson / "periodic component" smoothing flattens the seam rows)
  4. resample to the output size, light denoise, height = brightness
Normals are made from the height separately so bump depth can change instantly.
"""
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage

MIN_GOOD_SIDE = 1024
REF_SIDE = 1720.0          # the sigmas below were tuned on a photo this size
MAX_WORK_SIDE = 2600       # bigger photos are downscaled first (speed; no visible loss)


class Cancelled(Exception):
    pass


@dataclass
class PhotoResult:
    height: np.ndarray                      # size x size, zero mean, unit std, tiles seamlessly
    base_srgb: tuple                        # suggested colour (median of the photo), 0-1
    source_size: tuple                      # (w, h) of the original photo
    crop: Image.Image                       # square RGB crop used (for side-by-side views / colour picking)
    warnings: list = field(default_factory=list)


def load_image(path):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img.convert("RGB")


def check_photo(img):
    """Return a list of human-readable warnings (empty = fine)."""
    w, h = img.size
    out = []
    if min(w, h) < MIN_GOOD_SIDE:
        out.append(f"This photo is small ({w} × {h} px). The texture may look soft. "
                   f"{MIN_GOOD_SIDE} px or more on the short side works best.")
    return out


def _overlap_wrap(arr, n, b, axis):
    arr = np.moveaxis(arr, axis, 0)
    out = arr[:n].copy()
    t = (np.arange(b) + 0.5) / b
    w = (t * t * (3 - 2 * t)).reshape(-1, *([1] * (arr.ndim - 1)))
    out[:b] = (w * arr[:b] + (1 - w) * arr[n:n + b]) / np.sqrt(w ** 2 + (1 - w) ** 2)
    return np.moveaxis(out, 0, axis)


def process_photo(img, size=2048, seam_band=120, progress=None, cancel=None):
    """img: PIL RGB image. progress(step_index, message) is called before each step (0..2).
    cancel(): return True to abort (raises Cancelled)."""
    def step(i, msg):
        if cancel and cancel():
            raise Cancelled()
        if progress:
            progress(i, msg)

    source_size = img.size
    warnings = check_photo(img)
    work = img
    if min(img.size) > MAX_WORK_SIDE:
        s = MAX_WORK_SIDE / min(img.size)
        work = img.resize((round(img.size[0] * s), round(img.size[1] * s)), Image.LANCZOS)
    W, H = work.size
    k = min(W, H) / REF_SIDE  # scale the tuned sigmas to this photo

    step(0, "Evening out the lighting")
    g = np.asarray(work.convert("L"), dtype=np.float64) / 255.0
    lin = np.where(g <= 0.04045, g / 12.92, ((g + 0.055) / 1.055) ** 2.4) + 1e-4
    flat = np.log(lin / ndimage.gaussian_filter(lin, max(60 * k, 4), mode="reflect"))
    hp = flat - ndimage.gaussian_filter(flat, max(25 * k, 2), mode="reflect")
    hp = hp / (np.sqrt(ndimage.gaussian_filter(hp ** 2, max(40 * k, 3), mode="reflect")) + 1e-6)

    step(1, "Making it tile seamlessly")
    band = int(max(8, min(seam_band * k, min(W, H) // 6)))
    side = min(W, H) - band
    top = (H - side - band) // 2
    left = (W - side - band) // 2
    strip = hp[top:top + side + band, left:left + side + band]
    crop_h = _overlap_wrap(_overlap_wrap(strip, side, band, 0), side, band, 1)
    crop_rgb = work.crop((left, top, left + side, top + side))

    step(2, "Building the height map")
    h = np.asarray(Image.fromarray(crop_h.astype(np.float32), mode="F").resize((size, size), Image.LANCZOS),
                   dtype=np.float64)
    h = ndimage.gaussian_filter(h, 0.8 if size >= 2048 else 0.55, mode="wrap")
    lo, hi = np.percentile(h, [0.5, 99.5])
    h = np.clip(h, lo, hi)
    h = (h - h.mean()) / (h.std() + 1e-12)

    if cancel and cancel():
        raise Cancelled()
    med = np.median(np.asarray(crop_rgb, dtype=np.float64).reshape(-1, 3), axis=0) / 255.0
    return PhotoResult(height=h, base_srgb=tuple(float(c) for c in med), source_size=source_size,
                       crop=crop_rgb, warnings=warnings)
