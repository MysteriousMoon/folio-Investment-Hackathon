#!/bin/zsh
set -e
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
if [[ ! -f .env ]]; then cp .env.example .env; fi
chmod 600 .env
exec .venv/bin/python app.py
