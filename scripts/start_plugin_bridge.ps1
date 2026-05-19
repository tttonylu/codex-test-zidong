$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonCandidates = @(
    "C:\Python314\python.exe",
    "python"
)

$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -eq "python") {
        try {
            $cmd = Get-Command python -ErrorAction Stop
            $pythonExe = $cmd.Source
            break
        } catch {
            continue
        }
    }
    if (Test-Path $candidate) {
        $pythonExe = $candidate
        break
    }
}

if (-not $pythonExe) {
    throw "Python executable not found."
}

$env:XMATRIX_NAS_BASE_URL = if ($env:XMATRIX_NAS_BASE_URL) { $env:XMATRIX_NAS_BASE_URL } else { "http://192.168.0.100:3210" }
$env:XMATRIX_BITBROWSER_BASE_URL = if ($env:XMATRIX_BITBROWSER_BASE_URL) { $env:XMATRIX_BITBROWSER_BASE_URL } else { "http://127.0.0.1:54345" }
$env:XMATRIX_PLUGIN_BRIDGE_HOST = if ($env:XMATRIX_PLUGIN_BRIDGE_HOST) { $env:XMATRIX_PLUGIN_BRIDGE_HOST } else { "127.0.0.1" }
$env:XMATRIX_PLUGIN_BRIDGE_PORT = if ($env:XMATRIX_PLUGIN_BRIDGE_PORT) { $env:XMATRIX_PLUGIN_BRIDGE_PORT } else { "54346" }
$env:XMATRIX_TERMINAL_ID = if ($env:XMATRIX_TERMINAL_ID) { $env:XMATRIX_TERMINAL_ID } else { "terminal-plugin-bridge-01" }
$env:XMATRIX_TERMINAL_HOSTNAME = if ($env:XMATRIX_TERMINAL_HOSTNAME) { $env:XMATRIX_TERMINAL_HOSTNAME } else { "localhost" }
$env:XMATRIX_OPERATOR_NAME = if ($env:XMATRIX_OPERATOR_NAME) { $env:XMATRIX_OPERATOR_NAME } else { "plugin-bridge" }
$env:PYTHONPATH = $repoRoot

Set-Location $repoRoot
& $pythonExe -m terminal_agent.run_plugin_bridge
