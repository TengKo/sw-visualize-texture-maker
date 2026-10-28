import struct
import zipfile

import numpy as np
import pytest
from PIL import Image

from texture_maker.engine import (auto_strength, build_svap, check_photo, generate_fdm, height_to_normal,
                                  normal_convention, process_photo, render_sphere, verify_svap, write_dds)
from texture_maker.engine.svap import make_material_xml, read_template_xml, safe_stem


def synthetic_photo(w=1400, h=1800, seed=0):
    """Blobby texture under a strong top-to-bottom lighting gradient."""
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(h)[:, None] ** 2 + np.fft.fftfreq(w)[None, :] ** 2
    tex = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((h, w))) * np.exp(-f / 0.002)))
    tex = (tex - tex.min()) / (tex.max() - tex.min())
    light = np.linspace(0.35, 1.0, h)[:, None]
    g = np.clip((0.25 + 0.5 * tex) * light, 0, 1)
    return Image.fromarray((np.dstack([g, g, g]) * 255).astype(np.uint8), "RGB")


def test_dds_header_matches_visualize_layout():
    rgb = np.zeros((4, 8, 3), np.uint8)
    rgb[..., 0] = 10; rgb[..., 1] = 20; rgb[..., 2] = 30
    d = write_dds(rgb)
    assert d[:4] == b"DDS " and len(d) == 128 + 4 * 8 * 4
    size, flags, height, width, pitch = struct.unpack("<IIIII", d[4:24])
    assert (size, flags, height, width, pitch) == (124, 0x100F, 4, 8, 32)
    pf = struct.unpack("<IIIIIIII", d[76:108])
    assert pf == (32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    assert struct.unpack("<I", d[108:112])[0] == 0x1000
    assert d[128:132] == bytes([30, 20, 10, 255])  # BGRA


def test_photo_pipeline_is_seamless_and_normalised():
    res = process_photo(synthetic_photo(), size=256)
    h = res.height
    assert h.shape == (256, 256)
    assert abs(h.mean()) < 1e-6 and abs(h.std() - 1) < 1e-6
    interior = np.abs(np.diff(h, axis=0)).mean()
    wrap = np.abs(h[0] - h[-1]).mean()
    assert wrap < interior * 1.6, (wrap, interior)
    # lighting gradient removed: top and bottom halves have similar mean
    assert abs(h[:128].mean() - h[128:].mean()) < 0.3


def test_small_photo_warns():
    assert check_photo(Image.new("RGB", (640, 480))) and not check_photo(Image.new("RGB", (1500, 1500)))


def test_normal_maps_are_directx():
    h = generate_fdm(256, 16, seed=1)
    assert normal_convention(height_to_normal(h, 1.0))[0] == "DirectX"
    res = process_photo(synthetic_photo(900, 900, 2), size=256)
    n = height_to_normal(res.height, auto_strength(res.height))
    assert normal_convention(n)[0] == "DirectX"


def test_fdm_tiles_seamlessly():
    h = generate_fdm(512, 32, seed=5)
    assert np.abs(h[:, 0] - h[:, -1]).mean() < np.abs(np.diff(h, axis=1)).mean() * 1.6
    assert np.abs(h[0] - h[-1]).mean() < np.abs(np.diff(h, axis=0)).mean() * 2.5


def test_template_edit_and_build_roundtrip(tmp_path):
    xml, guids = make_material_xml(read_template_xml(), "My <Test> & Co", "My_Test_normal", (0.2, 0.4, 0.6), 0.35, 7)
    assert 'Name="My &lt;Test&gt; &amp; Co"' in xml and "<TileS>7</TileS>" in xml
    assert '<BaseColor R="0.2" G="0.4" B="0.6" />' in xml and "<PbrRoughness>0.35</PbrRoughness>" in xml

    n = height_to_normal(generate_fdm(256, 16, seed=2), 1.0)
    out = tmp_path / "t.svap"
    build_svap(str(out), "Layer Test", (0.5, 0.5, 0.52), 0.4, 8, n)
    info = verify_svap(str(out))
    assert info["name"] == "Layer Test" and info["tile"] == "8" and info["normal_convention"] == "DirectX"
    assert info["dds"] == "256x256 RGBA"
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert sum(n.endswith(".thb.png") for n in names) == 2 and "Thumb.png" in names
        assert z.read("_rels/.rels")[:3] == b"\xef\xbb\xbf"           # UTF-8 BOM like Visualize
        assert z.read("Material.xml")[:5] == b"<?xml"                  # no BOM, CRLF kept
        assert b"\r\n" in z.read("Material.xml")


def test_sphere_preview_shape():
    img = render_sphere(np.full((64, 64, 3), (128, 128, 255), np.uint8), (0.5, 0.5, 0.5), 0.5, 1, res=64, ss=2)
    assert img.shape == (64, 64, 4) and img[0, 0, 3] == 0 and img[32, 32, 3] == 255


@pytest.mark.parametrize("name,stem", [("Gray Vertical Stipple", "Gray_Vertical_Stipple"), ("a/b:c*", "abc"), ("  ", "Appearance")])
def test_safe_stem(name, stem):
    assert safe_stem(name) == stem
