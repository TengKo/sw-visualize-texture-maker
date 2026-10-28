"""Settings and colour-picker dialogs."""
import os

import numpy as np
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..engine.svap import make_material_xml, read_template_xml
from ..settings import default_output_dir
from .widgets import field, label, pil_to_pixmap, srgb_to_hex

REPO_URL = "https://github.com/TengKo/sw-visualize-texture-maker"


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 20)
        lay.setSpacing(20)

        self.out = QLineEdit(settings.output_dir)
        b1 = QPushButton("Browse…")
        b1.clicked.connect(self._browse_out)
        b1r = QPushButton("Default")
        b1r.clicked.connect(lambda: self.out.setText(default_output_dir()))
        row1 = QWidget()
        row1.setObjectName("Transparent")
        r1 = QHBoxLayout(row1)
        r1.setContentsMargins(0, 0, 0, 0)
        r1.addWidget(self.out, 1)
        r1.addWidget(b1)
        r1.addWidget(b1r)
        lay.addWidget(field("Save .svap files to", row1))

        self.tpl = QLineEdit(settings.template)
        self.tpl.setPlaceholderText("Built-in template")
        b2 = QPushButton("Browse…")
        b2.clicked.connect(self._browse_tpl)
        b2r = QPushButton("Use built-in")
        b2r.clicked.connect(lambda: self.tpl.setText(""))
        row2 = QWidget()
        row2.setObjectName("Transparent")
        r2 = QHBoxLayout(row2)
        r2.setContentsMargins(0, 0, 0, 0)
        r2.addWidget(self.tpl, 1)
        r2.addWidget(b2)
        r2.addWidget(b2r)
        lay.addWidget(field("Template appearance", row2,
                            hint="Advanced. New appearances copy this file's settings and change only the name, "
                                 "color, roughness, bump map and repeat. A custom .svap must have exactly one "
                                 "texture, in the normal-map slot."))

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #2C3036;")
        lay.addWidget(line)
        about = label(f"<b>{APP_NAME}</b> {__version__} · open source (MIT) · "
                      f"<a href='{REPO_URL}' style='color:#F2A93B'>GitHub</a><br>"
                      "Not affiliated with or endorsed by Dassault Systèmes. SOLIDWORKS and SOLIDWORKS Visualize "
                      "are trademarks of Dassault Systèmes.", "Hint", wrap=True)
        about.setTextFormat(Qt.TextFormat.RichText)
        about.setOpenExternalLinks(True)
        lay.addWidget(about)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primary")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _browse_out(self):
        d = QFileDialog.getExistingDirectory(self, "Save .svap files to", self.out.text() or os.path.expanduser("~"))
        if d:
            self.out.setText(os.path.normpath(d))

    def _browse_tpl(self):
        p, _ = QFileDialog.getOpenFileName(self, "Choose a template appearance", "",
                                           "Visualize appearance (*.svap);;Material XML (*.xml)")
        if p:
            self.tpl.setText(os.path.normpath(p))

    def _save(self):
        tpl = self.tpl.text().strip()
        if tpl:
            try:
                make_material_xml(read_template_xml(tpl), "Check", "Check_normal", (0.5, 0.5, 0.5), 0.5, 1)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Template can't be used", f"This file can't be used as a template:\n\n{e}")
                return
        out = self.out.text().strip() or default_output_dir()
        try:
            os.makedirs(out, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, "Folder problem", f"Can't use that folder:\n\n{e}")
            return
        self.settings.output_dir = out
        self.settings.template = tpl
        self.accept()


class _PickView(QWidget):
    picked = Signal(float, float)

    def __init__(self, pm, parent=None):
        super().__init__(parent)
        self.pm = pm
        self.setMinimumSize(520, 520)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _rect(self):
        s = min(self.width(), self.height())
        return QRectF((self.width() - s) / 2, (self.height() - s) / 2, s, s)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(self._rect(), self.pm, QRectF(self.pm.rect()))
        p.end()

    def mousePressEvent(self, e):
        r = self._rect()
        x, y = (e.position().x() - r.x()) / r.width(), (e.position().y() - r.y()) / r.height()
        if 0 <= x <= 1 and 0 <= y <= 1:
            self.picked.emit(x, y)


class PickColorDialog(QDialog):
    """Click the photo to sample a colour (averaged over a small patch)."""

    def __init__(self, crop_img, current, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick a color from the photo")
        self.arr = np.asarray(crop_img.convert("RGB"), dtype=np.float64)
        self.color = tuple(current)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(14)
        lay.addWidget(label("Click anywhere on the photo. The color is averaged over a small area.", "Muted"))
        view = _PickView(pil_to_pixmap(crop_img.resize((1040, 1040))))
        view.picked.connect(self._pick)
        lay.addWidget(view, 1)
        self.swatch = QLabel()
        self.swatch.setFixedSize(40, 40)
        self.hex = label("", "Mono")
        row = QHBoxLayout()
        row.addWidget(self.swatch)
        row.addWidget(self.hex)
        row.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Use this color")
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primary")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        row.addWidget(bb)
        lay.addLayout(row)
        self._show()

    def _pick(self, x, y):
        h, w = self.arr.shape[:2]
        r = max(2, w // 120)
        cx, cy = int(x * (w - 1)), int(y * (h - 1))
        patch = self.arr[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1]
        self.color = tuple(float(v) for v in patch.reshape(-1, 3).mean(0) / 255)
        self._show()

    def _show(self):
        hx = srgb_to_hex(self.color)
        self.swatch.setStyleSheet(f"background: {hx}; border: 1px solid #6A7078; border-radius: 8px;")
        self.hex.setText(hx)
