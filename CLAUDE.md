# CLAUDE.md: SW Visualize Texture Maker

Windows desktop app (Python + PySide6) that turns a photo, or a procedural preset, into a SOLIDWORKS Visualize
appearance (`.svap`). Open source (MIT), public repo `TengKo/sw-visualize-texture-maker`. The owner works on
Windows 10 and is a designer moving into development: explain decisions in plain language.

## Commands
```bash
pip install -r requirements-dev.txt        # numpy, scipy, Pillow, PySide6, pytest, pyinstaller
python run.py                              # run the app
python -m pytest -q                        # engine tests (fast, no GUI)
python run.py --self-test <dir>            # engine + builds MainWindow, writes <dir>/self_test.json, exit 0 = OK
pyinstaller --noconfirm --clean packaging/texture_maker.spec          # one-file exe -> dist/
set TM_ONEFILE=0 && pyinstaller --noconfirm packaging/texture_maker.spec   # portable folder (PowerShell: $env:TM_ONEFILE="0")
```
Headless GUI checks (Linux/CI): `QT_QPA_PLATFORM=offscreen`, then `widget.grab().save(...)` for screenshots.

## Layout
- `texture_maker/engine/`: pure numpy/scipy/Pillow, **no Qt imports** (keeps it testable and reusable).
  - `photo.py`: `process_photo(img, size, seam_band, progress, cancel)` → `PhotoResult(height, base_srgb, crop, …)`
  - `fdm.py`: `generate_fdm(size, layers, seed, bead_shape, imperfections)`: 3D-print layer height field (px units)
  - `normal.py`: `height_to_normal` (DirectX), `auto_strength`, `normal_convention`, `tilt_stats`, `resize_height`
  - `preview.py`: `render_sphere`: CPU lit-sphere preview (approximate, not Visualize's renderer)
  - `svap.py`: `build_svap`, `verify_svap`, `write_dds`, template handling; `template/Material.xml` = built-in template
- `texture_maker/ui/`: PySide6. `main_window.py` (navigation + generate/save jobs), `pages.py` (Home, Processing,
  Saved), `editor.py` (photo editor + 3D print preset), `widgets.py`, `dialogs.py`, `theme.py` (colors + QSS),
  `workers.py` (`run_async`, `LatestJob` = newest-request-wins background jobs), `icons.py` (inline SVG).
- `texture_maker/settings.py`: JSON settings + recent items in `%APPDATA%\SW Visualize Texture Maker\`.
- `packaging/texture_maker.spec`: PyInstaller recipe (drops unused Qt modules to save size).
- `.github/workflows/build.yml`: Windows CI: tests → build exe + portable zip → run `--self-test` on the exe →
  upload artifact; tags `v*` publish a GitHub Release.

## .svap rules (verified working in Visualize; don't break)
- ZIP in OPC layout: `Material.xml`, `Assets/<imageGuid>.dds`, `Thumb.png` + `Thumbnails/<matGuid>.thb.png`
  (same 128×128 sphere), `Thumbnails/<texGuid>.thb.png`, `_rels/.rels`, `[Content_Types].xml`,
  `package/services/metadata/core-properties/<32hex>.psmdcp`. `.rels`/psmdcp/Content_Types are UTF-8 **with BOM**;
  `Material.xml` has **no BOM and CRLF** line endings.
- New appearances copy the template `Material.xml` and change ONLY: the 3 GUIDs (material, texture node, image),
  names, `<BaseColor>` + albedo ParameterValue (sRGB 0–1), `<PbrRoughness>` + roughness ParameterValue +
  `<PbrGlossiness>` (= 1 − roughness), optional metallic, TileS/TileT inside `TextureOperationsList`,
  `IsPredefined=false`. Leave `EntrySet` values alone (type defaults).
- DDS: uncompressed A8R8G8B8, no mipmaps, BGRA, header flags 0x100F, pixel-format flags 0x41, caps 0x1000.
- Normal maps: tangent space, seamless, **DirectX** (green = down), checked with the curl test in
  `normal_convention`. Reference strength: Visualize's MT11050 map has tilt p50 0.19 / p99 0.53.
- Always run `verify_svap()` on output in tests. Color/roughness *texture* maps are not supported yet: get a sample
  `.svap` that uses those slots first and copy its exact XML.

## Image pipeline notes
- Photo seams: square crop with a 120 px margin cross-faded over the opposite edge (variance-preserving).
  Do **not** use Poisson / "periodic component" smoothing: it flattens the seam rows.
- Photo sigmas were tuned on a 1720 px photo and scale with photo size; photos over 2600 px are downscaled first.
- The photo is always processed at 2048 px; a 1024 export resizes the height and re-runs `auto_strength`.
- The 3D print preview renders at 512 px with the same seed. The pattern differs slightly from the 2048 export,
  but the look matches.

## UI conventions
- Dark graphite theme from the design flow: bg `#16181B`, surface `#1C1F23`, border `#2C3036`, text `#E8EAED`,
  muted `#9AA1AB`, accent amber `#F2A93B` (text on accent `#1A1305`), success `#5CC48A`. Colors live in `theme.C`.
- Heavy work never runs on the UI thread: use `run_async` / `LatestJob`.
- Keep wording plain and short ("bump map", not "tangent-space normal map", in the UI).

## Roadmap ideas
Batch mode (drop several photos) · interactive 3D preview (rotate + light) · color/roughness maps (needs a sample
`.svap`) · 3D-print top-surface (diagonal infill) preset · code signing to avoid the SmartScreen prompt.

## Releasing
Bump `__version__` in `texture_maker/__init__.py` and `pyproject.toml`, commit, then `git tag vX.Y.Z && git push --tags`.
CI builds and attaches `SW-Visualize-Texture-Maker.exe` and `SW-Visualize-Texture-Maker-portable.zip` to the release.
