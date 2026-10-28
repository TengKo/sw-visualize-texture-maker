"""Main window: header with mode switch + stacked pages, and the generate/save jobs."""
import os
import subprocess
import sys

from PIL import Image
from PySide6.QtCore import Qt, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import APP_NAME
from ..engine import (auto_strength, build_svap, check_photo, generate_fdm, height_to_normal, load_image,
                      process_photo, resize_height)
from ..engine.normal import flip_green
from ..engine.svap import safe_stem
from . import icons
from .dialogs import PickColorDialog, SettingsDialog
from .editor import EditorPage, PresetPage
from .pages import HomePage, ProcessingPage, SavedPage
from .theme import C
from .widgets import IMAGE_EXTS, DropZone, Segmented, label, numpy_to_pixmap
from .workers import run_async

IMAGE_FILTER = "Images (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp)"


def unique_path(folder, stem, ext):
    p = os.path.join(folder, stem + ext)
    i = 2
    while os.path.exists(p):
        p = os.path.join(folder, f"{stem} ({i}){ext}")
        i += 1
    return p


# --- jobs (run in worker threads) ---------------------------------------------------------
def _job_photo_svap(height, p, out_path, template):
    hh = resize_height(height, p["size"])
    n = height_to_normal(hh, p["bump"] * auto_strength(hh))
    thumb = build_svap(out_path, p["name"], tuple(p["color"]), p["roughness"], p["tile"], n,
                       template=template or None, thumb_tile=2.0)
    png = None
    if p.get("save_png"):
        png = os.path.splitext(out_path)[0] + "_normal.png"
        Image.fromarray(flip_green(n) if p.get("png_style") == "gl" else n, "RGB").save(png)
    return {"svap": out_path, "png": png, "bytes": os.path.getsize(out_path), "tex_size": p["size"],
            "tile": p["tile"], "thumb": thumb}


def _job_preset_svap(p, out_path, template):
    n = height_to_normal(generate_fdm(p["size"], p["layers"], p["seed"], p["bead"], p["imperfections"]), 1.0)
    thumb = build_svap(out_path, p["name"], tuple(p["color"]), p["roughness"], p["tile"], n,
                       template=template or None, thumb_tile=0.5)
    return {"svap": out_path, "png": None, "bytes": os.path.getsize(out_path), "tex_size": p["size"],
            "tile": p["tile"], "thumb": thumb}


def _job_bump_png(kind, p, height, out_path):
    if kind == "photo":
        hh = resize_height(height, p["size"])
        n = height_to_normal(hh, p["bump"] * auto_strength(hh))
        if p.get("png_style") == "gl":
            n = flip_green(n)
    else:
        n = height_to_normal(generate_fdm(p["size"], p["layers"], p["seed"], p["bead"], p["imperfections"]), 1.0)
    Image.fromarray(n, "RGB").save(out_path)
    return out_path


