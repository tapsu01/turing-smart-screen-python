#!/bin/sh
# Build "Turing Screen.app" (dist/) from turing-screen-macos.spec with the project virtual environment.
# Requirements: .venv with requirements.txt installed (PyInstaller included), Homebrew libusb (brew install libusb).
set -e

cd "$(dirname "$0")/.."

PYTHON=.venv/bin/python
if [ ! -x "$PYTHON" ]; then
  echo "Missing virtual environment: create .venv and install requirements.txt first" >&2
  exit 1
fi
if [ ! -f /opt/homebrew/lib/libusb-1.0.0.dylib ]; then
  echo "Missing libusb: brew install libusb" >&2
  exit 1
fi

"$PYTHON" -m PyInstaller --noconfirm --clean turing-screen-macos.spec

echo
echo "Built: dist/Turing Screen.app ($(du -sh "dist/Turing Screen.app" | cut -f1))"
echo "Install: drag it to /Applications (or ~/Applications)"
