# PowerShell Installer for Antigravity Honcho Plugin
# Usage:
#   irm https://raw.githubusercontent.com/jspenst/antigravity-honcho/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$PluginDir = Join-Path $env:USERPROFILE ".gemini\config\plugins\honcho"
Write-Host "Installing Antigravity Honcho plugin to: $PluginDir" -ForegroundColor Cyan

New-Item -ItemType Directory -Path $PluginDir -Force | Out-Null

# If run from a local clone:
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir "plugin.json"))) {
    Write-Host "Copying local files..." -ForegroundColor Green
    $Excluded = @(".git", "__pycache__", "*.pyc", "*.pyo", "*.tmp", ".env*", "config.json", "*state.json", ".honcho", "*.pem", "*.key")
    Get-ChildItem -Path $ScriptDir -Exclude $Excluded | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $PluginDir -Recurse -Force
    }
} else {
    Write-Host "Downloading files from repository..." -ForegroundColor Yellow
    # Fallback to git clone if available
    if (Get-Command git -ErrorAction SilentlyContinue) {
        if (Test-Path (Join-Path $PluginDir ".git")) {
            git -C $PluginDir pull
        } else {
            Remove-Item -Path $PluginDir -Recurse -Force -ErrorAction SilentlyContinue
            git clone "https://github.com/jspenst/antigravity-honcho.git" $PluginDir
        }
    } else {
        throw "Git not found. Please clone the repository directly to $PluginDir"
    }
}

Write-Host "Honcho plugin installed successfully!" -ForegroundColor Green
Write-Host "Restart Antigravity for the plugin to be loaded." -ForegroundColor Cyan
