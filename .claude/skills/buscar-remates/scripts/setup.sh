#!/usr/bin/env bash
# Instala lo necesario para la habilidad buscar-remates (una vez por sesión).
set -euo pipefail
WORK="${REMATES_WORK:-$HOME/.cache/buscar-remates}"
mkdir -p "$WORK"
if [ ! -d "$WORK/node_modules/playwright-core" ]; then
  (cd "$WORK" && npm init -y >/dev/null 2>&1 && npm i --silent playwright-core)
fi
python3 -c 'import pypdfium2' 2>/dev/null || python3 -m pip install -q pypdfium2
if [ -z "${CHROME_PATH:-}" ] && [ ! -e /opt/pw-browsers/chromium ]; then
  echo "Aviso: no encuentro Chromium. Defina CHROME_PATH con la ruta del navegador." >&2
fi
echo "Listo. REMATES_WORK=$WORK"
