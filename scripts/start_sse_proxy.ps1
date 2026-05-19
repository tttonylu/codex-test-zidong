$port = 18765
$upstream = "https://thisis.best/v1"
$stripPrefix = "/v1"
$key = "sk-CMQXR8M9j0Gq70kvx8KpRQDuOhDKJlxFzZ2u9kvCbs4ZLrnK"

Write-Host "Starting SSE Proxy on http://127.0.0.1:$port -> $upstream"
Write-Host "Run opencode in another terminal after this starts."

$env:UPSTREAM_URL = $upstream
$env:STRIP_PREFIX = $stripPrefix
$env:API_KEY = $key
$env:LISTEN_PORT = $port

python "$PSScriptRoot\sse_proxy.py"

if (-not $?) {
    Write-Host "Failed to start. Make sure Python is installed." -ForegroundColor Red
    exit 1
}
