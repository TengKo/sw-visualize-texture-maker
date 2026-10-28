"""Procedural, seamlessly tiling FDM (3D-print) layer-line height field.

Layer lines run horizontally (along U); the print's Z axis is the texture's V axis.
The height is in pixel units, so height_to_normal(h, 1.0) gives true geometric normals.
"""
import numpy as np
from scipy import ndimage


def _noise1d(rng, n, cutoff, rows):
    f = np.fft.rfftfreq(n) * n
    spec = (rng.standard_normal((rows, f.size)) + 1j * rng.standard_normal((rows, f.size))) * np.exp(-(f / cutoff) ** 2)
    spec[:, 0] = 0
    x = np.fft.irfft(spec, n)
    return x / (x.std(axis=1, keepdims=True) + 1e-12)


def _noise2d(rng, n, fx_scale, fy_scale):
    fy = np.fft.fftfreq(n)[:, None]
    fx = np.fft.fftfreq(n)[None, :]
    filt = np.exp(-((fx / fx_scale) ** 2 + (fy / fy_scale) ** 2))
    x = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((n, n))) * filt))
    return x / (x.std() + 1e-12)


def generate_fdm(size=2048, layers=64, seed=3, bead_shape=3.0, imperfections=1.0, bulge=0.22,
                 groove_soften=None, wobble_period=16):
    """Return a size x size height field (px units).

    bead_shape    2 = round beads ... 4 = flat faces with sharp grooves
    imperfections 0 = perfectly clean ... 1 = typical printer ... 2 = rough
    """
    if layers % wobble_period:
        wobble_period = next(p for p in (16, 8, 4, 2, 1) if layers % p == 0)
    rng = np.random.default_rng(seed)
    N, L = int(size), int(layers)
    period = N / L
    sc = period / 32.0                     # tuned at 32 px per layer
    imp = float(max(imperfections, 0.0))

    thick = 1 + 0.035 * imp * rng.standard_normal(L)
    thick = thick / thick.sum() * N
    starts = np.concatenate([[0.0], np.cumsum(thick)[:-1]])
    wave = (0.9 * _noise1d(rng, N, 6, L) + 0.35 * _noise1d(rng, N, 45, L)) * sc * imp
    bounds = starts[:, None] + wave                                   # (L, N): top edge of each layer per column

    amp = bulge * period * (1 + 0.06 * imp * rng.standard_normal((L, 1)))
    amp = amp * (1 + imp * (0.07 * _noise1d(rng, N, 4, L) + 0.04 * _noise1d(rng, N, 35, L)))
    amp = amp * (1 + 0.05 * imp * np.sin(2 * np.pi * np.arange(L) / wobble_period)[:, None])

    # extended edges: index j+1 holds layer j for j = -1 .. L+1 (wrap-around)
    bext = np.vstack([bounds[L - 1:L] - N, bounds, bounds[0:1] + N, bounds[1:2] + N])
    ys = (np.arange(N) + 0.5)[:, None]
    cols = np.arange(N)[None, :]
    idx = np.repeat((np.searchsorted(starts, ys[:, 0], side="right") - 1)[:, None], N, axis=1)
    for _ in range(2):                                                # waviness is << a layer, so 2 passes settle it
        idx = np.where(ys < bext[idx + 1, cols], idx - 1, idx)
        idx = np.where(ys >= bext[idx + 2, cols], idx + 1, idx)
        idx = np.clip(idx, -1, L)
    top = bext[idx + 1, cols]
    t = (ys - top) / (bext[idx + 2, cols] - top)
    k = float(np.clip(bead_shape, 1.5, 6.0))
    prof = np.clip(1 - np.abs(2 * np.clip(t, 0, 1) - 1) ** k, 0, 1) ** (1 / k)
    h = amp[idx % L, cols] * prof

    h = ndimage.gaussian_filter(h, groove_soften if groove_soften is not None else 1.3 * sc, mode="wrap")
    h = h + imp * (0.16 * _noise2d(rng, N, 0.004, 0.12) + 0.07 * _noise2d(rng, N, 0.18, 0.18)) * sc
    return h
