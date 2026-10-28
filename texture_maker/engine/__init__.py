"""Texture engine: photo -> height map -> normal map -> .svap. No Qt imports in here."""

from .normal import height_to_normal, auto_strength, normal_convention, tilt_stats, resize_height
from .photo import load_image, check_photo, process_photo, PhotoResult, Cancelled
from .fdm import generate_fdm
from .preview import render_sphere
from .svap import build_svap, verify_svap, write_dds, builtin_template_path

__all__ = [
    "height_to_normal", "auto_strength", "normal_convention", "tilt_stats", "resize_height",
    "load_image", "check_photo", "process_photo", "PhotoResult", "Cancelled",
    "generate_fdm", "render_sphere",
    "build_svap", "verify_svap", "write_dds", "builtin_template_path",
]
