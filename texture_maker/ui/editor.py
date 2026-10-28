"""Preview & adjust (photo) and 3D print preset pages."""
import os
import random
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from ..engine import auto_strength, generate_fdm, height_to_normal, render_sphere, resize_height
from ..engine.preview import DEFAULT_LIGHT, light_from_drag
from . import icons
from .pages import footer_bar
from .theme import C
from .widgets import (ColorField, PreviewLabel, Segmented, SliderRow, field, hbox, label, numpy_to_pixmap,
                      pil_to_pixmap, set_elided, srgb_to_hex, vbox)

PREVIEW_RES = 480


def _render(nrm, color, rough, tile, light, ss):
    return render_sphere(nrm, color, rough, tile, res=PREVIEW_RES, ss=ss, light=light)


def _size_hint(size):
    return "Keeps fine detail · about 7–12 MB file" if size >= 2048 else "Smaller file · about 2–3 MB, softer detail"


class _Base(QWidget):
    """Shared layout: preview column on the left, settings panel on the right, footer below."""
    generateRequested = Signal(dict)
    saveBumpRequested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.light = DEFAULT_LIGHT
        self.sphere_pm = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        body = QHBoxLayout()
        body.setSpacing(0)
        root.addLayout(body, 1)

        self.preview_col = QVBoxLayout()
        self.preview_col.setContentsMargins(24, 20, 24, 20)
        self.preview_col.setSpacing(14)
        pc = QWidget()
        pc.setObjectName("Transparent")
        pc.setLayout(self.preview_col)
        body.addWidget(pc, 1)

        self.stage = QFrame()
        self.stage.setObjectName("Stage")
        self.stage_lay = QVBoxLayout(self.stage)
        self.stage_lay.setContentsMargins(20, 20, 20, 14)
        self.stage_lay.setSpacing(10)
        self.sphere_view = PreviewLabel(draggable=True)
        self.sphere_view.setToolTip("Drag to move the light")
        self.sphere_view.dragged.connect(self._drag)
        self.sphere_view.released.connect(lambda: self.request_render(fast=False))
        self.busy = label("Updating preview…", "Busy")
        self.busy.setVisible(False)

        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setFixedWidth(392)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.form = QWidget()
        self.form.setObjectName("Transparent")
        self.form_lay = QVBoxLayout(self.form)
        self.form_lay.setContentsMargins(24, 22, 24, 22)
        self.form_lay.setSpacing(18)
        scroll.setWidget(self.form)
        pl.addWidget(scroll)
        body.addWidget(panel)

        self.out_label = label("", "Mono")
        self.save_bump = QPushButton("Save bump map only…")
        self.save_bump.clicked.connect(lambda: self.saveBumpRequested.emit(self.params()))
        self.generate = QPushButton("Generate .svap")
        self.generate.setObjectName("Primary")
        self.generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate.clicked.connect(lambda: self.generateRequested.emit(self.params()))
        root.addWidget(footer_bar(self.out_label, "stretch", self.save_bump, self.generate))

        self.render_job = None  # set by subclass (LatestJob)

    # common controls -----------------------------------------------------------------
    def _finish_controls(self, options, default_rough):
        self.finish = Segmented(options, value=default_rough)
        self.rough = SliderRow(0.0, 1.0, default_rough, inline_label="Roughness")
        self.finish.changed.connect(lambda v: (self.rough.set_value(v), self.request_render()))
        self.rough.changed.connect(self._rough_changed)
        return field("Finish", self.finish, self.rough, spacing=10)

    def _rough_changed(self, v):
        self.finish.set_value(v) if v in self.finish.values else self.finish.clear()
        self.request_render()

    def _size_repeat_controls(self, default_tile):
        self.size = Segmented([(1024, "1024 px"), (2048, "2048 px")], value=2048)
        self.size_hint = label(_size_hint(2048), "Hint")
        self.size.changed.connect(lambda v: self.size_hint.setText(_size_hint(v)))
        self.tile = QSpinBox()
        self.tile.setRange(1, 200)
        self.tile.setValue(default_tile)
        self.tile.setSuffix("×")
        self.tile.setFixedWidth(96)
        self.tile.setAccessibleName("Repeat across surface")
        rep = QWidget()
        rep.setObjectName("Transparent")
        rl = QHBoxLayout(rep)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(label("Repeat across surface", "FieldLabel"))
        rl.addStretch(1)
        rl.addWidget(self.tile)
        return field("Texture size", self.size, hint=self.size_hint), rep

    def set_output_dir(self, d):
        set_elided(self.out_label, d, 460)

    def set_busy(self, on):
        self.busy.setVisible(on)

    def set_generating(self, on):
        self.generate.setEnabled(not on)
        self.save_bump.setEnabled(not on)
        self.generate.setText("Generating…" if on else "Generate .svap")

    def _drag(self, nx, ny):
        self.light = light_from_drag(nx, ny)
        self.request_render(fast=True)

    def _show_sphere(self, rgba):
        self.sphere_pm = numpy_to_pixmap(rgba)
        self.sphere_view.set_pixmap(self.sphere_pm)


