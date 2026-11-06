#Requires -Version 5.1
<#
.SYNOPSIS
    Bootstrap installer for intune-visual-doc on Windows.

.DESCRIPTION
    Designed for a relatively clean Windows 10/11 workstation.

    Performs:
      - Basic Windows validation
      - winget detection
      - Git installation/check
      - Python installation/check
      - Repository clone/update
      - Python virtual environment creation
      - pip/setuptools/wheel upgrade
      - Project dependency installation
      - Playwright Chromium installation
      - Basic installation validation

.EXAMPLE
    PowerShell -ExecutionPolicy Bypass -File .\Install-IntuneVisualDoc.ps1

.EXAMPLE
    .\Install-IntuneVisualDoc.ps1 -InstallPath "C:\Tools\intune-visual-doc"

.NOTES
    Repository:
    https://github.com/leifdavisson/intune-visual-doc.git
#>

[CmdletBinding()]
param (
    [string]$InstallPath = "$env:USERPROFILE\intune-visual-doc",

    [string]$Repository = "https://github.com/leifdavisson/intune-visual-doc.git",

    [switch]$ForceRebuildVenv
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkGray
    Write-Host " $Message" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkGray
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-WarningMessage {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Fail {
    param([string]$Message)

    Write-Host ""
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

function Test-Command {
    param([string]$Command)

    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

function Refresh-Path {
    # Refresh PATH after winget installs software without requiring
    # the user to close/reopen PowerShell.

    $machinePath = [Environment]::GetEnvironmentVariable(
        "Path",
        [EnvironmentVariableTarget]::Machine
    )

    $userPath = [Environment]::GetEnvironmentVariable(
        "Path",
        [EnvironmentVariableTarget]::User
    )

    $env:Path = "$machinePath;$userPath"
}

# ------------------------------------------------------------
# Banner
# ------------------------------------------------------------

Clear-Host

Write-Host @"

==============================================
       Intune Visual Doc - Windows Setup
==============================================

 Repository:
 $Repository

 Install location:
 $InstallPath

"@ -ForegroundColor Cyan

# ------------------------------------------------------------
# Check Operating System
# ------------------------------------------------------------

Write-Step "Checking Windows environment"

if ($env:OS -ne "Windows_NT") {
    Fail "This installer is intended for Windows."
}

Write-Success "Windows detected"

Write-Host "PowerShell: $($PSVersionTable.PSVersion)"

# ------------------------------------------------------------
# Check Winget
# ------------------------------------------------------------

Write-Step "Checking Windows Package Manager"

if (-not (Test-Command "winget")) {

    Write-WarningMessage "winget was not detected."

    Write-Host ""
    Write-Host "Install or update 'App Installer' from the Microsoft Store,"
    Write-Host "then run this script again."
    Write-Host ""

    Fail "Windows Package Manager (winget) is required for automatic prerequisite installation."
}

Write-Success "winget detected"

winget --version

# ------------------------------------------------------------
# Git
# ------------------------------------------------------------

Write-Step "Checking Git"

if (-not (Test-Command "git")) {

    Write-Host "Git is not installed. Installing Git for Windows..."

    winget install `
        --id Git.Git `
        -e `
        --source winget `
        --accept-package-agreements `
        --accept-source-agreements

    if ($LASTEXITCODE -ne 0) {
        Fail "Git installation failed with exit code $LASTEXITCODE."
    }

    Refresh-Path
}

if (-not (Test-Command "git")) {
    Fail "Git was installed but cannot be found in PATH."
}

Write-Success "Git available"

git --version

# ------------------------------------------------------------
# Python
# ------------------------------------------------------------

Write-Step "Checking Python"

if (-not (Test-Command "python")) {

    Write-Host "Python is not installed. Installing Python 3.12..."

    winget install `
        --id Python.Python.3.12 `
        -e `
        --source winget `
        --accept-package-agreements `
        --accept-source-agreements

    if ($LASTEXITCODE -ne 0) {
        Fail "Python installation failed with exit code $LASTEXITCODE."
    }

    Refresh-Path
}

if (-not (Test-Command "python")) {
    Fail "Python was installed but cannot be found in PATH."
}

Write-Success "Python available"

python --version

# ------------------------------------------------------------
# Verify pip
# ------------------------------------------------------------

Write-Step "Checking pip"

python -m pip --version

if ($LASTEXITCODE -ne 0) {

    Write-WarningMessage "pip was not available. Attempting ensurepip..."

    python -m ensurepip --upgrade

    if ($LASTEXITCODE -ne 0) {
        Fail "Unable to initialize pip."
    }
}

Write-Success "pip available"

# ------------------------------------------------------------
# Clone/update repository
# ------------------------------------------------------------

Write-Step "Preparing intune-visual-doc repository"

$GitDirectory = Join-Path $InstallPath ".git"

if (Test-Path $GitDirectory) {

    Write-Success "Existing repository detected"

    Push-Location $InstallPath

    try {
        Write-Host "Fetching repository updates..."

        git fetch

        if ($LASTEXITCODE -ne 0) {
            Write-WarningMessage "git fetch failed. Continuing with existing repository."
        }
        else {
            Write-Host "Updating working tree..."

            git pull --ff-only

            if ($LASTEXITCODE -ne 0) {
                Write-WarningMessage "Automatic git pull could not be completed."
                Write-WarningMessage "Local changes may exist. They have NOT been overwritten."
            }
            else {
                Write-Success "Repository updated"
            }
        }
    }
    finally {
        Pop-Location
    }
}
elseif (Test-Path $InstallPath) {

    Fail "Install path already exists but does not appear to be a Git repository: $InstallPath"

}
else {

    Write-Host "Cloning repository..."

    git clone $Repository $InstallPath

    if ($LASTEXITCODE -ne 0) {
        Fail "Unable to clone repository."
    }

    Write-Success "Repository cloned"
}

# ------------------------------------------------------------
# Enter project
# ------------------------------------------------------------

Set-Location $InstallPath

Write-Host ""
Write-Host "Working directory:" -ForegroundColor DarkGray
Write-Host (Get-Location)

# ------------------------------------------------------------
# Virtual environment
# ------------------------------------------------------------

Write-Step "Preparing Python virtual environment"

$VenvPath   = Join-Path $InstallPath ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

if ($ForceRebuildVenv -and (Test-Path $VenvPath)) {

    Write-Host "Removing existing virtual environment..."

    Remove-Item `
        -Path $VenvPath `
        -Recurse `
        -Force
}

if (-not (Test-Path $VenvPython)) {

    Write-Host "Creating Python virtual environment..."

    python -m venv .venv

    if ($LASTEXITCODE -ne 0) {
        Fail "Unable to create Python virtual environment."
    }

    Write-Success "Virtual environment created"
}
else {
    Write-Success "Existing virtual environment detected"
}

if (-not (Test-Path $VenvPython)) {
    Fail "Virtual environment Python executable was not created."
}

# ------------------------------------------------------------
# IMPORTANT
#
# We intentionally call .venv\Scripts\python.exe directly.
#
# This means the installer does NOT depend on:
#     Activate.ps1
#
# and doesn't care about PowerShell execution policy.
# ------------------------------------------------------------

Write-Step "Upgrading Python packaging tools"

& $VenvPython -m pip install --upgrade pip setuptools wheel

if ($LASTEXITCODE -ne 0) {
    Fail "Unable to upgrade pip/setuptools/wheel."
}

Write-Success "Python packaging tools updated"

# ------------------------------------------------------------
# Project dependencies
# ------------------------------------------------------------

Write-Step "Installing intune-visual-doc dependencies"

Write-Host 'Running: pip install -e ".[dev]"'
Write-Host ""

& $VenvPython -m pip install -e ".[dev]"

if ($LASTEXITCODE -ne 0) {
    Fail 'Project dependency installation failed: pip install -e ".[dev]"'
}

Write-Success "Project dependencies installed"

# ------------------------------------------------------------
# Playwright
# ------------------------------------------------------------

Write-Step "Installing Playwright Chromium"

& $VenvPython -m playwright install chromium

if ($LASTEXITCODE -ne 0) {
    Fail "Playwright Chromium installation failed."
}

Write-Success "Chromium installed"

# ------------------------------------------------------------
# Validation
# ------------------------------------------------------------

Write-Step "Validating installation"

Write-Host "Python:"
& $VenvPython --version

if ($LASTEXITCODE -ne 0) {
    Fail "Virtual environment Python validation failed."
}

Write-Host ""
Write-Host "pip:"
& $VenvPython -m pip --version

if ($LASTEXITCODE -ne 0) {
    Fail "pip validation failed."
}

Write-Host ""
Write-Host "Playwright:"
& $VenvPython -m playwright --version

if ($LASTEXITCODE -ne 0) {
    Fail "Playwright validation failed."
}

Write-Host ""
Write-Host "Testing Python Playwright import..."

& $VenvPython -c "from playwright.sync_api import sync_playwright; print('Playwright Python module: OK')"

if ($LASTEXITCODE -ne 0) {
    Fail "Python can not import Playwright."
}

# ------------------------------------------------------------
# Test launching Chromium
# ------------------------------------------------------------

Write-Host ""
Write-Host "Testing headless Chromium startup..."

$PlaywrightTest = @'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content("<html><title>Intune Visual Doc Test</title></html>")
    assert page.title() == "Intune Visual Doc Test"
    browser.close()

print("Chromium launch: OK")
'@

$PlaywrightTest | & $VenvPython -

if ($LASTEXITCODE -ne 0) {
    Fail "Chromium installed but failed its launch test."
}

Write-Success "Chromium launch test passed"

# ------------------------------------------------------------
# Complete
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

Write-Host ""
Write-Host "Project:" -ForegroundColor Cyan
Write-Host "  $InstallPath"

Write-Host ""
Write-Host "Virtual environment:" -ForegroundColor Cyan
Write-Host "  $VenvPath"

Write-Host ""
Write-Host "To work with the project later:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  cd `"$InstallPath`""
Write-Host "  .\.venv\Scripts\Activate.ps1"

Write-Host ""
Write-Host "Or bypass activation entirely:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  .\.venv\Scripts\python.exe <script.py>"

Write-Host ""
Write-Host "Setup completed successfully." -ForegroundColor Green
