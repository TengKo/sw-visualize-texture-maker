"""Reusable widgets for the dark UI."""
import os

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QColorDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
                               QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget)

from . import icons
from .theme import C

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp")


# ----------------------------------------------------------------------------- helpers
def label(text, name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def set_elided(lbl, text, max_px, mode=Qt.TextElideMode.ElideMiddle):
    """Show `text` shortened to fit max_px (full text in the tooltip)."""
    lbl.setText(lbl.fontMetrics().elidedText(text, mode, max_px))
    lbl.setToolTip(text)


def numpy_to_pixmap(arr):
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    if arr.ndim == 3 and arr.shape[2] == 4:
        img = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    else:
        arr = np.ascontiguousarray(arr[..., :3])
        img = QImage(arr.data, w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(img.copy())


def pil_to_pixmap(img):
    return numpy_to_pixmap(np.asarray(img.convert("RGBA")))


def srgb_to_hex(c):
    return "#{:02X}{:02X}{:02X}".format(*(int(round(max(0, min(1, v)) * 255)) for v in c))


def hex_to_srgb(s):
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        raise ValueError(s)
    return tuple(int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))


def vbox(*widgets, spacing=8, margins=(0, 0, 0, 0)):
    w = QWidget()
    w.setObjectName("Transparent")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    for x in widgets:
        if isinstance(x, QWidget):
            lay.addWidget(x)
        elif x == "stretch":
            lay.addStretch(1)
        else:
            lay.addLayout(x)
    return w


def hbox(*widgets, spacing=8, margins=(0, 0, 0, 0)):
    lay = QHBoxLayout()
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    for x in widgets:
        if x == "stretch":
            lay.addStretch(1)
        elif isinstance(x, QWidget):
            lay.addWidget(x)
        else:
            lay.addLayout(x)
    return lay


def field(title, *content, hint=None, spacing=8):
    """Label + controls (+ hint) stacked."""
    items = [label(title, "FieldLabel")] + list(content)
    if hint is not None:
        items.append(hint if isinstance(hint, QWidget) else label(hint, "Hint", wrap=True))
    return vbox(*items, spacing=spacing)


# ----------------------------------------------------------------------------- Segmented
class Segmented(QFrame):
    changed = Signal(object)

    def __init__(self, options, value=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.values = []
        for i, (val, text) in enumerate(options):
            b = QPushButton(text)
            b.setObjectName("SegButton")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.group.addButton(b, i)
            lay.addWidget(b)
            self.values.append(val)
        self.group.idClicked.connect(lambda i: self.changed.emit(self.values[i]))
        self.set_value(value if value is not None else self.values[0])

    def set_value(self, value, emit=False):
        if value in self.values:
            self.group.button(self.values.index(value)).setChecked(True)
            if emit:
                self.changed.emit(value)

    def clear(self):
        self.group.setExclusive(False)
        for b in self.group.buttons():
            b.setChecked(False)
        self.group.setExclusive(True)

    def value(self):
        i = self.group.checkedId()
        return self.values[i] if i >= 0 else None


# ----------------------------------------------------------------------------- SliderRow
class SliderRow(QWidget):
    """Float slider with a value read-out and optional end captions."""
    changed = Signal(float)

    def __init__(self, lo, hi, value, step=0.01, fmt="{:.2f}", inline_label=None, captions=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Transparent")
        self.lo, self.hi, self.step, self.fmt = lo, hi, step, fmt
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, int(round((hi - lo) / step)))
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.readout = label("", "Mono")
        self.readout.setMinimumWidth(44)
        self.readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(12)
        if inline_label:
            il = label(inline_label, "Muted")
            il.setMinimumWidth(84)
            row.addWidget(il)
        row.addWidget(self.slider, 1)
        row.addWidget(self.readout)
        outer.addLayout(row)
        if captions:
            cap = QHBoxLayout()
            cap.addWidget(label(captions[0], "Hint"))
            cap.addStretch(1)
            cap.addWidget(label(captions[1], "Hint"))
            cap.setContentsMargins(0, 0, 56, 0)
            outer.addLayout(cap)
        self.slider.valueChanged.connect(self._on)
        self.set_value(value)

    def _on(self, i):
        v = self.value()
        self.readout.setText(self.fmt.format(v))
        self.changed.emit(v)

    def value(self):
        return round(self.lo + self.slider.value() * self.step, 6)

    def set_value(self, v, emit=False):
        self.slider.blockSignals(not emit)
        self.slider.setValue(int(round((min(max(v, self.lo), self.hi) - self.lo) / self.step)))
        self.slider.blockSignals(False)
        self.readout.setText(self.fmt.format(self.value()))


# ----------------------------------------------------------------------------- ColorField
class ColorField(QWidget):
    changed = Signal(tuple)

    def __init__(self, srgb=(0.5, 0.5, 0.5), parent=None):
        super().__init__(parent)
        self.setObjectName("Transparent")
        self._c = tuple(srgb)
        self.swatch = QPushButton()
        self.swatch.setObjectName("Swatch")
        self.swatch.setToolTip("Choose a color")
        self.swatch.setAccessibleName("Choose color")
        self.swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hex = QLineEdit()
        self.hex.setObjectName("Mono")
        self.hex.setMaxLength(7)
        self.hex.setAccessibleName("Hex color")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self.swatch)
        lay.addWidget(self.hex, 1)
        self.swatch.clicked.connect(self._pick)
        self.hex.editingFinished.connect(self._typed)
        self.set_color(self._c)

    def color(self):
        return self._c

    def set_color(self, srgb, emit=False):
        self._c = tuple(float(v) for v in srgb)
        hx = srgb_to_hex(self._c)
        self.hex.setText(hx)
        lum = 0.2126 * self._c[0] + 0.7152 * self._c[1] + 0.0722 * self._c[2]
        border = "#6A7078" if lum < 0.5 else "#A0A4AA"
        self.swatch.setStyleSheet(f"QPushButton#Swatch {{ background: {hx}; border: 1px solid {border}; }}")
        if emit:
            self.changed.emit(self._c)

    def _pick(self):
        q = QColorDialog.getColor(QColor(srgb_to_hex(self._c)), self, "Choose a color")
        if q.isValid():
            self.set_color((q.redF(), q.greenF(), q.blueF()), emit=True)

    def _typed(self):
        try:
            c = hex_to_srgb(self.hex.text())
        except ValueError:
            self.set_color(self._c)
            return
        if srgb_to_hex(c) != srgb_to_hex(self._c):
            self.set_color(c, emit=True)


# ----------------------------------------------------------------------------- DropZone
class DropZone(QFrame):
    fileChosen = Signal(str)
    browseClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(340)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 36, 24, 36)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("image", C["accent"], 48, 1.5))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = label("Drop a texture photo here", "H1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = label("JPG, PNG or TIFF. Shoot straight on in even light and fill the frame with the surface. "
                    "1500 px or more works best.", "Muted", wrap=True)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setMinimumWidth(500)
        sub.setMaximumWidth(560)
        self.browse = QPushButton("Browse…")
        self.browse.setObjectName("Primary")
        self.browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse.clicked.connect(self.browseClicked.emit)
        lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(sub, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(4)
        lay.addWidget(self.browse, 0, Qt.AlignmentFlag.AlignHCenter)

    @staticmethod
    def image_from_mime(mime):
        if mime.hasUrls():
            for u in mime.urls():
                p = u.toLocalFile()
                if p and os.path.splitext(p)[1].lower() in IMAGE_EXTS:
                    return p
        return None

    def _hover(self, on):
        self.setProperty("hover", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if self.image_from_mime(e.mimeData()):
            e.acceptProposedAction()
            self._hover(True)

    def dragLeaveEvent(self, e):
        self._hover(False)

    def dropEvent(self, e):
        self._hover(False)
        p = self.image_from_mime(e.mimeData())
        if p:
            e.acceptProposedAction()
            self.fileChosen.emit(p)


# ----------------------------------------------------------------------------- StepList
class StepList(QWidget):
    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self.setObjectName("Transparent")
        self.rows = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self._done = icons.pixmap("check_circle", C["success"], 22, 2)
        self._todo = icons.pixmap("circle", "#3E444C", 22, 2)
        self._busy = icons.spinner_pixmap(22)
        for text in steps:
            ic = QLabel()
            ic.setFixedSize(22, 22)
            tx = QLabel(text)
            bar = QProgressBar()
            bar.setRange(0, 0)
            bar.setTextVisible(False)
            bar.setAccessibleName(text + " progress")
            row = QWidget()
            row.setObjectName("Transparent")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(6)
            top = QHBoxLayout()
            top.setSpacing(12)
            top.addWidget(ic)
            top.addWidget(tx, 1)
            rl.addLayout(top)
            bl = QHBoxLayout()
            bl.setContentsMargins(34, 0, 0, 0)
            bl.addWidget(bar)
            rl.addLayout(bl)
            lay.addWidget(row)
            self.rows.append((ic, tx, bar))
        self.set_active(-1)

    def set_active(self, idx):
        for i, (ic, tx, bar) in enumerate(self.rows):
            if i < idx:
                ic.setPixmap(self._done)
                tx.setStyleSheet(f"color: {C['text']}; font-weight: 400;")
                bar.hide()
            elif i == idx:
                ic.setPixmap(self._busy)
                tx.setStyleSheet(f"color: {C['text']}; font-weight: 600;")
                bar.show()
            else:
                ic.setPixmap(self._todo)
                tx.setStyleSheet(f"color: {C['muted']}; font-weight: 400;")
                bar.hide()


# ----------------------------------------------------------------------------- PreviewLabel
class PreviewLabel(QWidget):
    """Shows a pixmap scaled to fit, centred. Emits normalised drag positions (for moving the light)."""
    dragged = Signal(float, float)
    released = Signal()

    def __init__(self, draggable=False, parent=None):
        super().__init__(parent)
        self._pm = None
        self.draggable = draggable
        self.setMinimumSize(QSize(200, 200))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if draggable:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.max_side = 560

    def set_pixmap(self, pm):
        self._pm = pm
        self.update()

    def _target(self):
        if self._pm is None:
            return QRectF()
        w, h = self.width(), self.height()
        pw = self._pm.width() / self._pm.devicePixelRatio()
        ph = self._pm.height() / self._pm.devicePixelRatio()
        s = min(w / pw, h / ph, self.max_side / max(pw, ph))
        tw, th = pw * s, ph * s
        return QRectF((w - tw) / 2, (h - th) / 2, tw, th)

    def paintEvent(self, e):
        if self._pm is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(self._target(), self._pm, QRectF(self._pm.rect()))
        p.end()

    def _emit(self, pos):
        r = self._target()
        if r.isEmpty():
            return
        c = r.center()
        self.dragged.emit((pos.x() - c.x()) / (r.width() / 2), (pos.y() - c.y()) / (r.height() / 2))

    def mousePressEvent(self, e):
        if self.draggable and e.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._emit(QPointF(e.position()))

    def mouseMoveEvent(self, e):
        if self.draggable and e.buttons() & Qt.MouseButton.LeftButton:
            self._emit(QPointF(e.position()))

    def mouseReleaseEvent(self, e):
        if self.draggable:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.released.emit()


def hline():
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {C['border']};")
    return f
