#!/usr/bin/env bash
# Shell Installer for Antigravity Honcho Plugin
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<user>/antigravity-honcho/main/install.sh | bash

set -e

PLUGIN_DIR="$HOME/.gemini/config/plugins/honcho"
echo "Instalando plugin Antigravity Honcho em: $PLUGIN_DIR"

mkdir -p "$PLUGIN_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/plugin.json" ]; then
    echo "Copiando arquivos locais..."
    cp -R "$SCRIPT_DIR/"* "$PLUGIN_DIR/"
else
    if command -v git >/dev/null 2>&1; then
        if [ -d "$PLUGIN_DIR/.git" ]; then
            git -C "$PLUGIN_DIR" pull
        else
            rm -rf "$PLUGIN_DIR"
            git clone "https://github.com/plastic-labs/antigravity-honcho.git" "$PLUGIN_DIR"
        fi
    else
        echo "Erro: git não encontrado. Por favor clone o repositório diretamente em $PLUGIN_DIR" >&2
        exit 1
    fi
fi

echo "Plugin Honcho instalado com sucesso!"
echo "Reinicie o Antigravity para que o plugin seja carregado."
