@echo off
REM Build SW Visualize Texture Maker locally on Windows (needs Python 3.10+ on PATH).
REM Output: dist\SW-Visualize-Texture-Maker.exe
setlocal
if not exist .venv (
    python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip
pip install -r requirements-dev.txt || goto :error
python -m pytest -q || goto :error
pyinstaller --noconfirm --clean packaging\texture_maker.spec || goto :error
echo.
echo Done: dist\SW-Visualize-Texture-Maker.exe
exit /b 0

:error
echo Build failed.
exit /b 1
