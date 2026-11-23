[CmdletBinding()]
param(
    [ValidateSet('build','boot','toolchains')][string]$Action='build',
    [string]$Hardware='',
    [string]$Workspace='',
    [string]$ToolVersion='',
    [string]$VitisDir=''
)
$ErrorActionPreference='Stop'
$template = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'axu4ev_template'
. "$template/scripts/toolchain.ps1"
$argsList = @("$PSScriptRoot/build.py", $Action)
if ($Hardware) { $argsList += @('--hardware', $Hardware) }
if ($Workspace) { $argsList += @('--workspace', $Workspace) }
if ($ToolVersion) { $argsList += @('--tool-version', $ToolVersion) }
if ($VitisDir) { $argsList += @('--vitis-dir', $VitisDir) }
Invoke-Axu4evPython @argsList
