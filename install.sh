#!/usr/bin/env bash
# Shell Installer for Antigravity Honcho Plugin
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<user>/antigravity-honcho/main/install.sh | bash

set -e

PLUGIN_DIR="$HOME/.gemini/config/plugins/honcho"
echo "Installing Antigravity Honcho plugin to: $PLUGIN_DIR"

mkdir -p "$PLUGIN_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/plugin.json" ]; then
    echo "Copying local files..."
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
        echo "Error: git not found. Please clone the repository directly to $PLUGIN_DIR" >&2
        exit 1
    fi
fi

echo "Honcho plugin installed successfully!"
echo "Restart Antigravity for the plugin to be loaded."