# ======================================================================================
class EditorPage(_Base):
    replaceRequested = Signal()
    reprocessRequested = Signal(int)
    pickColorRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from .workers import LatestJob
        self.result = None
        self.photo_path = ""
        self.h_prev = None
        self.n_prev = None

        # --- preview column
        self.view = Segmented([("sphere", "Sphere"), ("bump", "Bump map"), ("photo", "Photo vs result")], value="sphere")
        self.view.changed.connect(self._switch_view)
        self.thumb = QLabel()
        self.thumb.setFixedSize(36, 36)
        self.fname = label("", "MonoMuted")
        replace = QPushButton("Replace…")
        replace.clicked.connect(self.replaceRequested.emit)
        top = hbox(self.view, "stretch", self.thumb, self.fname, replace, spacing=10)
        self.preview_col.addLayout(top)

        self.views = QStackedWidget()
        self.views.setObjectName("Transparent")
        self.bump_view = PreviewLabel()
        photo_w = QWidget()
        photo_w.setObjectName("Transparent")
        pw = QHBoxLayout(photo_w)
        pw.setSpacing(24)
        self.cmp_photo = PreviewLabel()
        self.cmp_result = PreviewLabel()
        self.cmp_photo.max_side = self.cmp_result.max_side = 360
        pw.addWidget(vbox(self.cmp_photo, self._cap("Your photo"), spacing=6), 1)
        pw.addWidget(vbox(self.cmp_result, self._cap("Result"), spacing=6), 1)
        self.views.addWidget(self.sphere_view)
        self.views.addWidget(self.bump_view)
        self.views.addWidget(photo_w)
        self.stage_lay.addWidget(self.views, 1)
        self.caption = label("Drag on the sphere to move the light", "Hint")
        self.stage_lay.addLayout(hbox(self.caption, "stretch", self.busy))
        self.preview_col.addWidget(self.stage, 1)
        self.preview_col.addWidget(label("Preview is approximate. The final look depends on your Visualize scene lighting.", "Hint"))

        # --- settings panel
        f = self.form_lay
        self.name = QLineEdit()
        self.name.setAccessibleName("Appearance name")
        f.addWidget(field("Name", self.name))
        self.color = ColorField()
        self.color.changed.connect(lambda _c: self.request_render())
        pick = QPushButton("  Pick from photo")
        pick.setIcon(icons.icon("eyedropper", C["text"], 16))
        pick.clicked.connect(self.pickColorRequested.emit)
        crow = QWidget()
        crow.setObjectName("Transparent")
        cl = QHBoxLayout(crow)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        cl.addWidget(self.color, 1)
        cl.addWidget(pick)
        f.addWidget(field("Color", crow, hint="Starts as the photo's middle tone."))
        f.addWidget(self._finish_controls([(0.7, "Matte"), (0.5, "Satin"), (0.25, "Gloss")], 0.5))
        self.bump = SliderRow(0.25, 2.0, 1.0, step=0.05, fmt="{:.2f}×", captions=("Subtle", "Deep"))
        self.bump.changed.connect(lambda _v: self.update_normal())
        f.addWidget(field("Bump depth", self.bump))
        size_w, rep_w = self._size_repeat_controls(5)
        f.addWidget(size_w)
        f.addWidget(rep_w)

        self.adv_btn = QPushButton("Advanced  ▸")
        self.adv_btn.setObjectName("Disclosure")
        self.adv_btn.setCheckable(True)
        self.adv = QWidget()
        self.adv.setObjectName("Transparent")
        al = QVBoxLayout(self.adv)
        al.setContentsMargins(0, 4, 0, 0)
        al.setSpacing(14)
        self.seam = QComboBox()
        for text, val in (("Narrow (60 px)", 60), ("Normal (120 px)", 120), ("Wide (200 px)", 200)):
            self.seam.addItem(text, val)
        self.seam.setCurrentIndex(1)
        self.seam.activated.connect(lambda _i: self.reprocessRequested.emit(self.seam.currentData()))
        al.addWidget(field("Seam blend", self.seam, hint="How much of the photo's edge is blended so the texture tiles. "
                                                          "Changing it re-processes the photo."))
        self.png_style = Segmented([("dx", "DirectX (Visualize)"), ("gl", "OpenGL")], value="dx")
        al.addWidget(field("Bump map PNG style", self.png_style,
                           hint="The .svap always uses DirectX. Pick OpenGL only for a PNG going to other apps."))
        self.adv.setVisible(False)
        self.adv_btn.toggled.connect(self._toggle_adv)
        f.addWidget(self.adv_btn)
        f.addWidget(self.adv)
        self.save_png = QCheckBox("Also save the bump map as PNG")
        self.save_png.setChecked(True)
        f.addWidget(self.save_png)
        f.addStretch(1)

        self.render_job = LatestJob(_render, parent=self)
        self.render_job.result.connect(self._rendered)
        self.render_job.busy.connect(self.set_busy)

    @staticmethod
    def _cap(text):
        c = label(text, "Hint")
        c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return c

    def _toggle_adv(self, on):
        self.adv.setVisible(on)
        self.adv_btn.setText("Advanced  ▾" if on else "Advanced  ▸")

    def _switch_view(self, v):
        self.views.setCurrentIndex({"sphere": 0, "bump": 1, "photo": 2}[v])
        self.caption.setText("Drag on the sphere to move the light" if v == "sphere" else
                             "The bump map Visualize will use (tiles seamlessly)" if v == "bump" else
                             "Same area of your photo, next to the result")

    # data ----------------------------------------------------------------------------
    def load(self, result, photo_path, params=None):
        self.result = result
        self.photo_path = photo_path
        self.h_prev = resize_height(result.height, 512)
        self.base_prev = auto_strength(self.h_prev)
        crop_pm = pil_to_pixmap(result.crop.resize((720, 720)))
        self.cmp_photo.set_pixmap(crop_pm)
        th = pil_to_pixmap(result.crop.resize((72, 72)))
        th.setDevicePixelRatio(2.0)
        self.thumb.setPixmap(th)
        self.fname.setText(os.path.basename(photo_path))
        if params:
            self.set_params(params)
        else:
            stem = os.path.splitext(os.path.basename(photo_path))[0]
            words = [w for w in re.split(r"[\s_\-.]+", stem) if w]
            self.name.setText(" ".join(w[:1].upper() + w[1:] for w in words) or "Photo Texture")
            self.color.set_color(result.base_srgb)
        self.update_normal()

    def update_normal(self):
        if self.h_prev is None:
            return
        self.n_prev = height_to_normal(self.h_prev, self.bump.value() * self.base_prev)
        self.bump_view.set_pixmap(numpy_to_pixmap(self.n_prev))
        self.request_render()

    def request_render(self, fast=False):
        if self.n_prev is None:
            return
        self.render_job.request(nrm=self.n_prev, color=self.color.color(), rough=self.rough.value(), tile=2.0,
                                light=self.light, ss=1 if fast else 2)

    def _rendered(self, rgba):
        self._show_sphere(rgba)
        self.cmp_result.set_pixmap(self.sphere_pm)

    def params(self):
        return {"name": self.name.text().strip() or "Photo Texture", "color": list(self.color.color()),
                "roughness": self.rough.value(), "bump": self.bump.value(), "size": self.size.value(),
                "tile": self.tile.value(), "save_png": self.save_png.isChecked(), "png_style": self.png_style.value(),
                "seam_band": self.seam.currentData()}

    def set_params(self, p):
        self.name.setText(p.get("name", ""))
        if p.get("color"):
            self.color.set_color(tuple(p["color"]))
        self.rough.set_value(p.get("roughness", 0.5))
        self._rough_changed(self.rough.value())
        self.bump.set_value(p.get("bump", 1.0))
        self.size.set_value(p.get("size", 2048), emit=True)
        self.tile.setValue(int(p.get("tile", 5)))
        self.save_png.setChecked(bool(p.get("save_png", True)))
        self.png_style.set_value(p.get("png_style", "dx"))
        i = self.seam.findData(p.get("seam_band", 120))
        self.seam.setCurrentIndex(i if i >= 0 else 1)


