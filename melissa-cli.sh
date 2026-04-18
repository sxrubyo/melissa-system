#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# melissa-cli — Deploy y gestión de instancias Melissa
#
# Uso:
#   ./melissa-cli nuevo-cliente            → crea nueva instancia interactivamente
#   ./melissa-cli nuevo-cliente mi-clinica → nombre directo
#   ./melissa-cli listar                   → ver todas las instancias activas
#   ./melissa-cli estado mi-clinica        → ver estado de una instancia
#   ./melissa-cli detener mi-clinica       → detener instancia
#   ./melissa-cli reiniciar mi-clinica     → reiniciar instancia
#   ./melissa-cli eliminar mi-clinica      → eliminar instancia completamente
#   ./melissa-cli logs mi-clinica          → ver logs en vivo
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# ── Configuración ──────────────────────────────────────────────────────────────
MELISSA_TEMPLATE="/home/ubuntu/melissa"          # instancia base/template
INSTANCES_DIR="/home/ubuntu/melissa-instances"   # donde viven los clientes
PORT_START=8002                                  # primer puerto disponible (8001 = template)
PORT_MAX=8099                                    # máximo 98 instancias

# ── Colores ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; PURPLE='\033[0;35m'; CYAN='\033[0;36m'; NC='\033[0m'

# ── Helpers ────────────────────────────────────────────────────────────────────
info()    { echo -e "${CYAN}  $1${NC}"; }
success() { echo -e "${GREEN}  ✓ $1${NC}"; }
warn()    { echo -e "${YELLOW}  ! $1${NC}"; }
error()   { echo -e "${RED}  ✗ $1${NC}"; }
header()  { echo -e "\n${PURPLE}══ $1 ══${NC}"; }

# ── Funciones ──────────────────────────────────────────────────────────────────

next_free_port() {
    for port in $(seq $PORT_START $PORT_MAX); do
        if ! lsof -i ":$port" >/dev/null 2>&1; then
            echo $port
            return
        fi
    done
    echo ""
}

slug() {
    # Normaliza nombre: "Mi Clínica" -> "mi-clinica"
    echo "$1" | tr '[:upper:]' '[:lower:]' | \
        sed 's/[áäâà]/a/g; s/[éëêè]/e/g; s/[íïîì]/i/g; s/[óöôò]/o/g; s/[úüûù]/u/g; s/ñ/n/g' | \
        tr -cs '[:alnum:]' '-' | sed 's/^-//; s/-$//'
}

instance_dir() { echo "$INSTANCES_DIR/$1"; }
instance_env()  { echo "$INSTANCES_DIR/$1/.env"; }
instance_db()   { echo "$INSTANCES_DIR/$1/melissa.db"; }
pm2_name()      { echo "melissa-$1"; }

# ══════════════════════════════════════════════════════════════════════════════
# COMANDO: nuevo-cliente
# ══════════════════════════════════════════════════════════════════════════════

