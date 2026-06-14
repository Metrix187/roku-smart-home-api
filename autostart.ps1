# Idempotently (re)start the bulb dashboard + token watchdog.
# Invoked at logon by the hidden .vbs in the Startup folder. Safe to run anytime:
# it only starts a service that isn't already running. Uses pythonw.exe so there
# are no console windows.
$dir = "D:\lightbulb sniff"
$pyw = "C:\Python314\pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = "C:\Windows\py.exe" }

# --- Dashboard (port 8765): start only if nothing is already listening there ---
if (-not (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)) {
    $p = Start-Process -FilePath $pyw -ArgumentList 'dashboard.py' -WorkingDirectory $dir -WindowStyle Hidden `
         -RedirectStandardOutput "$dir\capture\dash_stdout.log" -RedirectStandardError "$dir\capture\dash_stderr.log" -PassThru
    $p.Id | Set-Content "$dir\capture\dash.pid"
    "dashboard started (PID $($p.Id))"
} else {
    "dashboard already running (8765 in use) - skipped"
}

# --- Watchdog: start only if the recorded PID isn't a live python process ---
$alive = $false
$wp = Get-Content "$dir\capture\watch.pid" -ErrorAction SilentlyContinue
if ($wp) {
    $pr = Get-Process -Id $wp -ErrorAction SilentlyContinue
    if ($pr -and $pr.ProcessName -in 'py', 'pythonw', 'python') { $alive = $true }
}
if (-not $alive) {
    $p = Start-Process -FilePath $pyw -ArgumentList 'token_watch.py', '600' -WorkingDirectory $dir -WindowStyle Hidden `
         -RedirectStandardOutput "$dir\capture\watch_stdout.log" -RedirectStandardError "$dir\capture\watch_stderr.log" -PassThru
    $p.Id | Set-Content "$dir\capture\watch.pid"
    "watchdog started (PID $($p.Id))"
} else {
    "watchdog already running (PID $wp) - skipped"
}
