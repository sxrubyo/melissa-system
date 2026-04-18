#!/bin/bash
# install.sh — instala 'melissa' como comando del sistema
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/melissa_cli.py"
[ ! -f "$SRC" ] && { echo "melissa_cli.py no encontrado en $SCRIPT_DIR"; exit 1; }
chmod +x "$SRC"
if [[ "$1" == "--user" ]]; then
  mkdir -p "$HOME/.local/bin"
  cp "$SRC" "$HOME/.local/bin/melissa"
  chmod +x "$HOME/.local/bin/melissa"
  echo "✓ melissa instalado en ~/.local/bin/melissa"
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
  echo "Ejecuta: source ~/.bashrc"
else
  sudo cp "$SRC" /usr/local/bin/melissa
  sudo chmod +x /usr/local/bin/melissa
  echo "✓ melissa instalado en /usr/local/bin/melissa"
fi
echo ""
echo "Prueba: melissa init"
