"""Write and check SOLIDWORKS Visualize appearance packages (.svap).

A .svap is a ZIP in Open Packaging Conventions layout:
  Material.xml                         the appearance (DsPbrMaterial) + one texture node
  Assets/<imageGuid>.dds               the normal map, uncompressed A8R8G8B8
  Thumb.png, Thumbnails/<matGuid>.thb.png   128x128 sphere preview (same image)
  Thumbnails/<texGuid>.thb.png         128x128 texture preview
  _rels/.rels, [Content_Types].xml, package/services/metadata/core-properties/<hex>.psmdcp
New appearances are made by copying a template Material.xml and changing only names, GUIDs,
colour, roughness, metallic and tiling.
"""
import io
import os
import re
import struct
import sys
import uuid
import zipfile

import numpy as np
from PIL import Image

from .normal import normal_convention, tilt_stats
from .preview import render_sphere


def builtin_template_path():
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "texture_maker", "engine", "template", "Material.xml")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "template", "Material.xml")


def write_dds(rgb):
    """Uncompressed A8R8G8B8 DDS, no mipmaps - the same header layout Visualize writes."""
    hgt, wid = rgb.shape[:2]
    hdr = struct.pack("<4sIIIIIII11I", b"DDS ", 124, 0x100F, hgt, wid, wid * 4, 0, 0, *([0] * 11))
    pf = struct.pack("<IIIIIIII", 32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    caps = struct.pack("<IIIII", 0x1000, 0, 0, 0, 0)
    bgra = np.dstack([rgb[..., 2], rgb[..., 1], rgb[..., 0], np.full(rgb.shape[:2], 255, np.uint8)])
    data = hdr + pf + caps + np.ascontiguousarray(bgra).tobytes()
    assert len(data) == 128 + wid * hgt * 4
    return data


def read_template_xml(path=None):
    path = path or builtin_template_path()
    if path.lower().endswith(".svap"):
        with zipfile.ZipFile(path) as z:
            return z.read("Material.xml").decode("utf-8")
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def _fmt(v):
    v = float(v)
    if v in (0.0, 1.0):
        return str(int(v))
    return f"{v:.6f}".rstrip("0").rstrip(".")


def _xml_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def make_material_xml(xml, name, tex_name, base_srgb, roughness, tile, metallic=None):
    mat = re.search(r'xsi:type="InventoryMaterialNode" Guid="([^"]+)" Name="([^"]*)"', xml)
    texs = re.findall(r'xsi:type="InventoryTextureNode" Guid="([^"]+)" Name="([^"]*)"', xml)
    img = re.findall(r'<UriImageHandle Guid="([^"]+)"', xml)
    if not (mat and len(texs) == 1 and len(img) == 1):
        raise ValueError("Template must contain one appearance with exactly one texture.")
    old_mat, old_tex, old_img = mat.group(1), texs[0][0], img[0]
    if not re.search(r"<ParameterName>normal</ParameterName>\s*<ParameterValue[^>]*/>\s*<TextureReferenceGuid>"
                     + re.escape(old_tex), xml):
        raise ValueError("Template's texture must be in the normal-map slot.")
    new = {k: str(uuid.uuid4()) for k in ("mat", "tex", "img")}
    xml = xml.replace(old_mat, new["mat"]).replace(old_tex, new["tex"]).replace(old_img, new["img"])
    xml = xml.replace(f'Guid="{new["mat"]}" Name="{mat.group(2)}"', f'Guid="{new["mat"]}" Name="{_xml_escape(name)}"')
    xml = xml.replace(f'Guid="{new["tex"]}" Name="{texs[0][1]}"', f'Guid="{new["tex"]}" Name="{_xml_escape(tex_name)}"')
    xml = re.sub(r'(<UriImageHandle Guid="[^"]+" Uri=")[^"]*"', lambda m: f'{m.group(1)}file:///C:/Textures/{tex_name}.png"', xml)

    r, g, b = (_fmt(c) for c in base_srgb)
    subs = [
        (r'<BaseColor R="[^"]*" G="[^"]*" B="[^"]*" />', f'<BaseColor R="{r}" G="{g}" B="{b}" />'),
        (r'(<ParameterName>albedo</ParameterName>\s*<ParameterValue xsi:type="Color3F") R="[^"]*" G="[^"]*" B="[^"]*"',
         rf'\1 R="{r}" G="{g}" B="{b}"'),
        (r"<PbrRoughness>[^<]*</PbrRoughness>", f"<PbrRoughness>{_fmt(roughness)}</PbrRoughness>"),
        (r"<PbrGlossiness>[^<]*</PbrGlossiness>", f"<PbrGlossiness>{_fmt(1 - roughness)}</PbrGlossiness>"),
        (r'(<ParameterName>roughness</ParameterName>\s*<ParameterValue xsi:type="xsd:float">)[^<]*', rf"\g<1>{_fmt(roughness)}"),
    ]
    for pat, rep in subs:
        xml, n = re.subn(pat, rep, xml, count=1)
        if n != 1:
            raise ValueError(f"Template is missing an expected field ({pat[:40]}...).")
    if metallic is not None:
        xml = re.sub(r"<PbrMetallic>[^<]*</PbrMetallic>", f"<PbrMetallic>{_fmt(metallic)}</PbrMetallic>", xml, count=1)
        xml = re.sub(r'(<ParameterName>metallic</ParameterName>\s*<ParameterValue xsi:type="xsd:float">)[^<]*',
                     rf"\g<1>{_fmt(metallic)}", xml, count=1)

    def _tile(m):
        blk = re.sub(r"<TileS>[^<]*</TileS>", f"<TileS>{_fmt(tile)}</TileS>", m.group(0))
        return re.sub(r"<TileT>[^<]*</TileT>", f"<TileT>{_fmt(tile)}</TileT>", blk)

    xml, n = re.subn(r"<TextureOperationsList>.*?</TextureOperationsList>", _tile, xml, count=1, flags=re.S)
    if n != 1:
        raise ValueError("Template has no TextureOperationsList for the normal map.")
    xml = xml.replace("<IsPredefined>true</IsPredefined>", "<IsPredefined>false</IsPredefined>")
    return xml, new


def _png(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def safe_stem(name):
    s = re.sub(r"[^\w\- ]+", "", name, flags=re.UNICODE).strip()
    return re.sub(r"\s+", "_", s) or "Appearance"


def build_svap(out_path, name, base_srgb, roughness, tile, normal_rgb, template=None,
               metallic=None, thumb_tile=2.0, tex_name=None):
    """Write a .svap. base_srgb: (r, g, b) in 0-1. normal_rgb: HxWx3 uint8, DirectX convention."""
    normal_rgb = np.ascontiguousarray(normal_rgb[..., :3]).astype(np.uint8)
    w = normal_rgb.shape[1]
    tex_name = tex_name or safe_stem(name) + "_normal"
    xml, g = make_material_xml(read_template_xml(template), name, tex_name, base_srgb, roughness, tile, metallic)

    small = normal_rgb if w <= 512 else np.asarray(Image.fromarray(normal_rgb, "RGB").resize((512, 512), Image.LANCZOS))
    thumb = Image.fromarray(render_sphere(small, base_srgb, roughness, thumb_tile, res=128, ss=3), "RGBA")
    mat_thumb = _png(thumb)
    tex_thumb = _png(Image.fromarray(normal_rgb, "RGB").convert("RGBA").resize((128, 128), Image.LANCZOS))

    bom = "\ufeff"
    rid = lambda: "R" + uuid.uuid4().hex[:16]  # noqa: E731
    psmdcp = uuid.uuid4().hex
    content_types = (
        bom + '<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="text/xml" /><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />'
        '<Default Extension="png" ContentType="application/octet-stream" /><Default Extension="dds" ContentType="application/octet-stream" />'
        '<Default Extension="psmdcp" ContentType="application/vnd.openxmlformats-package.core-properties+xml" /></Types>')
    rels = (
        bom + '<?xml version="1.0" encoding="utf-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Type="Material" Target="/Material.xml" Id="{rid()}" />'
        f'<Relationship Type="Thumbnail" Target="/Thumb.png" Id="{rid()}" />'
        f'<Relationship Type="Asset" Target="/Assets/{g["img"]}.dds" Id="{rid()}" />'
        f'<Relationship Type="AssetThumbnail" Target="/Thumbnails/{g["mat"]}.thb.png" Id="{rid()}" />'
        f'<Relationship Type="AssetThumbnail" Target="/Thumbnails/{g["tex"]}.thb.png" Id="{rid()}" />'
        '<Relationship Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        f'Target="/package/services/metadata/core-properties/{psmdcp}.psmdcp" Id="{rid()}" /></Relationships>')
    core = (
        bom + '<?xml version="1.0" encoding="utf-8"?><coreProperties xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://schemas.openxmlformats.org/package/2006/metadata/core-properties">'
        f'<version>2011.0</version><dc:description>Bunkspeed Material File</dc:description><dc:title>{_xml_escape(name)}.svap</dc:title></coreProperties>')

    tmp = out_path + ".part"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Material.xml", xml.encode("utf-8"))
        z.writestr("_rels/.rels", rels.encode("utf-8"))
        z.writestr("Thumb.png", mat_thumb)
        z.writestr(f"Assets/{g['img']}.dds", write_dds(normal_rgb))
        z.writestr(f"Thumbnails/{g['mat']}.thb.png", mat_thumb)
        z.writestr(f"Thumbnails/{g['tex']}.thb.png", tex_thumb)
        z.writestr(f"package/services/metadata/core-properties/{psmdcp}.psmdcp", core.encode("utf-8"))
        z.writestr("[Content_Types].xml", content_types.encode("utf-8"))
    os.replace(tmp, out_path)
    return thumb


def verify_svap(path):
    """Structural checks. Returns a dict of key settings; raises AssertionError on problems."""
    import xml.dom.minidom as minidom
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        x = z.read("Material.xml").decode("utf-8")
        for n in names:
            if n.endswith((".xml", ".rels", ".psmdcp")):
                minidom.parseString(z.read(n))
        rels = z.read("_rels/.rels").decode("utf-8-sig")
        for tgt in re.findall(r'Target="/([^"]+)"', rels):
            assert tgt in names, f"missing part {tgt}"
        mat = re.search(r'InventoryMaterialNode" Guid="([^"]+)" Name="([^"]*)"', x)
        tex = re.search(r'InventoryTextureNode" Guid="([^"]+)" Name="([^"]*)"', x)
        img = re.search(r'<UriImageHandle Guid="([^"]+)"', x).group(1)
        assert f"<TextureReferenceGuid>{tex.group(1)}</TextureReferenceGuid>" in x
        assert f"<guid>{tex.group(1)}</guid>" in x
        for part in (f"Assets/{img}.dds", f"Thumbnails/{mat.group(1)}.thb.png", f"Thumbnails/{tex.group(1)}.thb.png", "Thumb.png"):
            assert part in names, f"missing {part}"
        dds = Image.open(io.BytesIO(z.read(f"Assets/{img}.dds")))
        nrm = np.asarray(dds.convert("RGB"))
    conv, rdx, rgl = normal_convention(nrm)
    tiles = re.search(r"<TextureOperationsList>.*?<TileS>([^<]+)</TileS>", x, re.S).group(1)
    ts = tilt_stats(nrm)
    return {
        "name": mat.group(2), "texture": tex.group(2), "dds": f"{dds.size[0]}x{dds.size[1]} {dds.mode}",
        "base_color": re.search(r"<BaseColor[^>]+>", x).group(0),
        "roughness": re.search(r"<PbrRoughness>([^<]+)", x).group(1),
        "metallic": re.search(r"<PbrMetallic>([^<]+)", x).group(1),
        "tile": tiles, "normal_convention": conv, "convention_residuals": (round(rdx, 4), round(rgl, 4)),
        "tilt_p50_p99": (round(ts[50], 3), round(ts[99], 3)),
    }
