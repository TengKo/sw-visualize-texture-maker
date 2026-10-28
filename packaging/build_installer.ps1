# Build dist\SW-Visualize-Texture-Maker-Setup.exe from the PyInstaller folder build (dist\SW-Visualize-Texture-Maker\).
# Needs Inno Setup 6 (free): winget install JRSoftware.InnoSetup
#   powershell -ExecutionPolicy Bypass -File packaging\build_installer.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $root "dist\SW-Visualize-Texture-Maker\SW-Visualize-Texture-Maker.exe"))) {
    throw "Build the app folder first: set TM_ONEFILE=0, then pyinstaller --noconfirm packaging\texture_maker.spec"
}

# Inno Setup installs per-user (winget) or per-machine (the regular installer, Chocolatey); look in both places.
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1
if (-not $iscc) {
    $places = @(${env:ProgramFiles(x86)}, $env:ProgramFiles, (Join-Path $env:LOCALAPPDATA "Programs")) | Where-Object { $_ }
    $iscc = Get-ChildItem ($places | ForEach-Object { Join-Path $_ "Inno Setup*\ISCC.exe" }) -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName -First 1
}
if (-not $iscc) { throw "Inno Setup not found. Install it with: winget install JRSoftware.InnoSetup" }

$init = Get-Content (Join-Path $root "texture_maker\__init__.py") -Raw
if ($init -notmatch '__version__\s*=\s*["'']([^"'']+)["'']') { throw "Couldn't read __version__ from texture_maker\__init__.py" }
$version = $Matches[1]

Write-Host "Building installer for version $version with $iscc"
& $iscc "/DAppVersion=$version" (Join-Path $PSScriptRoot "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed (exit code $LASTEXITCODE)" }
