# Installs blu — a CLI BLE scanner — and puts a `blu` command on your PATH.
#
# Usage (PowerShell):
#   irm https://raw.githubusercontent.com/Aiz-en/blu/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$installDir = Join-Path $env:LOCALAPPDATA "Programs\blu"

# uv runs the script and manages its Python + dependencies
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

if (Test-Path (Join-Path $installDir ".git")) {
    Write-Host "Updating existing install..."
    git -C $installDir pull --ff-only
} elseif (Get-Command git -ErrorAction SilentlyContinue) {
    git clone https://github.com/Aiz-en/blu.git $installDir
} else {
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    Invoke-WebRequest https://raw.githubusercontent.com/Aiz-en/blu/main/Blu.py `
        -OutFile (Join-Path $installDir "Blu.py")
}

# `blu` command: a shim that runs the script via uv
$shim = Join-Path $installDir "blu.cmd"
"@echo off`r`nuv run --script `"%~dp0Blu.py`" %*" | Set-Content -Path $shim -Encoding ascii

# Add the install dir to the user PATH so `blu` works in new terminals
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $installDir) {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$installDir", "User")
    Write-Host "Added $installDir to your PATH."
}

Write-Host "Done. Open a new terminal and run: blu"
