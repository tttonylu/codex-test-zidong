$procs = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "sse_proxy"
}

if ($procs) {
    $procs | Stop-Process -Force
    Write-Host "SSE Proxy stopped." -ForegroundColor Green
} else {
    Write-Host "No SSE Proxy process found." -ForegroundColor Yellow
}
