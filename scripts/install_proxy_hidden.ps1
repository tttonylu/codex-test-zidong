$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$proxyScript = Join-Path $scriptDir "sse_proxy.py"
$shortcutDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$shortcutPath = "$shortcutDir\opencode-sse-proxy.lnk"

# Create a WScript.Shell shortcut so it runs hidden (no window)
$wshell = New-Object -ComObject WScript.Shell
$shortcut = $wshell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "python.exe"
$shortcut.Arguments = "`"$proxyScript`""
$shortcut.WorkingDirectory = (Get-Item $scriptDir).Parent.FullName
$shortcut.WindowStyle = 7  # 7 = Minimized (no window flash)
$shortcut.Description = "OpenCode SSE proxy - filters ping events"
$shortcut.Save()

Write-Host "Created startup shortcut: $shortcutPath" -ForegroundColor Green

# Start it now (hidden)
$env:UPSTREAM_URL = "https://thisis.best/v1"
$env:API_KEY = "sk-CMQXR8M9j0Gq70kvx8KpRQDuOhDKJlxFzZ2u9kvCbs4ZLrnK"
$env:LISTEN_PORT = "18765"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "python.exe"
$psi.Arguments = "`"$proxyScript`""
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.EnvironmentVariables["UPSTREAM_URL"] = $env:UPSTREAM_URL
$psi.EnvironmentVariables["API_KEY"] = $env:API_KEY
$psi.EnvironmentVariables["LISTEN_PORT"] = $env:LISTEN_PORT

$proc = [System.Diagnostics.Process]::Start($psi)
Write-Host "SSE Proxy started (PID: $($proc.Id), hidden window)" -ForegroundColor Green
Write-Host "It will auto-start on next login via startup shortcut." -ForegroundColor Green
Write-Host "You can now run opencode normally." -ForegroundColor Cyan
