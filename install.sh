#!/usr/bin/env bash
set -euo pipefail
if [[ "${EUID}" -ne 0 ]]; then echo "Run with sudo: sudo ./install.sh"; exit 1; fi
apt-get update
apt-get install -y python3-venv pipx exiftool
install_dir="/opt/customosint"
python3 -m venv "$install_dir/.venv"
"$install_dir/.venv/bin/pip" install "$(pwd)"
ln -sfn "$install_dir/.venv/bin/customosint" /usr/local/bin/customosint
echo "Core installed. Optional providers: pipx install maigret sherlock-project holehe"

