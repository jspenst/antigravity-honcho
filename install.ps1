# PowerShell Installer for Antigravity Honcho Plugin
# Usage:
#   irm https://raw.githubusercontent.com/<user>/antigravity-honcho/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$PluginDir = Join-Path $env:USERPROFILE ".gemini\config\plugins\honcho"
Write-Host "Installing Antigravity Honcho plugin to: $PluginDir" -ForegroundColor Cyan

New-Item -ItemType Directory -Path $PluginDir -Force | Out-Null

$RepoBase = "https://raw.githubusercontent.com/plastic-labs/honcho/main/integrations/antigravity"
# If run from a local clone:
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir "plugin.json"))) {
    Write-Host "Copying local files..." -ForegroundColor Green
    Copy-Item -Path "$ScriptDir\*" -Destination $PluginDir -Recurse -Force
} else {
    Write-Host "Downloading files from repository..." -ForegroundColor Yellow
    # Fallback to git clone if available
    if (Get-Command git -ErrorAction SilentlyContinue) {
        if (Test-Path (Join-Path $PluginDir ".git")) {
            git -C $PluginDir pull
        } else {
            Remove-Item -Path $PluginDir -Recurse -Force -ErrorAction SilentlyContinue
            git clone "https://github.com/plastic-labs/antigravity-honcho.git" $PluginDir
        }
    } else {
        throw "Git not found. Please clone the repository directly to $PluginDir"
    }
}

Write-Host "Honcho plugin installed successfully!" -ForegroundColor Green
Write-Host "Restart Antigravity for the plugin to be loaded." -ForegroundColor Cyan
