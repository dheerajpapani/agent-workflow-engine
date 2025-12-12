# Ensure script stops on any error
$ErrorActionPreference = "Stop"

# Resolve root directory relative to this script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = Resolve-Path "$ScriptDir\.."
$FRONTEND_DIR = Resolve-Path "$ROOT\..\frontend" -ErrorAction SilentlyContinue

# Build frontend if folder exists
if (Test-Path $FRONTEND_DIR) {
    Write-Host "Building frontend..."

    Set-Location $FRONTEND_DIR

    # Install Node dependencies
    npm ci --prefer-offline --no-audit --progress=false

    # Run frontend build
    npm run build

    Write-Host "Frontend built into backend static folder"

    # Return to previous working directory
    Set-Location $ROOT
}

# Install Python backend dependencies
pip install -r "$ROOT\requirements.txt"

# Read PORT from environment or default to 8000
$PORT = $env:PORT
if (-not $PORT) {
    $PORT = 8000
}

# Start Uvicorn server
uvicorn app.main:app --host 0.0.0.0 --port $PORT
