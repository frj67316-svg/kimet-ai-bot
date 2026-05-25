#!/usr/bin/env bash
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers (only Chromium needed for headless automation)
playwright install chromium
