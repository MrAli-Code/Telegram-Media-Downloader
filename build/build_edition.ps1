# build_edition.ps1 - Build one edition (personal/public) of Telegram Downloader.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File build\build_edition.ps1 -Edition personal
#   powershell -ExecutionPolicy Bypass -File build\build_edition.ps1 -Edition public -Clean
#
# Steps:
#   1) Generate config/_build_info.py for the edition (source of truth: build_profiles/**)
#   2) Build a single-file EXE via PyInstaller (build/telegram_downloader_onefile.spec)
#   3) Compile the Inno Setup installer into release/<folder>/
#
# Output:
#   release/<folder>/<exe_name>.exe
#   release/<folder>/<exe_name>-Setup.exe

param(
    [ValidateSet("personal", "public")]
    [string]$Edition = "personal",
    [switch]$Clean
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONIOENCODING = "utf-8"

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[build] venv python not found: $Py" -ForegroundColor Red
    exit 1
}

Write-Host "[build] edition = $Edition"

# --- 1) build info -------------------------------------------------------
& $Py scripts\generate_build_info.py --profile $Edition
if ($LASTEXITCODE -ne 0) {
    Write-Host "[build] generate_build_info failed" -ForegroundColor Red
    exit $LASTEXITCODE
}

# --- 2) read profile / version -------------------------------------------
$ProfilePath = Join-Path $Root "build_profiles\$Edition.json"
if (-not (Test-Path $ProfilePath)) {
    Write-Host "[build] profile not found: $ProfilePath" -ForegroundColor Red
    exit 1
}
$Profile = Get-Content -LiteralPath $ProfilePath -Raw -Encoding UTF8 | ConvertFrom-Json
$ExeName = [string]$Profile.exe_name
$Folder = [string]$Profile.folder
$DisplayName = [string]$Profile.display_name
$AppId = [string]$Profile.app_id_guid

$VersionLine = (& $Py -c "from config.version import APP_VERSION; print(APP_VERSION)" | Where-Object { $_ -match '^\d+\.\d+\.\d+$' } | Select-Object -Last 1)
if (-not $VersionLine) { $VersionLine = "1.0.1" }
$Version = $VersionLine.Trim()

$ReleaseRoot = Join-Path $Root ("release\" + $Folder)
New-Item -ItemType Directory -Force -Path $ReleaseRoot | Out-Null

if ($Clean) {
    Write-Host "[build] cleaning intermediates..."
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Root "build\pyi")
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Root "build\staging")
    Get-ChildItem -Path $ReleaseRoot -Filter *.exe -ErrorAction SilentlyContinue | Remove-Item -Force
}

# --- 3) icon -------------------------------------------------------------
& $Py scripts\make_icon.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# --- 4) PyInstaller one-file EXE ----------------------------------------
$Staging = Join-Path $Root "build\staging"
$ExeStaged = Join-Path $Staging "$ExeName.exe"
Write-Host "[build] PyInstaller -> $ExeName.exe"
& $Py -m PyInstaller --noconfirm --clean --distpath $Staging --workpath (Join-Path $Root "build\pyi") build\telegram_downloader_onefile.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "[build] PyInstaller failed" -ForegroundColor Red
    exit $LASTEXITCODE
}
if (-not (Test-Path $ExeStaged)) {
    Write-Host "[build] staged EXE not found: $ExeStaged" -ForegroundColor Red
    exit 1
}
$ExeOut = Join-Path $ReleaseRoot "$ExeName.exe"
try {
    Copy-Item -LiteralPath $ExeStaged -Destination $ExeOut -Force -ErrorAction Stop
} catch {
    Write-Host "[build] cannot replace $ExeOut" -ForegroundColor Red
    Write-Host "[build] close the running application then re-run the build." -ForegroundColor Red
    exit 1
}
Write-Host "[build] EXE ready: $ExeOut" -ForegroundColor Green

# --- 5) Inno Setup installer ---------------------------------------------
$ISCC = "C:\Users\Ali\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $ISCC)) {
    Write-Host "[build] ISCC not found, skipping installer" -ForegroundColor Yellow
} else {
    $SetupBase = "$ExeName-Setup"
    $IssArgs = @(
        "installer\setup.iss",
        "/DAppName=$DisplayName",
        "/DAppVersion=$Version",
        "/DAppExeName=$ExeName.exe",
        "/DAppId=$AppId",
        "/DAppFolderName=$Folder",
        "/DAppPublisher=Ali Khanmohammadi",
        "/DAppPublisherURL=https://alikhanmohammadi.ir/",
        "/DAppSupportURL=https://alikhanmohammadi.ir/",
        "/DAppUpdatesURL=https://alikhanmohammadi.ir/",
        "/DOutputBaseFilename=$SetupBase",
        "/DBuildDir=$ExeOut",
        "/DOutputDir=$ReleaseRoot"
    )
    Write-Host "[build] Inno Setup -> $SetupBase.exe"
    & $ISCC $IssArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[build] Inno Setup failed" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "[build] done." -ForegroundColor Green
Get-ChildItem -Path $ReleaseRoot -Filter *.exe | Select-Object Name, Length | Format-Table -AutoSize

# Keep the tree's dev default = Personal after a Public build, so running
# `python app.py` locally keeps the embedded-credentials experience.
if ($Edition -eq "public") {
    Write-Host "[build] restoring dev default (personal _build_info)..."
    & $Py scripts\generate_build_info.py --profile personal | Out-Null
}