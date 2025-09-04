#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- Installing system dependencies (running as root) ---"
# Pas de 'sudo' car l'environnement de build de Render est déjà root.
apt-get update
apt-get install -y --no-install-recommends \
    pandoc \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-lang-french \
    texlive-latex-extra \
    texlive-latex-recommended \
    texlive-science \
    texlive-fonts-extra \
    lmodern \
    fonts-freefont-ttf \
    texlive-base

echo "--- Installing Python dependencies ---"
pip install --upgrade pip
pip install -r requirements.txt

echo "--- Verifying installations ---"
pandoc --version
# On vérifie que xelatex est bien installé et accessible
if ! command -v xelatex &> /dev/null
then
    echo "FATAL: xelatex command could not be found after installation."
    exit 1
fi
echo "xelatex command found successfully. Build should succeed."