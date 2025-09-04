#!/usr/bin/env bash
set -o errexit

echo "--- Installing Pandoc and LaTeX ---"
apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-lang-french \
    texlive-latex-extra \
    texlive-latex-recommended \
    texlive-science \
    texlive-fonts-extra \
    lmodern \
    fonts-freefont-ttf

echo "--- Installing Python dependencies ---"
pip install --upgrade pip
pip install -r requirements.txt

echo "--- Verifying installations ---"
pandoc --version
xelatex --version