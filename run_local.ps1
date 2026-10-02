# PowerShell script to run WDOS locally
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Activate virtual environment
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[!] Virtual environment not found. Please create it first: py -3.11 -m venv .venv" -ForegroundColor Red
    exit 1
}

# Load .env file into environment variables
$EnvPath = Join-Path $ScriptDir ".env"
if (Test-Path $EnvPath) {
    Write-Host "[*] Loading configuration from .env..." -ForegroundColor Cyan
    Get-Content $EnvPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not ($line.StartsWith("#")) -and ($line -match "^([^=]+)=(.*)$")) {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Strip quotes if present
            if ($value.StartsWith('"') -and $value.EndsWith('"')) {
                $value = $value.Substring(1, $value.Length - 2)
            } elseif ($value.StartsWith("'") -and $value.EndsWith("'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
} else {
    Write-Host "[*] No .env found; using default local development settings." -ForegroundColor Yellow
}

# Ensure critical defaults for local HTTP execution
$Port = if ($env:PORT) { $env:PORT } else { "8080" }
if (-not $env:PYTHONUTF8) { $env:PYTHONUTF8 = "1" }
if (-not $env:DJANGO_DEBUG) { $env:DJANGO_DEBUG = "1" }
if (-not $env:WDOS_SECURE_COOKIES) { $env:WDOS_SECURE_COOKIES = "0" }
if (-not $env:WDOS_PUBLIC_ORIGIN) { $env:WDOS_PUBLIC_ORIGIN = "http://127.0.0.1:$Port" }
if (-not $env:DJANGO_ALLOWED_HOSTS) { $env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost" }

Write-Host "`n[*] Applying database migrations..." -ForegroundColor Cyan
& $VenvPython manage.py migrate --noinput

Write-Host "`n[*] Seeding system roles..." -ForegroundColor Cyan
& $VenvPython manage.py seed_roles

Write-Host "`n[*] Verifying local dev accounts..." -ForegroundColor Cyan
& $VenvPython scripts\create_dev_user.py

Write-Host "`n=======================================================" -ForegroundColor Green
Write-Host "  WDOS Local Development Server Ready!" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "  App Home:       http://127.0.0.1:$Port/" -ForegroundColor White
Write-Host "  Sign In:        http://127.0.0.1:$Port/auth/login/" -ForegroundColor White
Write-Host "  Admin Panel:    http://127.0.0.1:$Port/admin/" -ForegroundColor White
Write-Host "  Health API:     http://127.0.0.1:$Port/health" -ForegroundColor White
Write-Host "-------------------------------------------------------" -ForegroundColor Gray
Write-Host "  Pre-configured Accounts:" -ForegroundColor Yellow
Write-Host "  - Member: member@example.org / DevMember@2026!Wdos" -ForegroundColor Yellow
Write-Host "  - Admin:  admin@example.org  / DevAdmin@2026!Wdos" -ForegroundColor Yellow
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "Starting Django development server at 127.0.0.1:$Port (Ctrl+C to stop)...`n" -ForegroundColor Cyan

& $VenvPython manage.py runserver "127.0.0.1:$Port"

