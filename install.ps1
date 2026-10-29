# PowerShell Installer for Antigravity Honcho Plugin
# Usage:
#   irm https://raw.githubusercontent.com/<user>/antigravity-honcho/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$PluginDir = Join-Path $env:USERPROFILE ".gemini\config\plugins\honcho"
Write-Host "Instalando plugin Antigravity Honcho em: $PluginDir" -ForegroundColor Cyan

New-Item -ItemType Directory -Path $PluginDir -Force | Out-Null

$RepoBase = "https://raw.githubusercontent.com/plastic-labs/honcho/main/integrations/antigravity"
# Se executado a partir de clone local:
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir "plugin.json"))) {
    Write-Host "Copiando arquivos locais..." -ForegroundColor Green
    Copy-Item -Path "$ScriptDir\*" -Destination $PluginDir -Recurse -Force
} else {
    Write-Host "Baixando arquivos do repositório..." -ForegroundColor Yellow
    # Fallback git clone se disponível
    if (Get-Command git -ErrorAction SilentlyContinue) {
        if (Test-Path (Join-Path $PluginDir ".git")) {
            git -C $PluginDir pull
        } else {
            Remove-Item -Path $PluginDir -Recurse -Force -ErrorAction SilentlyContinue
            git clone "https://github.com/plastic-labs/antigravity-honcho.git" $PluginDir
        }
    } else {
        throw "Git não encontrado. Por favor clone o repositório diretamente em $PluginDir"
    }
}

Write-Host "Plugin Honcho instalado com sucesso!" -ForegroundColor Green
Write-Host "Reinicie o Antigravity para que o plugin seja carregado." -ForegroundColor Cyan
