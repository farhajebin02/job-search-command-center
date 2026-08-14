# Starts all three processes in separate windows.
$root = Split-Path $PSScriptRoot -Parent
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root\backend'; .venv\Scripts\python -m uvicorn api.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root\backend'; .venv\Scripts\python -m agent.worker dev"
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root\frontend'; npm run dev"
Write-Output "Started API (8000), agent worker, and frontend (3000)."
