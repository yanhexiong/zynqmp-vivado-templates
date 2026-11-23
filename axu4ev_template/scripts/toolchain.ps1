# Cross-platform PowerShell compatibility helpers delegating to Python toolchain discovery.
function Get-Axu4evPython {
    $templateRoot = Split-Path -Parent $PSScriptRoot
    foreach ($rel in @('.venv/Scripts/python.exe', '.venv/bin/python')) {
        $cand = Join-Path $templateRoot $rel
        if (Test-Path -LiteralPath $cand) { return $cand }
    }
    if ($env:AXU4EV_PYTHON) { return $env:AXU4EV_PYTHON }
    if ($env:ZYNQMP_PYTHON) { return $env:ZYNQMP_PYTHON }
    foreach ($cmd in @('python3', 'python')) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { return $found.Source }
    }
    throw 'Python 3 is required.'
}

function Invoke-Axu4evPython {
    param([Parameter(ValueFromRemainingArguments)][string[]]$Arguments)
    $exe = Get-Axu4evPython
    & $exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python failed ($LASTEXITCODE)" }
}

function Enter-Axu4evToolchain {
    param(
        [Parameter(Mandatory)][ValidateSet('Vivado','Vitis')][string]$Product,
        [string]$Version = '',
        [string]$ToolDir = ''
    )
    $repoScripts = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'scripts'
    $exe = Get-Axu4evPython
    $pyCode = @"
import sys
sys.path.insert(0, r'$repoScripts')
from zynqmp_host import select_toolchain
inst = select_toolchain('$Product', tool_dir=r'$ToolDir' or None, tool_version=r'$Version' or None)
print(inst.root.as_posix())
"@
    $root = (& $exe -c $pyCode) | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0 -or !$root) { throw "Failed to locate $Product toolchain." }
    $var = if ($Product -eq 'Vivado') { 'XILINX_VIVADO' } else { 'XILINX_VITIS' }
    [Environment]::SetEnvironmentVariable($var, $root)
    $binDir = "$root/bin"
    $sep = [IO.Path]::PathSeparator
    $env:Path = "$binDir$sep$env:Path"
    if ($Product -eq 'Vitis') { $env:XILINX_SDK = $root }
    return $root
}
