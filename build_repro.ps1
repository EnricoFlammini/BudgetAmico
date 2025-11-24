Write-Host "Building reproduction script..."
if (Test-Path "dist_repro") { Remove-Item "dist_repro" -Recurse -Force }
if (Test-Path "build_repro") { Remove-Item "build_repro" -Recurse -Force }

.venv\Scripts\pyinstaller --name "reproduce_issue" `
    --onedir `
    --clean `
    --noconfirm `
    --distpath "dist_repro" `
    --workpath "build_repro" `
    --additional-hooks-dir="hooks" `
    --collect-all yfinance `
    reproduce_issue.py

Write-Host "Build complete!"
