# Gera dist\bip.exe (arquivo único, sem console).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
& .venv\Scripts\pyinstaller --noconfirm --clean --onefile --noconsole --name bip `
    --add-data "bip/static;bip/static" `
    --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 `
    run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }
Get-Item dist\bip.exe | Select-Object Name, Length
