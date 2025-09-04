#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- Installing system dependencies ---"
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

# Install minimal LaTeX base that includes xelatex
apt-get install -y --no-install-recommends texlive-base

echo "--- Installing Python dependencies ---"
pip install --upgrade pip
pip install -r requirements.txt

echo "--- Verifying installations ---"
pandoc --version
which xelatex || echo "xelatex not found, but we'll try to continue"