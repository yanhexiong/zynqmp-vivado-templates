[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Port,
    [ValidateSet('Capture','Jtag')][string]$Mode='Capture',
    [string]$Hardware='',
    [string]$Workspace='',
    [string]$Server='tcp:127.0.0.1:3121',
    [string]$Cable='*',
    [int]$TimeoutSeconds=120,
    [string]$PlEcho='',
    [double]$EchoDelayMs=15,
    [string]$ToolVersion='',
    [string]$VitisDir=''
)
$ErrorActionPreference='Stop'
$template = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'fz5_template'
. "$template/scripts/toolchain.ps1"
$argsList = @("$PSScriptRoot/serial_test.py", '--console', $Port, '--timeout', "$TimeoutSeconds", '--echo-delay-ms', "$EchoDelayMs")
if ($Mode -eq 'Jtag') { $argsList += @('--jtag', '--server', $Server, '--cable', $Cable) }
if ($Hardware) { $argsList += @('--hardware', $Hardware) }
if ($Workspace) { $argsList += @('--workspace', $Workspace) }
if ($PlEcho) { $argsList += @('--pl-echo', $PlEcho) }
if ($ToolVersion) { $argsList += @('--tool-version', $ToolVersion) }
if ($VitisDir) { $argsList += @('--vitis-dir', $VitisDir) }
$uv = Get-Command uv -ErrorAction SilentlyContinue | Select-Object -First 1
if ($uv) {
    & $uv.Source run --with pyserial python @argsList
    if ($LASTEXITCODE -ne 0) { throw "Serial test failed ($LASTEXITCODE)" }
} else {
    Invoke-Fz5Python @argsList
}
