FROM python:3.13-slim

WORKDIR /app

# Installer dépendances système minimales (compilateur + outils pour sentencepiece & PyTorch)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copier et installer les dépendances Python du backend
COPY sam/requirements.txt ./sam/requirements.txt
RUN pip install --no-cache-dir -r sam/requirements.txt

# Copier le code backend
COPY sam ./sam

# Port (OCI / Cloud Run utilisent souvent 8080)
ENV PORT=8080
EXPOSE 8080

# Premier démarrage peut être long (imports lourds).
HEALTHCHECK --interval=30s --timeout=8s --start-period=240s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5)" || exit 1

CMD ["sh", "-c", "exec uvicorn sam.api:app --host 0.0.0.0 --port ${PORT:-8080}"]

