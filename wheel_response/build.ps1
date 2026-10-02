param([string]$Uv4Path, [switch]$Baseline, [switch]$Rebuild)
$ErrorActionPreference = 'Stop'
$arguments = @((Join-Path $PSScriptRoot 'tools\build_firmware.py'))
if ($Uv4Path) { $arguments += @('--uv4', $Uv4Path) }
if ($Baseline) { $arguments += '--baseline' }
if ($Rebuild) { $arguments += '--rebuild' }
& py -3 @arguments
exit $LASTEXITCODE
