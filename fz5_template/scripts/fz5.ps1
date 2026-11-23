[CmdletBinding()]
param(
    [ValidateSet('help','toolchains','defconfig','menuconfig','generate','project','bitstream','matrix','check')][string]$Action='help',
    [string]$Profile='fz5d',
    [string]$ToolVersion='',
    [string]$VivadoDir='',
    [switch]$StrictVersion
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/toolchain.ps1"
$argsList = @("$PSScriptRoot/fz5.py", $Action)
if ($Action -eq 'defconfig') { $argsList += @('--profile', $Profile) }
if ($ToolVersion) { $argsList += @('--tool-version', $ToolVersion) }
if ($VivadoDir) { $argsList += @('--vivado-dir', $VivadoDir) }
if ($StrictVersion) { $argsList += '--strict-version' }
Invoke-Fz5Python @argsList
