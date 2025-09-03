#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Installer les dépendances système (pandoc pour les PDF)
echo "--- Installing system dependencies ---"
apt-get update && apt-get install -y pandoc texlive-xetex texlive-fonts-recommended texlive-lang-french

# 2. Installer les paquets Python
echo "--- Installing Python dependencies ---"
pip install -r requirements.txt