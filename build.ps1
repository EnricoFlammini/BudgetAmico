# Build script for Budget Amico
Write-Host "Building Budget Amico..."

# Clean previous builds
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }

# Run PyInstaller
.venv\Scripts\pyinstaller --name "Budget Amico" `
    --windowed `
    --onedir `
    --clean `
    --noconfirm `
    --add-data "assets;assets" `
    --add-data "credentials.json;." `
    --icon "assets/icon.ico" `
    --hidden-import=yfinance `
    --hidden-import=python_dotenv `
    main.py

Write-Host "Build complete!"
