#!/usr/bin/env bash
# Déploiement du backend sur une VM Oracle Cloud (Ubuntu + Docker).
# Usage sur la VM :
#   chmod +x deploy/oci-backend.sh
#   export ENV_FILE=/home/ubuntu/mosam-api.env   # fichier avec les variables (voir ci-dessous)
#   ./deploy/oci-backend.sh
#
# Variables minimales dans ENV_FILE (une par ligne, KEY=value) :
#   OPENAI_API_KEY=...
#   SUPABASE_DB_POOLER_URL=postgresql://...
#   SUPABASE_URL=...
#   SUPABASE_SERVICE_ROLE_KEY=...
#   SUPABASE_JWT_SECRET=...
#   (optionnel) UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE_NAME="${IMAGE_NAME:-mosam-api}"
CONTAINER_NAME="${CONTAINER_NAME:-mosam-api}"
HOST_PORT="${HOST_PORT:-8080}"
ENV_FILE="${ENV_FILE:-}"

if [[ -z "$ENV_FILE" || ! -f "$ENV_FILE" ]]; then
  echo "Définis ENV_FILE vers un fichier existant, ex. :"
  echo "  export ENV_FILE=\$HOME/mosam-api.env"
  echo "  ./deploy/oci-backend.sh"
  exit 1
fi

echo "Build image $IMAGE_NAME (depuis $ROOT)..."
if docker info 2>/dev/null | grep -qi 'aarch64\|arm64'; then
  docker build -t "$IMAGE_NAME" -f Dockerfile .
else
  echo "Si la VM est ARM (Ampere A1) et ton build est sur x86, build sur la VM ou utilise :"
  echo "  docker buildx build --platform linux/arm64 -t $IMAGE_NAME -f Dockerfile . --load"
  docker build -t "$IMAGE_NAME" -f Dockerfile .
fi

docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
echo "Run $CONTAINER_NAME sur le port hôte $HOST_PORT..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "0.0.0.0:${HOST_PORT}:8080" \
  --env-file "$ENV_FILE" \
  "$IMAGE_NAME"

echo "OK — API : http://$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}'):${HOST_PORT}/docs"
echo "Health : .../${HOST_PORT}/health"
