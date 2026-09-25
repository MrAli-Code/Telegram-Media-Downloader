# build_exe.ps1
# ساخت EXE با PyInstaller (One Folder) و سپس بسته ZIP.
#
# طرز استفاده:
#   .\build\build_exe.ps1            (نسخه One Folder)
#   .\build\build_exe.ps1 -OneFile   (نسخه تک فایل)
#   .\build\build_exe.ps1 -Clean     (پاک‌سازی میانی)

param(
    [switch]$OneFile,
    [switch]$Clean
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONIOENCODING = "utf-8"

# مسیر Python پروژه (venv)
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "python پروژه پیدا نشد؛ ابتدا اجرا کنید: uv venv --python 3.12 .venv" -ForegroundColor Red
    exit 1
}

if ($Clean) {
    Write-Host "پاک‌سازی میانی..."
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build\pyi, dist\TelegramDownloader
}

Write-Host "تولید آیکون برنامه..."
& $Py scripts\make_icon.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($OneFile) {
    $Spec = "build\telegram_downloader_onefile.spec"
    $OutDir = "dist"
} else {
    $Spec = "build\telegram_downloader.spec"
    $OutDir = "dist"
}

Write-Host "ساخت EXE با $Spec ..."
& $Py -m PyInstaller --noconfirm --clean --distpath $OutDir --workpath build\pyi $Spec
if ($LASTEXITCODE -ne 0) { Write-Host "خطا در ساخت EXE" -ForegroundColor Red; exit $LASTEXITCODE }

Write-Host "ساخت ZIP..."
$ZipName = Join-Path $OutDir "TelegramDownloader-Windows.zip"
if (Test-Path $ZipName) { Remove-Item $ZipName }
if ($OneFile) {
    $Target = Get-ChildItem "$OutDir\*.exe" | Select-Object -First 1
    if ($Target) { Copy-Item $Target.FullName "TelegramDownloader.exe" }
    Compress-Archive -Path "TelegramDownloader.exe" -DestinationPath $ZipName
    Remove-Item "TelegramDownloader.exe"
} else {
    Compress-Archive -Path "$OutDir\TelegramDownloader" -DestinationPath $ZipName
}

Write-Host "خروجی آماده است:" -ForegroundColor Green
Get-ChildItem $ZipName, "$OutDir\TelegramDownloader\TelegramDownloader.exe" -ErrorAction SilentlyContinue | Select-Object FullName, Length