cmd_nuevo_cliente() {
    local client_name="$1"
    header "Nuevo Cliente Melissa"

    # ── Nombre del cliente ────────────────────────────────────────────────────
    if [ -z "$client_name" ]; then
        echo ""
        read -p "  Nombre del cliente (ej: clinica-bella): " client_name
    fi

    if [ -z "$client_name" ]; then
        error "Necesitas dar un nombre para el cliente."
        exit 1
    fi

    local NAME
    NAME=$(slug "$client_name")
    local DIR
    DIR=$(instance_dir "$NAME")

    if [ -d "$DIR" ]; then
        error "Ya existe una instancia con el nombre '$NAME'."
        info "Usa: ./melissa-cli estado $NAME"
        exit 1
    fi

    # ── Puerto ────────────────────────────────────────────────────────────────
    local PORT
    PORT=$(next_free_port)
    if [ -z "$PORT" ]; then
        error "No hay puertos disponibles ($PORT_START-$PORT_MAX). Revisa instancias activas."
        exit 1
    fi

    echo ""
    info "Nombre:  $NAME"
    info "Puerto:  $PORT"
    info "Directorio: $DIR"
    echo ""

    # ── Token de Telegram ─────────────────────────────────────────────────────
    echo -e "${YELLOW}  Necesito el Telegram Bot Token para este cliente.${NC}"
    echo    "  Cómo obtenerlo: abre @BotFather en Telegram → /newbot → copia el token"
    echo ""
    read -p "  Token de Telegram: " TELEGRAM_TOKEN

    if [ -z "$TELEGRAM_TOKEN" ]; then
        error "El Token de Telegram es obligatorio."
        exit 1
    fi

    # ── BASE_URL ──────────────────────────────────────────────────────────────
    # Intentar detectar IP pública del servidor
    PUBLIC_IP=$(curl -s https://api.ipify.org 2>/dev/null || echo "")
    if [ -n "$PUBLIC_IP" ]; then
        DEFAULT_URL="http://${PUBLIC_IP}:${PORT}"
    else
        DEFAULT_URL="http://TU-IP:${PORT}"
    fi

    echo ""
    read -p "  URL pública de este cliente [$DEFAULT_URL]: " BASE_URL
    BASE_URL="${BASE_URL:-$DEFAULT_URL}"

    # ── Master API Key ────────────────────────────────────────────────────────
    MASTER_KEY="melissa_$(openssl rand -hex 8 2>/dev/null || echo "${NAME}_$(date +%s)")"

    # ══════════════════════════════════════════════════════════════════════════
    # Crear la instancia
    # ══════════════════════════════════════════════════════════════════════════
    header "Creando instancia"

    # 1. Crear directorio
    mkdir -p "$DIR"
    mkdir -p "$DIR/logs"
    success "Directorio creado"

    # 2. Copiar archivos de Melissa (sin DB, sin .env — sesión nueva limpia)
    for f in melissa.py search.py knowledge_base.py requirements.txt; do
        if [ -f "$MELISSA_TEMPLATE/$f" ]; then
            cp "$MELISSA_TEMPLATE/$f" "$DIR/$f"
        fi
    done
    success "Archivos copiados"

    # 3. Copiar .env base y personalizarlo
    cp "$MELISSA_TEMPLATE/.env" "$DIR/.env.base" 2>/dev/null || true

    # Leer claves de la instalación base (LLM, búsqueda, etc.)
    GROQ_KEY=""
    GEMINI_KEY=""
    GEMINI_KEY_2=""
    GEMINI_KEY_3=""
    GEMINI_KEY_4=""
    GEMINI_KEY_5=""
    GEMINI_KEY_6=""
    GEMINI_KEY_7=""
    OPENROUTER_KEY=""
    OPENAI_KEY=""
    SERP_KEY=""
    BRAVE_KEY=""

    if [ -f "$MELISSA_TEMPLATE/.env" ]; then
        GROQ_KEY=$(grep "^GROQ_API_KEY=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        GEMINI_KEY=$(grep "^GEMINI_API_KEY=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        GEMINI_KEY_2=$(grep "^GEMINI_API_KEY_2=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        GEMINI_KEY_3=$(grep "^GEMINI_API_KEY_3=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        GEMINI_KEY_4=$(grep "^GEMINI_API_KEY_4=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        GEMINI_KEY_5=$(grep "^GEMINI_API_KEY_5=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        GEMINI_KEY_6=$(grep "^GEMINI_API_KEY_6=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        GEMINI_KEY_7=$(grep "^GEMINI_API_KEY_7=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        OPENROUTER_KEY=$(grep "^OPENROUTER_API_KEY=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        OPENAI_KEY=$(grep "^OPENAI_API_KEY=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        SERP_KEY=$(grep "^SERP_API_KEY=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
        BRAVE_KEY=$(grep "^BRAVE_API_KEY=" "$MELISSA_TEMPLATE/.env" | cut -d= -f2-)
    fi

    # Escribir .env limpio para esta instancia
    cat > "$DIR/.env" << ENVEOF
# ═══════════════════════════════════════════════════════════════════════════════
# Melissa — Instancia: $NAME
# Creada: $(date '+%Y-%m-%d %H:%M')
# Puerto: $PORT
# ═══════════════════════════════════════════════════════════════════════════════

# Telegram — BOT EXCLUSIVO de este cliente
TELEGRAM_TOKEN=$TELEGRAM_TOKEN
PLATFORM=telegram

# LLM — claves compartidas de la infraestructura base
GROQ_API_KEY=$GROQ_KEY
GEMINI_API_KEY=$GEMINI_KEY
GEMINI_API_KEY_2=$GEMINI_KEY_2
GEMINI_API_KEY_3=$GEMINI_KEY_3
GEMINI_API_KEY_4=$GEMINI_KEY_4
GEMINI_API_KEY_5=$GEMINI_KEY_5
GEMINI_API_KEY_6=$GEMINI_KEY_6
GEMINI_API_KEY_7=$GEMINI_KEY_7
OPENROUTER_API_KEY=$OPENROUTER_KEY
OPENAI_API_KEY=$OPENAI_KEY

# Búsqueda
SERP_API_KEY=$SERP_KEY
BRAVE_API_KEY=$BRAVE_KEY

# Servidor — puerto exclusivo
PORT=$PORT
HOST=0.0.0.0
BASE_URL=$BASE_URL
WEBHOOK_SECRET=melissa_${NAME}_$(openssl rand -hex 4 2>/dev/null || echo "secret")

# Base de datos — aislada por cliente
DB_PATH=$DIR/melissa.db
VECTOR_DB_PATH=$DIR/vectors.db

# Auth — clave maestra única por cliente
MASTER_API_KEY=$MASTER_KEY

# Timing
BUFFER_WAIT_MIN=35
BUFFER_WAIT_MAX=55
BUBBLE_PAUSE_MIN=1.0
BUBBLE_PAUSE_MAX=3.0

# Calendario (opcional — configurar después)
GCAL_CLIENT_ID=
GCAL_CLIENT_SECRET=
GCAL_ACCESS_TOKEN=
GCAL_REFRESH_TOKEN=
GCAL_CALENDAR_ID=primary
CALENDLY_LINK=
ENVEOF

    success ".env configurado (puerto $PORT, token propio)"

    # 4. Lanzar con PM2
    local PM2_NAME
    PM2_NAME=$(pm2_name "$NAME")

    # Verificar si existe venv, si no crearlo
    if [ ! -d "$DIR/.venv" ]; then
        python3 -m venv "$DIR/.venv" 2>/dev/null || true
    fi

    # Instalar dependencias en segundo plano (silencioso)
    "$DIR/.venv/bin/pip" install --quiet fastapi "uvicorn[standard]" httpx python-dotenv 2>/dev/null &

    pm2 delete "$PM2_NAME" 2>/dev/null || true
    pm2 start "$DIR/melissa.py" \
        --name "$PM2_NAME" \
        --interpreter "python3" \
        --restart-delay=3000 \
        --max-restarts=10 \
        --log "$DIR/logs/melissa.log" \
        --error "$DIR/logs/error.log" \
        2>/dev/null

    pm2 save 2>/dev/null || true
    success "Instancia lanzada con PM2 ($PM2_NAME)"

    # ── 5. Integración Nova (opcional) ────────────────────────────────────────
    echo ""
    NOVA_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" \
      "http://localhost:9002/health" 2>/dev/null || echo "000")
    
    if [ "$NOVA_HEALTH" = "200" ]; then
      echo -e "  ${P}Nova está activo en el servidor.${NC}"
      read -p "  ¿Quieres que Nova gobierne esta instancia? (s/N): " WANT_NOVA
      if [[ "$WANT_NOVA" =~ ^[sS] ]]; then
        # Crear agente Nova para esta instancia
        NOVA_DIR_REF="$(dirname "$0")"
        NOVA_API_KEY=""
        if [ -f "/home/ubuntu/nova-os/.env" ]; then
          NOVA_API_KEY=$(grep "^API_KEY=\|^NOVA_API_KEY=" "/home/ubuntu/nova-os/.env" 2>/dev/null | \
            cut -d= -f2 | xargs 2>/dev/null || echo "")
        fi
        
        AGENT_RESP=$(curl -s -X POST "http://localhost:9002/tokens" \
          -H "Content-Type: application/json" \
          -H "Authorization: Bearer $NOVA_API_KEY" \
          -d "{
            \"agent_name\": \"Melissa - $NAME\",
            \"description\": \"Recepcionista virtual — $NAME\",
            \"can_do\": [
              \"send appointment confirmations\",
              \"answer questions about clinic services\",
              \"book free consultation appointments\"
            ],
            \"cannot_do\": [
              \"provide medical diagnosis\",
              \"share other patients personal information\",
              \"guarantee treatment results\"
            ],
            \"authorized_by\": \"Santiago\"
          }" 2>/dev/null || echo "{}")
        
        NOVA_TOKEN=$(echo "$AGENT_RESP" | \
          python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('token_id',''))" 2>/dev/null || echo "")
        
        if [ -n "$NOVA_TOKEN" ]; then
          echo "NOVA_URL=http://localhost:9002" >> "$DIR/.env"
          echo "NOVA_TOKEN=$NOVA_TOKEN" >> "$DIR/.env"
          echo "NOVA_ENABLED=true" >> "$DIR/.env"
          # Copiar nova_bridge.py
          [ -f "$(dirname "$0")/nova_bridge.py" ] && \
            cp "$(dirname "$0")/nova_bridge.py" "$DIR/nova_bridge.py"
          success "Nova integrado — agente: ${NOVA_TOKEN:0:20}..."
          pm2 restart "$PM2_NAME" 2>/dev/null || true
        else
          warn "No pude crear el agente Nova. Puedes configurarlo después con ./nova-setup.sh"
        fi
      fi
    fi
    sleep 4
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null || echo "000")

    if [ "$HTTP_STATUS" = "200" ]; then
        success "Health check OK"
        # Configurar webhook
        curl -s "http://localhost:$PORT/setup-webhook" >/dev/null 2>&1 || true
        success "Webhook configurado"
    else
        warn "Health check pendiente (HTTP $HTTP_STATUS) — puede tardar unos segundos más"
    fi

    # ══════════════════════════════════════════════════════════════════════════
    # Resumen final
    # ══════════════════════════════════════════════════════════════════════════
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Instancia '$NAME' creada y corriendo${NC}"
    echo -e "${GREEN}══════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${CYAN}Health:${NC}    http://localhost:$PORT/health"
    echo -e "  ${CYAN}API:${NC}       http://localhost:$PORT"
    echo -e "  ${CYAN}URL pública:${NC} $BASE_URL"
    echo ""
    echo -e "  ${YELLOW}Master Key:${NC} $MASTER_KEY"
    echo    "  (guárdala — es la clave para crear tokens de activación de admin)"
    echo ""
    echo -e "  ${CYAN}Comandos útiles:${NC}"
    echo    "  ./melissa-cli logs $NAME       → logs en vivo"
    echo    "  ./melissa-cli estado $NAME     → estado"
    echo    "  ./melissa-cli detener $NAME    → detener"
    echo ""
    echo -e "  ${YELLOW}Siguiente paso:${NC}"
    echo    "  1. Abre el bot en Telegram"
    echo    "  2. Genera un token de activación:"
    echo    "     POST $BASE_URL/api/tokens/create"
    echo    "     Header: X-Master-Key: $MASTER_KEY"
    echo    "  3. Envía el token al bot para activarlo"
    echo ""

    # Guardar metadata de la instancia
    cat > "$DIR/instance.json" << METAEOF
{
  "name": "$NAME",
  "port": $PORT,
  "base_url": "$BASE_URL",
  "pm2_name": "$PM2_NAME",
  "master_key": "$MASTER_KEY",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "running"
}
METAEOF
}

# ══════════════════════════════════════════════════════════════════════════════
# COMANDO: listar
# ══════════════════════════════════════════════════════════════════════════════

cmd_listar() {
    header "Instancias Melissa activas"

    # Siempre mostrar la instancia base
    BASE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/health" 2>/dev/null || echo "000")
    BASE_COLOR=$([[ "$BASE_STATUS" == "200" ]] && echo "$GREEN" || echo "$RED")
    echo -e "  ${BASE_COLOR}●${NC} [base]    puerto 8001  ${BASE_COLOR}$([[ "$BASE_STATUS" == "200" ]] && echo "online" || echo "offline")${NC}"

    # Instancias de clientes
    if [ ! -d "$INSTANCES_DIR" ] || [ -z "$(ls -A "$INSTANCES_DIR" 2>/dev/null)" ]; then
        echo ""
        warn "Sin instancias de clientes todavía."
        echo "  Crea una con: ./melissa-cli nuevo-cliente"
        echo ""
        return
    fi

    echo ""
    for dir in "$INSTANCES_DIR"/*/; do
        [ -d "$dir" ] || continue
        local name
        name=$(basename "$dir")
        local meta="$dir/instance.json"
        local port="?"

        if [ -f "$meta" ]; then
            port=$(python3 -c "import json; d=json.load(open('$meta')); print(d.get('port','?'))" 2>/dev/null || echo "?")
        else
            port=$(grep "^PORT=" "$dir/.env" 2>/dev/null | cut -d= -f2 || echo "?")
        fi

        local status_code
        status_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port/health" 2>/dev/null || echo "000")

        if [ "$status_code" = "200" ]; then
            # Check WhatsApp from health
            wa=$(curl -s "http://localhost:$port/health" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); w=d.get('whatsapp',{}); print('WA' if w.get('connected') else 'Telegram')" 2>/dev/null || echo "")
            echo -e "  ${GREEN}●${NC} $name    puerto $port  ${GREEN}online${NC}  ${DIM}$wa${NC}"
        else
            echo -e "  ${RED}●${NC} $name    puerto $port  ${RED}offline${NC}"
        fi
    done
    echo ""
    echo "  Para gestionar: ./melissa-cli [estado|detener|reiniciar|logs|eliminar] [nombre]"
    echo ""
}

# ══════════════════════════════════════════════════════════════════════════════
# COMANDO: estado
# ══════════════════════════════════════════════════════════════════════════════

cmd_estado() {
    local name
    name=$(slug "$1")
    local dir
    dir=$(instance_dir "$name")

    if [ ! -d "$dir" ]; then
        error "No existe instancia '$name'"
        echo "  Instancias disponibles: $(ls "$INSTANCES_DIR" 2>/dev/null | tr '\n' ' ')"
        exit 1
    fi

    local port
    port=$(grep "^PORT=" "$dir/.env" 2>/dev/null | cut -d= -f2 || echo "8002")
    local health
    health=$(curl -s "http://localhost:$port/health" 2>/dev/null || echo '{"status":"offline"}')

    header "Estado: $name"
    echo ""
    echo -e "  Puerto:    $port"
    echo -e "  PM2:       $(pm2_name "$name")"
    echo -e "  Dir:       $dir"
    echo -e "  Health:    $health" | python3 -m json.tool 2>/dev/null || echo "  Health: $health"
    echo ""
    pm2 show "$(pm2_name "$name")" 2>/dev/null | grep -E "status|restarts|uptime|memory" | head -6 || true
    echo ""
}

# ══════════════════════════════════════════════════════════════════════════════
# COMANDOS: detener / reiniciar / eliminar / logs
# ══════════════════════════════════════════════════════════════════════════════

cmd_detener() {
    local name
    name=$(slug "$1")
    pm2 stop "$(pm2_name "$name")" 2>/dev/null && success "Instancia '$name' detenida" || error "No encontrada"
}

cmd_reiniciar() {
    local name
    name=$(slug "$1")
    pm2 restart "$(pm2_name "$name")" 2>/dev/null && success "Instancia '$name' reiniciada" || error "No encontrada"
}

cmd_logs() {
    local name
    name=$(slug "$1")
    info "Logs de '$name' (Ctrl+C para salir):"
    pm2 logs "$(pm2_name "$name")" 2>/dev/null || \
        tail -f "$(instance_dir "$name")/logs/melissa.log" 2>/dev/null || \
        error "No se encontraron logs"
}

cmd_eliminar() {
    local name
    name=$(slug "$1")
    local dir
    dir=$(instance_dir "$name")

    if [ ! -d "$dir" ]; then
        error "No existe instancia '$name'"
        exit 1
    fi

    echo -e "${RED}  Esto eliminará la instancia '$name' y TODOS sus datos (DB, conversaciones, config).${NC}"
    read -p "  Confirmar (escribe el nombre '$name' para confirmar): " confirm

    if [ "$confirm" != "$name" ]; then
        info "Cancelado."
        exit 0
    fi

    pm2 delete "$(pm2_name "$name")" 2>/dev/null || true
    rm -rf "$dir"
    pm2 save 2>/dev/null || true
    success "Instancia '$name' eliminada completamente."
}

# ══════════════════════════════════════════════════════════════════════════════
# ROUTER DE COMANDOS
# ══════════════════════════════════════════════════════════════════════════════

mkdir -p "$INSTANCES_DIR"

COMMAND="${1:-}"
ARG="${2:-}"

case "$COMMAND" in
    "chat"|"melissa-chat")
        # Abrir el chat de lenguaje natural
        CHAT_SCRIPT="$(dirname "$0")/melissa-chat.py"
        if [ ! -f "$CHAT_SCRIPT" ]; then
            error "melissa-chat.py no encontrado en $(dirname "$0")"
            exit 1
        fi
        python3 "$CHAT_SCRIPT" "$ARG"
        ;;
    "nuevo-cliente"|"new"|"nuevo")
        cmd_nuevo_cliente "$ARG"
        ;;
    "listar"|"list"|"ls")
        cmd_listar
        ;;
    "estado"|"status")
        [ -z "$ARG" ] && { cmd_listar; exit 0; }
        cmd_estado "$ARG"
        ;;
    "detener"|"stop")
        [ -z "$ARG" ] && { error "Especifica el nombre de la instancia"; exit 1; }
        cmd_detener "$ARG"
        ;;
    "reiniciar"|"restart")
        [ -z "$ARG" ] && { error "Especifica el nombre de la instancia"; exit 1; }
        cmd_reiniciar "$ARG"
        ;;
    "logs")
        [ -z "$ARG" ] && { error "Especifica el nombre de la instancia"; exit 1; }
        cmd_logs "$ARG"
        ;;
    "eliminar"|"delete"|"rm")
        [ -z "$ARG" ] && { error "Especifica el nombre de la instancia"; exit 1; }
        cmd_eliminar "$ARG"
        ;;
    *)
        echo ""
        echo -e "${PURPLE}  melissa-cli${NC} — Gestión de instancias Melissa"
        echo ""
        echo -e "  ${CYAN}Comandos:${NC}"
        echo    "  chat [nombre]             Hablar con Melissa en lenguaje natural"
        echo    "  nuevo-cliente [nombre]    Crear nueva instancia para un cliente"
        echo    "  listar                    Ver todas las instancias"
        echo    "  estado [nombre]           Estado de una instancia"
        echo    "  logs [nombre]             Ver logs en vivo"
        echo    "  reiniciar [nombre]        Reiniciar instancia"
        echo    "  detener [nombre]          Detener instancia"
        echo    "  eliminar [nombre]         Eliminar instancia y sus datos"
        echo ""
        echo -e "  ${YELLOW}Ejemplos:{NC}"
        echo    "  ./melissa-cli chat                    → hablar con la instancia base"
        echo    "  ./melissa-cli chat clinica-bella      → hablar con instancia específica"
        echo    "  ./melissa-cli nuevo-cliente           → crear nuevo cliente"
        echo    "  ./melissa-cli listar"
        echo ""
        ;;
esac
