#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Install system dependencies (pandoc and LaTeX)
echo "--- Installing system dependencies ---"
apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-lang-french \
    texlive-latex-extra \
    texlive-latex-recommended \
    lmodern

# 2. Install Python dependencies
echo "--- Installing Python dependencies ---"
pip install --upgrade pip
pip install -r requirements.txt

# 3. Verify pandoc installation
echo "--- Verifying pandoc installation ---"
pandoc --version
which pandoc