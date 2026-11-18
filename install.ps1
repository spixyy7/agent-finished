<#
.SYNOPSIS
  Installs finished: Python environment, the Kokoro voice model, the `finished`
  command, and connects the AI agents on this computer (required).

.DESCRIPTION
  finished only works when your agents call it, so connecting them is part of the
  install, not an option. The installer asks once before it changes anything.
  Use -Yes to agree up front (for scripts). Undo any time with: finished unregister

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install.ps1
#>
param(
    [switch]$Yes,
    [string]$BinDir = "$HOME\.local\bin"
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'
$script = Join-Path $root 'finished.py'
$hasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)

Write-Host ''
Write-Host 'finished - your AI agents tell you when they are done, out loud' -ForegroundColor Magenta
Write-Host ''
Write-Host 'finished works by your agents calling it, so this install also connects them (required):'
Write-Host '  - adds the notify_finished tool (MCP) to Claude Code, Codex, Gemini, Cursor, OpenCode, Grok, Qwen, Windsurf'
Write-Host '  - turns on automatic notifications when a turn ends (Claude Code Stop hook, Codex notify;'
Write-Host '    a notify program you already have keeps working, it is run right after)'
Write-Host '  - adds one short rule to their global instructions (CLAUDE.md, AGENTS.md, GEMINI.md, ...)'
Write-Host 'Only agents installed on this computer are touched. Every changed file is backed up first.'
Write-Host 'Undo any time: finished unregister'
Write-Host ''
if (-not $Yes) {
    $answer = Read-Host 'Install finished and connect your agents? [Y/n]'
    if ($answer -match '^\s*(n|no)\s*$') {
        Write-Host 'Stopped. finished needs your agents connected to work, so nothing was installed.' -ForegroundColor Yellow
        exit 1
    }
}

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
[IO.File]::WriteAllText((Join-Path $BinDir 'finished.cmd'), "@echo off`r`n`"$py`" `"$script`" %*`r`n")
$sh = "#!/bin/sh`nexec `"$($py -replace '\\', '/')`" `"$($script -replace '\\', '/')`" `"`$@`"`n"
[IO.File]::WriteAllText((Join-Path $BinDir 'finished'), $sh)
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($userPath -split ';') -notcontains $BinDir) {
    [Environment]::SetEnvironmentVariable('Path', ($(if ($userPath) { "$userPath;$BinDir" } else { $BinDir })), 'User')
    Write-Host "     added $BinDir to your PATH - open a new terminal to use it"
}

Write-Host '4/4  Connecting your agents'
& $py $script register all
if ($LASTEXITCODE) { throw 'Connecting the agents failed. Run "finished register" to try again.' }

& $py $script -w -l en 'finished is installed'
Write-Host 'Done. Restart your agents, then try: finished setup' -ForegroundColor Green
