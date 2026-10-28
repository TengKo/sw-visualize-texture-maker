"""Home, Processing and Saved pages."""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import icons
from .theme import C
from .widgets import DropZone, StepList, hbox, label, pil_to_pixmap, set_elided


def _basename(path):
    return os.path.basename(path.replace("\\", "/"))


def footer_bar(saves_label, *buttons):
    f = QFrame()
    f.setObjectName("Footer")
    lay = QHBoxLayout(f)
    lay.setContentsMargins(24, 12, 24, 12)
    lay.setSpacing(12)
    lay.addWidget(label("Saves to", "Hint"))
    lay.addWidget(saves_label)
    for b in buttons:
        if b == "stretch":
            lay.addStretch(1)
        else:
            lay.addWidget(b)
    return f


class RecentCard(QPushButton):
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("RecentCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(76)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(14)
        th = QLabel()
        th.setFixedSize(52, 52)
        pm = QPixmap(entry.get("thumb", "")) if entry.get("thumb") else QPixmap()
        if not pm.isNull():
            th.setPixmap(pm.scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            th.setPixmap(icons.pixmap("logo", C["muted"], 40))
        name = label(entry.get("name", "Untitled"))
        name.setStyleSheet("font-weight: 600;")
        kind = "3D print preset" if entry.get("kind") == "preset" else "From photo"
        meta = label(f"{kind} · {entry.get('params', {}).get('size', 2048)} px", "Hint")
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(name)
        col.addWidget(meta)
        lay.addWidget(th)
        lay.addLayout(col, 1)
        for w in (th, name, meta):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setToolTip(entry.get("svap", ""))
        self.setAccessibleName(f"Open {entry.get('name', '')}")


class HomePage(QWidget):
    photoChosen = Signal(str)
    browseClicked = Signal()
    recentClicked = Signal(dict)
    changeOutput = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner.setObjectName("Transparent")
        il = QHBoxLayout(inner)
        il.setContentsMargins(24, 40, 24, 32)
        col = QWidget()
        col.setObjectName("Transparent")
        col.setMaximumWidth(880)
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(28)
        self.drop = DropZone()
        self.drop.fileChosen.connect(self.photoChosen.emit)
        self.drop.browseClicked.connect(self.browseClicked.emit)
        cl.addWidget(self.drop)
        self.recent_box = QWidget()
        self.recent_box.setObjectName("Transparent")
        rl = QVBoxLayout(self.recent_box)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(12)
        rl.addWidget(label("RECENT", "SectionCaps"))
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        rl.addLayout(self.grid)
        cl.addWidget(self.recent_box)
        cl.addStretch(1)
        il.addStretch(1)
        il.addWidget(col, 100)
        il.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        self.out_label = label("", "Mono")
        change = QPushButton("Change…")
        change.clicked.connect(self.changeOutput.emit)
        root.addWidget(footer_bar(self.out_label, change, "stretch"))

    def refresh(self, settings):
        set_elided(self.out_label, settings.output_dir, 640)
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        items = settings.recent()
        self.recent_box.setVisible(bool(items))
        for i, e in enumerate(items):
            card = RecentCard(e)
            card.clicked.connect(lambda _=False, e=e: self.recentClicked.emit(e))
            self.grid.addWidget(card, i // 3, i % 3)
        for c in range(3):
            self.grid.setColumnStretch(c, 1)


class ProcessingPage(QWidget):
    cancelClicked = Signal()
    STEPS = ["Evening out the lighting", "Making it tile seamlessly", "Building the height map", "Rendering the preview"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 48, 24, 48)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(800)
        cl = QHBoxLayout(card)
        cl.setContentsMargins(32, 32, 32, 32)
        cl.setSpacing(32)
        self.thumb = QLabel()
        self.thumb.setFixedSize(240, 240)
        self.thumb.setStyleSheet("border-radius: 12px;")
        cl.addWidget(self.thumb, 0, Qt.AlignmentFlag.AlignTop)
        right = QVBoxLayout()
        right.setSpacing(20)
        right.addWidget(label("Making your texture", "H2"))
        self.fname = label("", "MonoMuted")
        right.addWidget(self.fname)
        self.steps = StepList(self.STEPS)
        right.addWidget(self.steps)
        right.addStretch(1)
        self.cancel = QPushButton("Cancel")
        self.cancel.clicked.connect(self.cancelClicked.emit)
        right.addLayout(hbox(label("Usually takes a few seconds.", "Hint"), "stretch", self.cancel))
        cl.addLayout(right, 1)
        root.addStretch(1)
        root.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch(1)

    def set_photo(self, img, name):
        w, h = img.size
        s = min(w, h)
        sq = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((480, 480))
        pm = pil_to_pixmap(sq)
        pm.setDevicePixelRatio(2.0)
        self.thumb.setPixmap(pm)
        self.fname.setText(f"{name} · {w} × {h} px")
        self.cancel.setEnabled(True)
        self.steps.set_active(0)

    def set_step(self, i, _msg=""):
        self.steps.set_active(i)


class SavedPage(QWidget):
    makeAnother = Signal()
    backToEdit = Signal()
    openFolder = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self._path = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 48, 24, 48)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(860)
        cl = QHBoxLayout(card)
        cl.setContentsMargins(32, 32, 32, 32)
        cl.setSpacing(32)
        self.sphere = QLabel()
        self.sphere.setFixedSize(220, 220)
        cl.addWidget(self.sphere, 0, Qt.AlignmentFlag.AlignVCenter)
        right = QVBoxLayout()
        right.setSpacing(16)
        ok = QHBoxLayout()
        ok.setSpacing(8)
        okic = QLabel()
        okic.setPixmap(icons.pixmap("check_circle", C["success"], 22, 2))
        ok.addWidget(okic)
        ok.addWidget(label("Saved", "Success"))
        ok.addStretch(1)
        right.addLayout(ok)
        self.title = label("", "H2")
        right.addWidget(self.title)
        self.details = QGridLayout()
        self.details.setHorizontalSpacing(20)
        self.details.setVerticalSpacing(8)
        right.addLayout(self.details)
        self.another = QPushButton("Make another")
        self.another.setObjectName("Primary")
        self.another.clicked.connect(self.makeAnother.emit)
        folder = QPushButton("  Open folder")
        folder.setIcon(icons.icon("folder", C["text"], 18))
        folder.clicked.connect(lambda: self.openFolder.emit(self._path))
        back = QPushButton("Back to editing")
        back.clicked.connect(self.backToEdit.emit)
        right.addLayout(hbox(self.another, folder, back, "stretch", spacing=12))
        right.addWidget(label("Next: import the .svap into Visualize's appearance library, then drag it onto your part.",
                              "Hint", wrap=True))
        cl.addLayout(right, 1)
        root.addStretch(1)
        root.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch(1)

    def set_result(self, info, sphere_pixmap=None):
        self._path = info["svap"]
        set_elided(self.title, _basename(info["svap"]), 460)
        if sphere_pixmap is not None:
            pm = sphere_pixmap.scaled(440, 440, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(2.0)
            self.sphere.setPixmap(pm)
        while self.details.count():
            w = self.details.takeAt(0).widget()
            if w:
                w.deleteLater()
        mb = info.get("bytes", 0) / 1e6
        rows = [("Location", info["svap"], True), ("File size", f"{mb:.1f} MB", False),
                ("Bump map", f"{info['tex_size']} × {info['tex_size']} px, seamless", False),
                ("Repeat", f"{info['tile']:g}×", False)]
        if info.get("png"):
            rows.append(("Also saved", _basename(info["png"]), True))
        for r, (k, v, mono) in enumerate(rows):
            kl = label(k, "Muted")
            vl = label("", "Mono" if mono else None)
            set_elided(vl, v, 400)
            vl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            for w in (kl, vl):
                w.setFixedHeight(22)
            self.details.addWidget(kl, r, 0)
            self.details.addWidget(vl, r, 1)
        self.details.setColumnStretch(1, 1)
        self.updateGeometry()
