FROM python:3.13-slim

WORKDIR /app

# Installer dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copier et installer les dépendances Python du backend
COPY sam/requirements.txt ./sam/requirements.txt
RUN pip install --no-cache-dir -r sam/requirements.txt

# Copier le code backend
COPY sam ./sam

# Port utilisé par uvicorn dans le conteneur
ENV PORT=8080
EXPOSE 8080

# Commande de démarrage FastAPI
CMD ["uvicorn", "sam.api:app", "--host", "0.0.0.0", "--port", "8080"]

