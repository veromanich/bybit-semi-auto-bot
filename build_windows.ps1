param(
    [switch]$Console
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

$Python = "python"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $Python = $VenvPython
}

Invoke-Checked $Python -m pip install -r requirements.txt
Invoke-Checked $Python -m pip install -r requirements-build.txt

$WindowMode = @("--windowed")
if ($Console) {
    $WindowMode = @("--console")
}

Invoke-Checked $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name "BybitSemiAutoBot" `
    @WindowMode `
    --collect-all "customtkinter" `
    --hidden-import "pybit" `
    --hidden-import "dotenv" `
    "run_bot.py"

if (Test-Path ".env.example") {
    Copy-Item ".env.example" "dist\.env.example" -Force
}

Write-Host ""
Write-Host "Done. Send your friend these files:"
Write-Host "  dist\BybitSemiAutoBot.exe"
Write-Host "  dist\.env.example"
Write-Host ""
Write-Host "Your friend should rename .env.example to .env and fill in their own Bybit API keys."