# ======================================================================================
QUICK_COLORS = [("Black", "#1E1E1E"), ("White", "#EDEDED"), ("Gray", "#8C8C8E"), ("Red", "#C23B32"),
                ("Blue", "#2F5DA8"), ("Green", "#3E8E4F"), ("Yellow", "#E3B634"), ("Orange", "#E07A2E")]


def _fdm_normal(size, layers, seed, bead, imp):
    return height_to_normal(generate_fdm(size, layers, seed, bead, imp), 1.0)


class PresetPage(_Base):
    def __init__(self, parent=None):
        super().__init__(parent)
        from .workers import LatestJob
        self.seed = 3
        self.n_prev = None
        self._activated = False

        self.stage_lay.addWidget(self.sphere_view, 1)
        self.stage_lay.addLayout(hbox(label("Drag on the sphere to move the light", "Hint"), "stretch", self.busy))
        self.preview_col.addWidget(self.stage, 1)
        self.preview_col.addWidget(label("Layer lines run horizontally. If they come out vertical on your part, "
                                         "rotate the texture 90° in Visualize.", "Hint", wrap=True))

        f = self.form_lay
        self.name = QLineEdit("3D Print PLA Layer Lines")
        self.name.setAccessibleName("Appearance name")
        f.addWidget(field("Name", self.name))
        self.color = ColorField((140 / 255, 140 / 255, 142 / 255))
        self.color.changed.connect(self._color_typed)
        dots = QWidget()
        dots.setObjectName("Transparent")
        dl = QHBoxLayout(dots)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(6)
        self.dot_group = QButtonGroup(self)
        self.dot_group.setExclusive(True)
        for nm, hx in QUICK_COLORS:
            b = QPushButton()
            b.setObjectName("Dot")
            b.setCheckable(True)
            b.setToolTip(nm)
            b.setAccessibleName(nm)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"QPushButton#Dot {{ background: {hx}; border: 1px solid #4A5058; }}"
                            f"QPushButton#Dot:checked {{ border: 3px solid {C['accent']}; }}")
            b.clicked.connect(lambda _=False, hx=hx: self._dot(hx))
            self.dot_group.addButton(b)
            dl.addWidget(b)
        dl.addStretch(1)
        f.addWidget(field("Filament color", self.color, dots))
        self._sync_dots()
        f.addWidget(self._finish_controls([(0.6, "Matte"), (0.4, "Satin"), (0.18, "Silk")], 0.4))

        self.layers = Segmented([(32, "32"), (64, "64"), (96, "96")], value=64)
        self.layers_hint = label("", "Hint", wrap=True)
        self.layers.changed.connect(lambda _v: (self._layers_hint(), self.request_geometry()))
        f.addWidget(field("Layers per tile", self.layers, hint=self.layers_hint))
        self._layers_hint()
        self.bead = SliderRow(2.0, 4.0, 3.0, step=0.1, fmt="{:.1f}", captions=("Round", "Flat"))
        self.bead.changed.connect(lambda _v: self.request_geometry())
        f.addWidget(field("Bead shape", self.bead))
        self.imp = SliderRow(0.0, 2.0, 1.0, step=0.05, fmt="{:.2f}", captions=("Clean", "Rough"))
        self.imp.changed.connect(lambda _v: self.request_geometry())
        f.addWidget(field("Imperfections", self.imp, hint="Uneven layers, wavy edges and the faint banding real printers leave."))
        shuffle = QPushButton("  Shuffle pattern")
        shuffle.setIcon(icons.icon("shuffle", C["text"], 16))
        shuffle.clicked.connect(self._shuffle)
        f.addWidget(vbox(shuffle, label("Same settings, new random layers.", "Hint"), spacing=6))
        size_w, rep_w = self._size_repeat_controls(8)
        f.addWidget(size_w)
        f.addWidget(rep_w)
        f.addStretch(1)

        self.geom_job = LatestJob(_fdm_normal, delay_ms=120, parent=self)
        self.geom_job.result.connect(self._geometry)
        self.geom_job.busy.connect(self.set_busy)
        self.render_job = LatestJob(_render, parent=self)
        self.render_job.result.connect(self._show_sphere)

    def _layers_hint(self):
        n = self.layers.value()
        self.layers_hint.setText(f"One tile = {n} layers ≈ {n * 0.2:.1f} mm at 0.2 mm layer height.")

    def _dot(self, hx):
        from .widgets import hex_to_srgb
        self.color.set_color(hex_to_srgb(hx))
        self.request_render()

    def _color_typed(self, _c):
        self._sync_dots()
        self.request_render()

    def _sync_dots(self):
        hx = srgb_to_hex(self.color.color())
        self.dot_group.setExclusive(False)
        for b, (_nm, qh) in zip(self.dot_group.buttons(), QUICK_COLORS):
            b.setChecked(qh.upper() == hx)
        self.dot_group.setExclusive(True)

    def _shuffle(self):
        self.seed = random.randint(1, 10 ** 6)
        self.request_geometry()

    def activate(self):
        if not self._activated:
            self._activated = True
            self.request_geometry()

    def request_geometry(self):
        self.geom_job.request(size=512, layers=self.layers.value(), seed=self.seed, bead=self.bead.value(),
                              imp=self.imp.value())

    def _geometry(self, nrm):
        self.n_prev = nrm
        self.request_render()

    def request_render(self, fast=False):
        if self.n_prev is None:
            return
        self.render_job.request(nrm=self.n_prev, color=self.color.color(), rough=self.rough.value(), tile=0.75,
                                light=self.light, ss=1 if fast else 2)

    def params(self):
        return {"name": self.name.text().strip() or "3D Print Layer Lines", "color": list(self.color.color()),
                "roughness": self.rough.value(), "layers": self.layers.value(), "bead": self.bead.value(),
                "imperfections": self.imp.value(), "seed": self.seed, "size": self.size.value(),
                "tile": self.tile.value()}

    def set_params(self, p):
        self.name.setText(p.get("name", "3D Print PLA Layer Lines"))
        if p.get("color"):
            self.color.set_color(tuple(p["color"]))
            self._sync_dots()
        self.rough.set_value(p.get("roughness", 0.4))
        self._rough_changed(self.rough.value())
        self.layers.set_value(p.get("layers", 64))
        self._layers_hint()
        self.bead.set_value(p.get("bead", 3.0))
        self.imp.set_value(p.get("imperfections", 1.0))
        self.seed = int(p.get("seed", 3))
        self.size.set_value(p.get("size", 2048), emit=True)
        self.tile.setValue(int(p.get("tile", 8)))
        self._activated = True
        self.request_geometry()
