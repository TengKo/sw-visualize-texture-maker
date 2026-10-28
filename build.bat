@echo off
REM Build SW Visualize Texture Maker locally on Windows (needs Python 3.10+ on PATH and Inno Setup 6:
REM   winget install JRSoftware.InnoSetup).
REM Output: dist\SW-Visualize-Texture-Maker-Setup.exe (installer) and dist\SW-Visualize-Texture-Maker\ (app folder)
setlocal
if not exist .venv (
    python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip
pip install -r requirements-dev.txt || goto :error
python -m pytest -q || goto :error
set TM_ONEFILE=0
pyinstaller --noconfirm --clean packaging\texture_maker.spec || goto :error
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build_installer.ps1 || goto :error
echo.
echo Done: dist\SW-Visualize-Texture-Maker-Setup.exe
exit /b 0

:error
echo Build failed.
exit /b 1
