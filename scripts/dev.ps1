# Starts all three processes in separate windows.
#
# Each one tees its output to a log file as well as its window. Without this
# the worker's output lives only in its console, so nothing that goes wrong
# mid-conversation can be read back afterwards -- and the agent's failures are
# exactly the ones you cannot catch in the moment.
$root = Split-Path $PSScriptRoot -Parent

# Close any windows left over from a previous run FIRST. Tee-Object holds its
# log file open for as long as its console lives, and a -NoExit window outlives
# the process it ran. Start a second worker while the old window is still open
# and its Tee cannot open the locked log, which breaks the output pipe and
# kills the worker seconds after it registers -- a clean startup log followed
# by DuplexClosed, with nothing pointing at the real cause.
$stale = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -match 'agent\.worker|uvicorn api\.main|npm run dev' -and
                 $_.ProcessId -ne $PID }
foreach ($p in $stale) {
  Write-Output "closing previous window $($p.ProcessId)"
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
if ($stale) { Start-Sleep -Seconds 2 }

# Then any processes those windows orphaned, so port 8000 is free. Scoped to
# python.exe deliberately: matching on command line alone also matches whatever
# shell invoked this script, since these very patterns appear in its arguments.
# Unscoped, this line kills its own caller.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'uvicorn api\.main|agent\.worker' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# `next dev` outlives the console that launched it, and rather than failing it
# quietly starts on 3001 and tells you the old server still owns 3000. The
# browser then keeps talking to a build from before your changes.
Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
  Where-Object { $_.CommandLine -match 'next[\\/]dist[\\/]bin[\\/]next|next dev' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# Logs append rather than truncate. Restarting used to erase the run you were
# trying to diagnose -- the evidence for a bug reported minutes earlier was
# gone before anyone read it. A banner separates runs instead.
$banner = "`n===== run started $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ====="
foreach ($log in "$root\backend\uvicorn.log", "$root\backend\worker.log",
                 "$root\frontend\next.log") {
  Add-Content -Path $log -Value $banner -Encoding utf8
}

# No --reload. Its reloader killed this server twice on this machine -- once on
# a test edit, once on a core/ edit -- and each time left nothing listening on
# 8000, which surfaces as "Failed to fetch" in the browser. That matches the
# venv spawn quirk noted in api/main.py. The agent worker already needs a manual
# restart (this SDK has no in-process auto-reload), so the loop is consistent:
# change backend code, re-run this script.
Start-Process powershell -ArgumentList "-NoExit","-Command",
  "Set-Location '$root\backend'; .venv\Scripts\python -m uvicorn api.main:app --port 8000 2>&1 | Tee-Object -Append -FilePath '$root\backend\uvicorn.log'"

Start-Process powershell -ArgumentList "-NoExit","-Command",
  "Set-Location '$root\backend'; .venv\Scripts\python -m agent.worker dev 2>&1 | Tee-Object -Append -FilePath '$root\backend\worker.log'"

Start-Process powershell -ArgumentList "-NoExit","-Command",
  "Set-Location '$root\frontend'; npm run dev 2>&1 | Tee-Object -Append -FilePath '$root\frontend\next.log'"

Write-Output "Started API (8000), agent worker, and frontend (3000)."
Write-Output "Logs: backend\uvicorn.log, backend\worker.log, frontend\next.log"
