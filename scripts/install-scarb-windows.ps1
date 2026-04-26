# 将 Scarb 安装到 %LOCALAPPDATA%\Programs\scarb 并追加到「用户」PATH（需 PowerShell）。
# 官方说明: https://docs.swmansion.com/scarb/download.html#windows
# 用法: 右键「使用 PowerShell 运行」或在仓库根目录执行:
#   powershell -ExecutionPolicy Bypass -File scripts/install-scarb-windows.ps1

$ErrorActionPreference = "Stop"
$version = "2.16.1"
$installRoot = Join-Path $env:LOCALAPPDATA "Programs\scarb"
$binPath = Join-Path $installRoot "bin"
$zipUrl = "https://github.com/software-mansion/scarb/releases/download/v$version/scarb-v$version-x86_64-pc-windows-msvc.zip"
$zipFile = Join-Path $env:TEMP "scarb-v$version-win.zip"
$extractRoot = Join-Path $env:TEMP "scarb_extract_$version"

Write-Host "Downloading Scarb v$version ..."
Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing

if (Test-Path $extractRoot) { Remove-Item -Recurse -Force $extractRoot }
Expand-Archive -LiteralPath $zipFile -DestinationPath $extractRoot -Force

$inner = Get-ChildItem -LiteralPath $extractRoot -Directory | Select-Object -First 1
if (-not $inner) { throw "Unexpected zip layout" }
$srcBin = Join-Path $inner.FullName "bin"
if (-not (Test-Path (Join-Path $srcBin "scarb.exe"))) { throw "scarb.exe not found" }

if (Test-Path $installRoot) { Remove-Item -Recurse -Force $installRoot }
New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
Copy-Item -Path $srcBin -Destination $binPath -Recurse -Force

Write-Host "Installed: $binPath"
& (Join-Path $binPath "scarb.exe") --version

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notmatch [regex]::Escape($binPath)) {
  $newPath = if ([string]::IsNullOrEmpty($userPath)) { $binPath } else { "$userPath;$binPath" }
  [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
  Write-Host "Appended to User PATH. Open a NEW terminal for Cursor/IDE to pick it up."
} else {
  Write-Host "User PATH already contains scarb bin."
}
