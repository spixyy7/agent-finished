<#
.SYNOPSIS
  Installs finished: Python environment, the Kokoro voice model, the `finished`
  command, and with -Register the MCP tool in every agent found on this computer.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install.ps1 -Register
#>
param(
    [switch]$Register,
    [string]$BinDir = "$HOME\.local\bin"
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'
$hasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)

Write-Host '1/4  Python environment'
if (-not (Test-Path $py)) {
    if ($hasUv) { uv venv (Join-Path $root '.venv') --python 3.12 }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { py -3.12 -m venv (Join-Path $root '.venv') }
    else { python -m venv (Join-Path $root '.venv') }
    if (-not (Test-Path $py)) { throw 'Could not create the Python environment. Install Python 3.10-3.13 or uv.' }
}
if ($hasUv) { uv pip install --python $py -r (Join-Path $root 'requirements.txt') }
else { & $py -m pip install --disable-pip-version-check -r (Join-Path $root 'requirements.txt') }
if ($LASTEXITCODE) { throw 'Installing the Python packages failed.' }

Write-Host '2/4  Voice model (Kokoro-82M, about 350 MB, downloaded once)'
$models = Join-Path $root 'models'
New-Item -ItemType Directory -Force $models | Out-Null
$base = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0'
foreach ($file in 'kokoro-v1.0.onnx', 'voices-v1.0.bin') {
    $dest = Join-Path $models $file
    if (-not (Test-Path $dest)) {
        curl.exe -L --fail --progress-bar -o "$dest.part" "$base/$file"
        if ($LASTEXITCODE) { throw "Downloading $file failed." }
        Move-Item -Force "$dest.part" $dest
    }
}

Write-Host '3/4  The finished command'
New-Item -ItemType Directory -Force $BinDir | Out-Null
$script = Join-Path $root 'finished.py'
[IO.File]::WriteAllText((Join-Path $BinDir 'finished.cmd'), "@echo off`r`n`"$py`" `"$script`" %*`r`n")
$sh = "#!/bin/sh`nexec `"$($py -replace '\\', '/')`" `"$($script -replace '\\', '/')`" `"`$@`"`n"
[IO.File]::WriteAllText((Join-Path $BinDir 'finished'), $sh)
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($userPath -split ';') -notcontains $BinDir) {
    [Environment]::SetEnvironmentVariable('Path', ($(if ($userPath) { "$userPath;$BinDir" } else { $BinDir })), 'User')
    Write-Host "     added $BinDir to your PATH - open a new terminal to use it"
}

Write-Host '4/4  Agents'
if ($Register) { & $py $script register all }
else { Write-Host '     run "finished register" to add the MCP tool to Claude Code, Codex, Gemini, Cursor, ...' }

& $py $script -w -l en 'finished is installed'
Write-Host 'Done. Try: finished setup'
