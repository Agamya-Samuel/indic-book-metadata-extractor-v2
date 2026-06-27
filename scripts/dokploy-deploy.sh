#!/usr/bin/env bash
# =============================================================================
# dokploy-deploy.sh — Push code and trigger Dokploy deployment
# =============================================================================
# Usage:
#   ./scripts/dokploy-deploy.sh                  # push + deploy
#   ./scripts/dokploy-deploy.sh --no-push        # deploy only (skip git push)
#   ./scripts/dokploy-deploy.sh --status         # check last deployment status
#
# Required env vars (set in .env or export before running):
#   DOKPLOY_URL        — e.g. https://dokploy.yourdomain.com
#   DOKPLOY_TOKEN      — API token from Dokploy → Settings → API Keys
#   DOKPLOY_COMPOSE_ID — ID of the docker-compose service (see below)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load .env if present
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# ── Config ─────────────────────────────────────────────────────────────────────

DOKPLOY_URL="${DOKPLOY_URL:-}"
DOKPLOY_TOKEN="${DOKPLOY_TOKEN:-}"
DOKPLOY_COMPOSE_ID="${DOKPLOY_COMPOSE_ID:-}"
BRANCH="${DOKPLOY_DEPLOY_BRANCH:-main}"

# ── Helpers ────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}▸${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
fail()  { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

api() {
    local method="$1" endpoint="$2" body="${3:-}"
    local args=(-s -S -w "\n%{http_code}")
    args+=(-H "x-api-key: ${DOKPLOY_TOKEN}")
    args+=(-H "Content-Type: application/json")

    if [ -n "$body" ]; then
        args+=(-X "$method" -d "$body")
    else
        args+=(-X "$method")
    fi

    local response
    response=$(curl "${args[@]}" "${DOKPLOY_URL}${endpoint}" 2>&1) || fail "API request failed: $response"

    local http_code body_text
    http_code=$(echo "$response" | tail -1)
    body_text=$(echo "$response" | sed '$d')

    if [ "$http_code" -ge 400 ]; then
        fail "API returned HTTP $http_code: $body_text"
    fi
    echo "$body_text"
}

# ── Preflight checks ──────────────────────────────────────────────────────────

check_config() {
    local missing=()
    [ -z "$DOKPLOY_URL" ]        && missing+=("DOKPLOY_URL")
    [ -z "$DOKPLOY_TOKEN" ]      && missing+=("DOKPLOY_TOKEN")
    [ -z "$DOKPLOY_COMPOSE_ID" ] && missing+=("DOKPLOY_COMPOSE_ID")

    if [ ${#missing[@]} -gt 0 ]; then
        fail "Missing required env vars: ${missing[*]}\n\nSet them in .env or export them. See DEPLOY.md for setup instructions."
    fi
}

# ── Commands ───────────────────────────────────────────────────────────────────

cmd_help() {
    cat <<EOF
Dokploy Deploy Script — Indic Book Metadata Extractor

Usage:
  ./scripts/dokploy-deploy.sh [OPTIONS]

Options:
  --no-push       Skip git push, just trigger deploy
  --status        Check the last deployment status
  --env-setup     Show env var setup instructions for Dokploy
  -h, --help      Show this help

Environment variables:
  DOKPLOY_URL         Dokploy instance URL (e.g. https://dokploy.example.com)
  DOKPLOY_TOKEN       API token (Dokploy → Settings → API Keys)
  DOKPLOY_COMPOSE_ID  Compose service ID (from URL when viewing the service)

Example:
  export DOKPLOY_URL=https://dokploy.example.com
  export DOKPLOY_TOKEN=dp_xxxxxxxxxxxx
  export DOKPLOY_COMPOSE_ID=abc123
  ./scripts/dokploy-deploy.sh
EOF
}

cmd_env_setup() {
    cat <<'EOF'
╔══════════════════════════════════════════════════════════════════════════════╗
║  Dokploy Environment Variables — Copy these into Dokploy's "Environment" tab ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌─ REQUIRED (change these) ────────────────────────────────────────────────────┐

  POSTGRES_PASSWORD    = <generate a strong password>
  NEXT_PUBLIC_API_URL  = https://YOUR_DOMAIN/api

└──────────────────────────────────────────────────────────────────────────────┘

┌─ OPTIONAL (defaults work) ───────────────────────────────────────────────────┐

  APP_NAME              = Indic Book Metadata Extractor
  DEBUG                 = false
  CORS_ORIGINS          = https://YOUR_DOMAIN
  DEFAULT_OCR_LANGUAGE  = tel
  MAX_UPLOAD_SIZE_MB    = 200
  FLOWER_BASIC_AUTH     = admin:<password>

└──────────────────────────────────────────────────────────────────────────────┘

EOF
}

cmd_deploy() {
    local do_push=true
    [ "${1:-}" = "--no-push" ] && do_push=false

    check_config

    # Git push
    if $do_push; then
        info "Pushing to $BRANCH..."
        cd "$PROJECT_ROOT"
        git push origin "$BRANCH" || fail "Git push failed"
        ok "Pushed to $BRANCH"
    fi

    # Trigger Dokploy deploy
    info "Triggering Dokploy deployment..."
    local response
    response=$(api POST "/api/compose.deploy" "{\"composeId\":\"${DOKPLOY_COMPOSE_ID}\"}")
    ok "Deployment triggered"

    # Extract deploy hash if available
    local deploy_hash
    deploy_hash=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('hash',''))" 2>/dev/null || echo "")

    if [ -n "$deploy_hash" ]; then
        info "Deploy hash: $deploy_hash"
        info "Monitor at: ${DOKPLOY_URL}/dashboard/compose/${DOKPLOY_COMPOSE_ID}"
    else
        info "Monitor at: ${DOKPLOY_URL}/dashboard/compose/${DOKPLOY_COMPOSE_ID}"
    fi

    ok "Done! Deployment is running in the background."
}

cmd_status() {
    check_config

    info "Fetching deployment status..."
    local response
    response=$(api GET "/api/compose.get?composeId=${DOKPLOY_COMPOSE_ID}")

    echo ""
    echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Name:     {data.get('name', 'N/A')}\")
print(f\"  Status:   {data.get('composeStatus', 'N/A')}\")
print(f\"  Type:     {data.get('sourceType', 'N/A')}\")
print(f\"  Branch:   {data.get('branch', 'N/A')}\")
print(f\"  Repo:     {data.get('repository', 'N/A')}\")
" 2>/dev/null || echo "$response"
}

# ── Main ───────────────────────────────────────────────────────────────────────

case "${1:-}" in
    --help|-h)    cmd_help ;;
    --status)     cmd_status ;;
    --env-setup)  cmd_env_setup ;;
    --no-push)    cmd_deploy --no-push ;;
    "")           cmd_deploy ;;
    *)            fail "Unknown option: $1 (try --help)" ;;
esac
