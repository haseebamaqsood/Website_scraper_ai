#!/usr/bin/env bash
# Install packages and start the app (Mac/Linux)
[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
