#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# start.sh — Melissa v5.0 Ultra — inicio completo en un comando
# ═══════════════════════════════════════════════════════════════════════════════

set -e
MELISSA_DIR="/home/ubuntu/melissa"
VENV="$MELISSA_DIR/.venv"
ENV_FILE="$MELISSA_DIR/.env"

echo ""
echo "  Melissa v5.0 Ultra — arranque"
echo "══════════════════════════════════"

# ── 1. Directorio ─────────────────────────────────────────────────────────────
cd "$MELISSA_DIR"

# ── 2. Python virtual env (si no existe) ──────────────────────────────────────
if [ ! -d "$VENV" ]; then
  echo "  Creando entorno virtual..."
  python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"

# ── 3. Dependencias ───────────────────────────────────────────────────────────
echo "  Instalando dependencias..."
pip install --quiet --upgrade pip
pip install --quiet \
  fastapi \
  "uvicorn[standard]" \
  httpx \
  python-dotenv \
  aiofiles \
  pydantic \
  openai \
  anthropic

echo "  Dependencias OK"

# ── 4. Validar .env ───────────────────────────────────────────────────────────
echo ""
echo "  Variables de entorno:"
check_var() {
  local name=$1
  local required=$2
  local val
  val=$(grep -E "^${name}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs 2>/dev/null)
  if [ -n "$val" ] && [ "$val" != "" ]; then
    echo "  [OK] $name"
  elif [ "$required" = "required" ]; then
    echo "  [!!] $name — FALTA (requerida)"
  else
    echo "  [--] $name — no configurada (opcional)"
  fi
}

check_var "TELEGRAM_TOKEN"    required
check_var "OPENROUTER_API_KEY" required
check_var "MASTER_API_KEY"    required
check_var "SERP_API_KEY"      optional
check_var "BRAVE_API_KEY"     optional
check_var "APIFY_API_KEY"     optional
check_var "GEMINI_API_KEY"    optional
check_var "ANTHROPIC_API_KEY" optional
check_var "N8N_WEBHOOK_URL"   optional

# Inyectar SERP_API_KEY automaticamente si se pasa como argumento
# Uso: ./start.sh --serp-key=TU_CLAVE
for arg in "$@"; do
  case $arg in
    --serp-key=*)
      SERP_KEY="${arg#*=}"
      if grep -q "SERP_API_KEY" "$ENV_FILE" 2>/dev/null; then
        sed -i "s/^SERP_API_KEY=.*/SERP_API_KEY=${SERP_KEY}/" "$ENV_FILE"
      else
        echo "SERP_API_KEY=${SERP_KEY}" >> "$ENV_FILE"
      fi
      echo "  [OK] SERP_API_KEY actualizada"
      ;;
  esac
done

# ── 5. Verificar archivos requeridos ──────────────────────────────────────────
echo ""
echo "  Archivos:"
for f in melissa.py search.py knowledge_base.py; do
  if [ -f "$MELISSA_DIR/$f" ]; then
    echo "  [OK] $f"
  else
    echo "  [!!] $f — NO ENCONTRADO"
  fi
done

# ── 6. PM2 ────────────────────────────────────────────────────────────────────
echo ""
echo "  Iniciando con PM2..."
pm2 delete melissa 2>/dev/null || true
pm2 start melissa.py \
  --name melissa \
  --interpreter "$VENV/bin/python3" \
  --restart-delay=3000 \
  --max-restarts=10 \
  --log "$MELISSA_DIR/logs/melissa.log" \
  --error "$MELISSA_DIR/logs/error.log"
pm2 save

# ── 7. Health check ───────────────────────────────────────────────────────────
echo "  Esperando que arranque..."
sleep 4

PORT=$(grep -E "^PORT=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' | xargs 2>/dev/null)
PORT=${PORT:-8001}

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
  echo "  [OK] Health check OK (puerto $PORT)"
else
  echo "  [!!] Health check fallo (HTTP $HTTP_STATUS)"
  echo "  Revisa los logs: pm2 logs melissa"
fi

# ── 8. Webhook ────────────────────────────────────────────────────────────────
WEBHOOK_RESULT=$(curl -s "http://localhost:$PORT/setup-webhook" 2>/dev/null || echo "error")
if echo "$WEBHOOK_RESULT" | grep -q "ok\|success\|webhook"; then
  echo "  [OK] Webhook configurado"
else
  echo "  [--] Webhook: revisa manualmente /setup-webhook"
fi

# ── 9. Crear directorio de logs si no existe ──────────────────────────────────
mkdir -p "$MELISSA_DIR/logs"

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════"
echo "  Melissa online en puerto $PORT"
echo ""
echo "  Comandos utiles:"
echo "    pm2 logs melissa          ver logs en vivo"
echo "    pm2 restart melissa       reiniciar"
echo "    pm2 stop melissa          detener"
echo "    tail -f logs/melissa.log  logs completos"
echo ""
echo "  Abre Telegram y escribe al bot para empezar."
echo "══════════════════════════════════"