class MainWindow(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._cancel = False
        self._job_token = 0
        self.last_kind = "photo"
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100, 720)
        self.resize(1320, 860)
        self.setAcceptDrops(True)

        central = QWidget()
        central.setObjectName("Page")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._header())
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.home = HomePage()
        self.processing = ProcessingPage()
        self.editor = EditorPage()
        self.saved = SavedPage()
        self.preset = PresetPage()
        for w in (self.home, self.processing, self.editor, self.saved, self.preset):
            self.stack.addWidget(w)

        self.home.photoChosen.connect(self.open_photo)
        self.home.browseClicked.connect(self.browse)
        self.home.recentClicked.connect(self.open_recent)
        self.home.changeOutput.connect(self.open_settings)
        self.processing.cancelClicked.connect(self._cancel_processing)
        self.editor.replaceRequested.connect(self.browse)
        self.editor.reprocessRequested.connect(self._reprocess)
        self.editor.pickColorRequested.connect(self._pick_color)
        self.editor.generateRequested.connect(lambda p: self.generate("photo", p))
        self.editor.saveBumpRequested.connect(lambda p: self.save_bump("photo", p))
        self.preset.generateRequested.connect(lambda p: self.generate("preset", p))
        self.preset.saveBumpRequested.connect(lambda p: self.save_bump("preset", p))
        self.saved.makeAnother.connect(self._make_another)
        self.saved.backToEdit.connect(lambda: self.show_page(self.editor if self.last_kind == "photo" else self.preset))
        self.saved.openFolder.connect(self.reveal)

        self.refresh_settings()
        self.show_page(self.home)

    # header ---------------------------------------------------------------------------
    def _header(self):
        h = QFrame()
        h.setObjectName("Header")
        lay = QHBoxLayout(h)
        lay.setContentsMargins(24, 10, 24, 10)
        lay.setSpacing(20)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("logo", C["accent"], 24))
        lay.addWidget(logo)
        lay.addWidget(label(APP_NAME, "AppTitle"))
        lay.addSpacing(8)
        self.mode = Segmented([("photo", "From photo"), ("preset", "3D print preset")], value="photo")
        self.mode.setFixedWidth(300)
        self.mode.changed.connect(self._mode_changed)
        lay.addWidget(self.mode)
        lay.addStretch(1)
        gear = QPushButton()
        gear.setObjectName("IconButton")
        gear.setIcon(icons.icon("gear", C["label"], 20))
        gear.setToolTip("Settings")
        gear.setAccessibleName("Settings")
        gear.clicked.connect(self.open_settings)
        lay.addWidget(gear)
        return h

    def show_page(self, page):
        self.stack.setCurrentWidget(page)
        if page is self.preset:
            self.mode.set_value("preset")
            self.preset.activate()
        elif page in (self.home, self.processing, self.editor):
            self.mode.set_value("photo")

    def _mode_changed(self, v):
        if v == "preset":
            self.show_page(self.preset)
        else:
            self.show_page(self.editor if self.editor.result is not None else self.home)

    def refresh_settings(self):
        self.home.refresh(self.settings)
        for p in (self.editor, self.preset):
            p.set_output_dir(self.settings.output_dir)

    def open_settings(self):
        if SettingsDialog(self.settings, self).exec():
            self.refresh_settings()

    # photo flow -------------------------------------------------------------------------
    def browse(self):
        start = os.path.dirname(self.editor.photo_path) if self.editor.photo_path else os.path.expanduser("~")
        p, _ = QFileDialog.getOpenFileName(self, "Choose a texture photo", start, IMAGE_FILTER)
        if p:
            self.open_photo(p)

    def open_photo(self, path, params=None):
        try:
            img = load_image(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Can't open that file", f"{os.path.basename(path)} couldn't be opened as an image.\n\n{e}")
            return
        warnings = check_photo(img)
        if warnings:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Heads-up")
            box.setText(warnings[0])
            go = box.addButton("Continue anyway", QMessageBox.ButtonRole.AcceptRole)
            other = box.addButton("Pick another", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(go)
            box.exec()
            if box.clickedButton() is other:
                self.browse()
                return
        self._start_processing(img, path, params, (params or {}).get("seam_band", 120))

    def _start_processing(self, img, path, params, seam_band):
        self._cancel = False
        self._job_token += 1
        token = self._job_token
        self.processing.set_photo(img, os.path.basename(path))
        self.show_page(self.processing)
        run_async(process_photo, img, 2048, seam_band, cancel=lambda: self._cancel or token != self._job_token,
                  on_progress=self.processing.set_step,
                  on_result=lambda r: self._photo_done(token, r, path, params),
                  on_error=lambda m: self._photo_failed(token, m))

    def _photo_done(self, token, result, path, params):
        if token != self._job_token:
            return
        self.processing.set_step(3)
        self.editor.load(result, path, params)
        self.show_page(self.editor)

    def _photo_failed(self, token, msg):
        if token != self._job_token:
            return
        self.show_page(self.editor if self.editor.result is not None else self.home)
        if msg != "__cancelled__":
            QMessageBox.critical(self, "Something went wrong", f"The photo couldn't be processed.\n\n{msg[:1500]}")

    def _cancel_processing(self):
        self._cancel = True
        self.processing.cancel.setEnabled(False)
        self._job_token += 1
        self.show_page(self.editor if self.editor.result is not None else self.home)

    def _reprocess(self, seam_band):
        if not self.editor.photo_path:
            return
        params = self.editor.params()
        try:
            img = load_image(self.editor.photo_path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Can't reopen the photo", str(e))
            return
        self._start_processing(img, self.editor.photo_path, params, seam_band)

    def _pick_color(self):
        if self.editor.result is None:
            return
        dlg = PickColorDialog(self.editor.result.crop, self.editor.color.color(), self)
        if dlg.exec():
            self.editor.color.set_color(dlg.color, emit=True)

    # generate -----------------------------------------------------------------------------
    def _output_dir(self):
        d = self.settings.output_dir
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, "Can't save there", f"The output folder can't be created:\n{d}\n\n{e}\n\n"
                                                          "Choose another folder in Settings.")
            return None
        return d

    def generate(self, kind, params):
        d = self._output_dir()
        if not d:
            return
        page = self.editor if kind == "photo" else self.preset
        out = unique_path(d, safe_stem(params["name"]), ".svap")
        page.set_generating(True)
        QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        if kind == "photo":
            run_async(_job_photo_svap, self.editor.result.height, params, out, self.settings.template,
                      on_result=lambda info: self._generated(kind, params, info),
                      on_error=lambda m: self._generate_failed(kind, m))
        else:
            run_async(_job_preset_svap, params, out, self.settings.template,
                      on_result=lambda info: self._generated(kind, params, info),
                      on_error=lambda m: self._generate_failed(kind, m))

    def _generated(self, kind, params, info):
        QApplication.restoreOverrideCursor()
        page = self.editor if kind == "photo" else self.preset
        page.set_generating(False)
        self.last_kind = kind
        entry = {"name": params["name"], "kind": kind, "svap": info["svap"], "params": params}
        if kind == "photo":
            entry["photo"] = self.editor.photo_path
        self.settings.add_recent(entry, thumb_image=info["thumb"])
        self.home.refresh(self.settings)
        self.saved.another.setText("Make another" if kind == "photo" else "Make another preset")
        self.saved.set_result(info, page.sphere_pm)
        self.stack.setCurrentWidget(self.saved)

    def _generate_failed(self, kind, msg):
        QApplication.restoreOverrideCursor()
        (self.editor if kind == "photo" else self.preset).set_generating(False)
        QMessageBox.critical(self, "Couldn't save the appearance", msg[:1500])

    def save_bump(self, kind, params):
        d = self._output_dir() or os.path.expanduser("~")
        default = os.path.join(d, safe_stem(params["name"]) + "_normal.png")
        p, _ = QFileDialog.getSaveFileName(self, "Save bump map", default, "PNG image (*.png)")
        if not p:
            return
        if not p.lower().endswith(".png"):
            p += ".png"
        height = self.editor.result.height if kind == "photo" else None
        QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        run_async(_job_bump_png, kind, params, height, p,
                  on_result=lambda path: (QApplication.restoreOverrideCursor(),
                                          QMessageBox.information(self, "Saved", f"Bump map saved:\n{path}")),
                  on_error=lambda m: (QApplication.restoreOverrideCursor(),
                                      QMessageBox.critical(self, "Couldn't save", m[:1500])))

    def _make_another(self):
        if self.last_kind == "preset":
            self.show_page(self.preset)
        else:
            self.show_page(self.home)

    def open_recent(self, entry):
        params = entry.get("params") or {}
        if entry.get("kind") == "preset":
            self.preset.set_params(params)
            self.show_page(self.preset)
            return
        photo = entry.get("photo", "")
        if photo and os.path.exists(photo):
            self.open_photo(photo, params)
        else:
            QMessageBox.information(self, "Photo not found",
                                    "The original photo for this texture was moved or deleted, so it can't be re-opened.\n\n"
                                    f"The saved appearance is here:\n{entry.get('svap', '')}")

    def reveal(self, path):
        if sys.platform == "win32" and os.path.exists(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    # window-level drag & drop -----------------------------------------------------------
    def dragEnterEvent(self, e):
        if self.stack.currentWidget() in (self.home, self.editor) and DropZone.image_from_mime(e.mimeData()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        p = DropZone.image_from_mime(e.mimeData())
        if p:
            e.acceptProposedAction()
            self.open_photo(p)

    def closeEvent(self, e):
        self._cancel = True
        self._job_token += 1
        QThreadPool.globalInstance().waitForDone(8000)
        super().closeEvent(e)

    def _numpy_pm(self, arr):
        return numpy_to_pixmap(arr)
