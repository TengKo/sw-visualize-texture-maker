"""Height field -> tangent-space normal map helpers.

Visualize expects DirectX-style normal maps (green channel points down); that is the default here.
"""
import numpy as np
from PIL import Image

# Default "bump depth" target: 99th-percentile tilt of a photo-derived map.
# Visualize's own library map (Mold-Tech style) sits around 0.53; coarse grains read well at ~0.62.
DEFAULT_TILT = 0.62


def _gradients(h):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gr = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    return gx, gr


def height_to_normal(h, strength=1.0, directx=True):
    """Seamless (wrap-around) normal map from a height field. Returns HxWx3 uint8."""
    gx, gr = _gradients(h)
    nx = -gx * strength
    ny = (-gr if directx else gr) * strength
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1.0)
    n = np.stack([nx * inv, ny * inv, inv], -1)
    return np.clip((n * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)


def auto_strength(h, tilt=DEFAULT_TILT):
    """Strength that makes the 99th-percentile gradient component tilt by `tilt`."""
    gx, gr = _gradients(h)
    p99 = np.percentile(np.abs(np.concatenate([gx.ravel(), gr.ravel()])), 99)
    t = float(np.clip(tilt, 0.05, 0.95))
    return (t / np.sqrt(1 - t * t)) / max(p99, 1e-9)


def resize_height(h, size):
    """Resample a height field to size x size (keeps it zero-mean / unit-std if it was)."""
    if h.shape[0] == size and h.shape[1] == size:
        return h
    img = Image.fromarray(h.astype(np.float32), mode="F").resize((size, size), Image.LANCZOS)
    return np.asarray(img, dtype=np.float64)


def flip_green(rgb):
    out = rgb.copy()
    out[..., 1] = 255 - out[..., 1]
    return out


def normal_convention(rgb):
    """Integrability (curl) test. Returns ('DirectX'|'OpenGL', residual_dx, residual_gl)."""
    n = rgb[..., :3].astype(float) / 255 * 2 - 1
    p = -n[..., 0] / n[..., 2]
    q = n[..., 1] / n[..., 2]
    d_row = lambda a: (np.roll(a, -1, 0) - np.roll(a, 1, 0)) / 2  # noqa: E731
    d_col = lambda a: (np.roll(a, -1, 1) - np.roll(a, 1, 1)) / 2  # noqa: E731
    r_gl = float(np.abs(d_row(p) - d_col(q)).mean())
    r_dx = float(np.abs(d_row(p) + d_col(q)).mean())
    return ("DirectX" if r_dx < r_gl else "OpenGL"), r_dx, r_gl


def tilt_stats(rgb):
    n = rgb[..., :3].astype(float) / 255 * 2 - 1
    t = np.sqrt(n[..., 0] ** 2 + n[..., 1] ** 2)
    return {k: float(np.percentile(t, k)) for k in (50, 90, 99)}
