[CmdletBinding()]
param(
    [string[]]$Profiles=@('fz5c','minimal','full'),
    [string]$ToolVersion='',
    [string]$VivadoDir='',
    [switch]$StrictVersion
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/toolchain.ps1"
$Profiles = @($Profiles | ForEach-Object { $_ -split ',' })
$argsList = @("$PSScriptRoot/fz5.py", 'matrix', '--profiles') + $Profiles
if ($ToolVersion) { $argsList += @('--tool-version', $ToolVersion) }
if ($VivadoDir) { $argsList += @('--vivado-dir', $VivadoDir) }
if ($StrictVersion) { $argsList += '--strict-version' }
Invoke-Fz5Python @argsList
