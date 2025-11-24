# Build script for Budget Amico using cx_Freeze
Write-Host "Building Budget Amico with cx_Freeze..."

# Clean previous builds
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

# Run cx_Freeze
.venv\Scripts\python setup.py build

Write-Host "Build complete!"
Write-Host "Executable location: build\exe.win-amd64-3.14\Budget Amico.exe"
