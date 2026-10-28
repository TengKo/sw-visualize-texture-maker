"""Application entry point."""
import os
import sys
import traceback


def _resource(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def self_test(out_dir):
    """Exercise the engine and build the main window without showing it. Writes self_test.json in out_dir.
    Used by CI on the packaged .exe (windowed apps have no console, so results go to a file)."""
    import json

    report = {"ok": False}
    try:
        import numpy as np
        from PIL import Image

        from .engine import (auto_strength, build_svap, generate_fdm, height_to_normal, process_photo,
                             verify_svap)
        os.makedirs(out_dir, exist_ok=True)
        rng = np.random.default_rng(0)
        f = np.fft.fftfreq(1200)[:, None] ** 2 + np.fft.fftfreq(1200)[None, :] ** 2
        tex = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((1200, 1200))) * np.exp(-f / 0.002)))
        g = (tex - tex.min()) / (tex.max() - tex.min()) * np.linspace(0.4, 1, 1200)[:, None]
        img = Image.fromarray((np.dstack([g, g, g]) * 255).astype(np.uint8), "RGB")
        r = process_photo(img, size=256)
        p1 = os.path.join(out_dir, "self_test_photo.svap")
        build_svap(p1, "Self Test Photo", r.base_srgb, 0.5, 5, height_to_normal(r.height, auto_strength(r.height)))
        report["photo"] = verify_svap(p1)
        p2 = os.path.join(out_dir, "self_test_fdm.svap")
        build_svap(p2, "Self Test Layers", (0.55, 0.55, 0.56), 0.4, 8, height_to_normal(generate_fdm(256, 16, 1), 1.0))
        report["fdm"] = verify_svap(p2)

        from PySide6.QtWidgets import QApplication

        from .settings import Settings
        from .ui.main_window import MainWindow
        from .ui.theme import palette, stylesheet
        app = QApplication.instance() or QApplication([sys.argv[0]])
        app.setPalette(palette())
        app.setStyleSheet(stylesheet())
        w = MainWindow(Settings(os.path.join(out_dir, "settings.json")))
        w.close()
        report["ui"] = "ok"
        report["ok"] = (report["photo"]["normal_convention"] == "DirectX"
                        and report["fdm"]["normal_convention"] == "DirectX")
    except Exception:  # noqa: BLE001
        report["error"] = traceback.format_exc()
    with open(os.path.join(out_dir, "self_test.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    return 0 if report["ok"] else 1


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if "--self-test" in argv:
        i = argv.index("--self-test")
        out = argv[i + 1] if len(argv) > i + 1 else os.path.join(os.getcwd(), "self-test")
        return self_test(out)
    if sys.platform == "win32":
        try:  # own taskbar icon instead of python.exe's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TengKo.SWVisualizeTextureMaker")
        except Exception:  # noqa: BLE001
            pass

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from . import APP_NAME, __version__
    from .settings import Settings, app_data_dir
    from .ui.main_window import MainWindow
    from .ui.theme import palette, stylesheet

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setPalette(palette())
    app.setStyleSheet(stylesheet())
    icon_path = _resource("texture_maker", "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    log_path = os.path.join(app_data_dir(), "error.log")

    def excepthook(etype, value, tb):
        text = "".join(traceback.format_exception(etype, value, tb))
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass
        QMessageBox.critical(None, "Unexpected error",
                             f"Something went wrong. Details were saved to:\n{log_path}\n\n{text[-1200:]}")

    sys.excepthook = excepthook

    win = MainWindow(Settings())
    win.show()
    # "Open with…" / drag a photo onto the .exe
    files = [a for a in argv[1:] if os.path.isfile(a)]
    if files:
        win.open_photo(files[0])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
