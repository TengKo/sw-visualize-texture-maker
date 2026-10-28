# Check the installer end to end: silent install -> Start menu shortcut -> --self-test on the installed app -> silent
# uninstall -> files and shortcut gone. CI runs it on every build; exit code 0 = OK.
#   powershell -ExecutionPolicy Bypass -File packaging\test_installer.ps1 [-InstallDir <folder>]
# Without -InstallDir it installs to the default per-user folder (%LOCALAPPDATA%\Programs\SW Visualize Texture Maker).
param(
    [string]$Setup = (Join-Path (Split-Path -Parent $PSScriptRoot) "dist\SW-Visualize-Texture-Maker-Setup.exe"),
    [string]$InstallDir = "",
    [string]$OutDir = (Join-Path ([IO.Path]::GetTempPath()) "tm-installer-test")
)
$ErrorActionPreference = "Stop"
$appName = "SW Visualize Texture Maker"

New-Item -ItemType Directory -Force $OutDir | Out-Null
$setupArgs = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/LOG=`"$OutDir\install.log`"")
if ($InstallDir) { $setupArgs += "/DIR=`"$InstallDir`"" }
else { $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\$appName" }
$exe = Join-Path $InstallDir "SW-Visualize-Texture-Maker.exe"
$shortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "$appName.lnk"

Write-Host "Installing $Setup"
$p = Start-Process -FilePath $Setup -ArgumentList $setupArgs -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "Installer failed (exit code $($p.ExitCode)), see $OutDir\install.log" }
if (-not (Test-Path $exe)) { throw "Installed app not found at $exe" }
if (-not (Test-Path $shortcut)) { throw "Start menu shortcut not found at $shortcut" }

Write-Host "Self-testing $exe"
$p = Start-Process -FilePath $exe -ArgumentList "--self-test", "`"$OutDir\selftest`"" -Wait -PassThru
Get-Content (Join-Path $OutDir "selftest\self_test.json")
if ($p.ExitCode -ne 0) { throw "Self-test failed (exit code $($p.ExitCode))" }

Write-Host "Uninstalling"
$p = Start-Process -FilePath (Join-Path $InstallDir "unins000.exe") -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "Uninstaller failed (exit code $($p.ExitCode))" }
# The uninstaller hands off to a copy of itself in %TEMP%, so give it time to finish removing files.
$deadline = (Get-Date).AddSeconds(120)
while (((Test-Path $exe) -or (Test-Path $shortcut)) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
if (Test-Path $exe) { throw "Uninstall left $exe behind" }
if (Test-Path $shortcut) { throw "Uninstall left $shortcut behind" }

Write-Host "Installer test passed: installed to $InstallDir, self-test OK, uninstalled cleanly."
