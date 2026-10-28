"""Quick lit-sphere preview of a normal map (CPU, numpy). Approximate - not Visualize's renderer."""
import numpy as np

DEFAULT_LIGHT = (-0.5, 0.6, 0.62)


def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)


def light_from_drag(dx, dy):
    """Map a normalised drag position (-1..1, -1..1; y down) to a light direction."""
    x, y = float(np.clip(dx, -0.95, 0.95)), float(np.clip(-dy, -0.95, 0.95))
    r2 = x * x + y * y
    if r2 > 0.9:
        s = np.sqrt(0.9 / r2)
        x, y, r2 = x * s, y * s, 0.9
    return (x, y, float(np.sqrt(1 - r2)))


def render_sphere(nrm_rgb, base_srgb, roughness, tile, res=128, ss=3, light=DEFAULT_LIGHT, directx=True):
    """Return a res x res RGBA uint8 image of a sphere wearing the normal map (transparent background)."""
    R = res * ss
    y, x = np.mgrid[0:R, 0:R]
    u = (x + 0.5) / R * 2 - 1
    v = 1 - (y + 0.5) / R * 2
    rad = 0.97
    mask = u * u + v * v <= rad * rad
    uu, vv = u / rad, v / rad
    z = np.sqrt(np.clip(1 - uu * uu - vv * vv, 0, 1))
    N = np.stack([uu, vv, z], -1)

    su = (np.arctan2(uu, z) / np.pi * 0.5 + 0.5) * tile
    sv = (np.arcsin(np.clip(vv, -1, 1)) / np.pi + 0.5) * tile
    H, W = nrm_rgb.shape[:2]
    px = (su * W).astype(np.int64) % W
    py = ((1 - sv % 1) * H).astype(np.int64) % H
    tn = nrm_rgb[py, px, :3].astype(np.float64) / 255 * 2 - 1
    if directx:
        tn[..., 1] *= -1

    T = np.stack([z, np.zeros_like(z), -uu], -1)
    T /= np.linalg.norm(T, axis=-1, keepdims=True) + 1e-9
    B = np.cross(N, T)
    Np = T * tn[..., :1] + B * tn[..., 1:2] + N * tn[..., 2:3]
    Np /= np.linalg.norm(Np, axis=-1, keepdims=True) + 1e-9

    V = np.array([0.0, 0.0, 1.0])
    base = srgb_to_lin(np.array(base_srgb, dtype=np.float64))
    rough = float(np.clip(roughness, 0.03, 1.0))
    shininess = min(2 / rough**4 - 2, 600)
    spec_k = 0.04 * (shininess + 8) / (8 * np.pi)
    key = np.array(light, dtype=np.float64)
    key /= np.linalg.norm(key)
    fill = np.array([-key[0] * 0.8, -0.2, 0.55])
    fill /= np.linalg.norm(fill)
    col = np.zeros(N.shape)
    for L, inten in ((key, 2.4), (fill, 0.55)):
        ndl = np.clip(Np @ L, 0, None)[..., None]
        Hh = (L + V) / np.linalg.norm(L + V)
        spec = (np.clip(Np @ Hh, 0, None) ** shininess * spec_k)[..., None]
        col += inten * (base * ndl + spec * ndl)
    col += base * 0.08 + 0.02 * (Np[..., 1:2] * 0.5 + 0.5)
    rgb = np.clip(lin_to_srgb(col), 0, 1)
    rgba = np.dstack([rgb * 255, mask * 255]).astype(np.float32)
    if ss > 1:
        rgba = rgba.reshape(res, ss, res, ss, 4).mean(axis=(1, 3))
    return np.clip(rgba + 0.5, 0, 255).astype(np.uint8)
